import glob
import json
import logging
import os
import sqlite3
import subprocess
import tempfile
import io
import soundfile
from time import sleep

import requests
import numpy as np
import librosa
from PIL import Image, ImageDraw, ImageFont

from .helpers import get_settings, ParseFileName, Detection, get_font, DB_PATH
from .notifications import sendAppriseNotifications

log = logging.getLogger(__name__)


def extract(in_file, out_file, start, stop):
    result = subprocess.run(['sox', '-V1', f'{in_file}', f'{out_file}', 'trim', f'={start}', f'={stop}'],
                            check=True, capture_output=True)
    ret = result.stdout.decode('utf-8')
    err = result.stderr.decode('utf-8')
    if err:
        raise RuntimeError(f'{ret}:\n {err}')
    return ret


def extract_safe(in_file, out_file, start, stop):
    conf = get_settings()
    # This section sets the SPACER that will be used to pad the audio clip with
    # context. If EXTRACTION_LENGTH is 10, for instance, 3 seconds are removed
    # from that value and divided by 2, so that the 3 seconds of the call are
    # within 3.5 seconds of audio context before and after.
    try:
        ex_len = conf.getint('EXTRACTION_LENGTH')
    except ValueError:
        ex_len = 6
    spacer = (ex_len - 3) / 2
    safe_start = max(0, start - spacer)
    safe_stop = min(conf.getint('RECORDING_LENGTH'), stop + spacer)

    extract(in_file, out_file, safe_start, safe_stop)


def compute_snr(audio_file):
    try:
        data, sr = soundfile.read(audio_file)
    except Exception as e:
        log.error("Error reading %s: %s", audio_file, e)
        return None
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    frame_length = int(0.05 * sr)
    hop_length = int(0.01 * sr)
    rms = librosa.feature.rms(y=data, frame_length=frame_length, hop_length=hop_length)[0]
    if rms.size == 0:
        return None
    noise_level = np.percentile(rms, 10)
    signal_level = np.percentile(rms, 90)
    noise_level = max(noise_level, 1e-8)
    snr_db = 20 * np.log10(signal_level / noise_level)
    return float(snr_db)


def compute_recording_quality(audio_path, plot_debug=False):
    try:
        y, sr = soundfile.read(audio_path)
    except Exception as e:
        log.error("Error reading %s: %s", audio_path, e)
        return None
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    if y.size == 0:
        return None
    duration = len(y) / sr
    frame_length = int(0.05 * sr)
    hop_length = int(0.01 * sr)
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    times = librosa.times_like(rms, sr=sr, hop_length=hop_length, n_fft=frame_length)
    noise_level = np.percentile(rms, 10)
    signal_level = np.percentile(rms, 90)
    if signal_level < 1e-6:
        signal_level = np.max(rms)
    noise_level = max(noise_level, 1e-8)
    snr_db = 20 * np.log10(signal_level / noise_level)
    threshold = noise_level * 2.0
    active_frames = rms > threshold
    segments = []
    if np.any(active_frames):
        diff = np.diff(active_frames.astype(int))
        start_indices = np.where(diff == 1)[0] + 1
        end_indices = np.where(diff == -1)[0] + 1
        if active_frames[0]:
            start_indices = np.concatenate(([0], start_indices))
        if active_frames[-1]:
            end_indices = np.concatenate((end_indices, [len(active_frames)]))
        for start, end in zip(start_indices, end_indices):
            seg_start_time = times[start]
            seg_end_time = times[end - 1] + (frame_length / sr)
            segments.append([seg_start_time, seg_end_time])
        merged_segments = []
        merge_gap = 0.3
        for seg in segments:
            if not merged_segments:
                merged_segments.append(seg)
            else:
                prev_seg = merged_segments[-1]
                if seg[0] - prev_seg[1] < merge_gap:
                    prev_seg[1] = seg[1]
                else:
                    merged_segments.append(seg)
        segments = merged_segments
    num_segments = len(segments)
    multiple_calls = num_segments > 1
    overlap_detected = False
    if segments:
        D = librosa.stft(y, n_fft=1024, hop_length=hop_length)
        S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
        mask = np.zeros(S_db.shape[1], dtype=bool)
        for seg in segments:
            start_col = int(seg[0] * sr / hop_length)
            end_col = int(seg[1] * sr / hop_length)
            mask[start_col:end_col + 1] = True
        for t_idx in np.where(mask)[0]:
            spectrum = np.abs(D[:, t_idx])
            if len(spectrum) == 0:
                continue
            top_idx = spectrum.argsort()[-3:][::-1]
            top_idx = top_idx[spectrum[top_idx] > 0.1 * np.max(spectrum)]
            if len(top_idx) >= 2:
                f1, f2 = freqs[top_idx[0]], freqs[top_idx[1]]
                if f1 < 1 or f2 < 1:
                    continue
                ratio = f2 / f1 if f1 > 0 else np.inf
                if not (0.95 < ratio % 1 < 1.05 or 1.95 < ratio < 2.05):
                    overlap_detected = True
                    break
    quality_score = float(snr_db)
    if multiple_calls:
        quality_score -= 5 * (num_segments - 1)
    if overlap_detected:
        quality_score -= 20
    if plot_debug:
        try:
            import matplotlib.pyplot as plt
            import librosa.display  # noqa: F401
            fig, ax = plt.subplots(2, 1, figsize=(10, 6))
            t = np.linspace(0, duration, len(y))
            ax[0].plot(t, y, label="Waveform")
            for (seg_start, seg_end) in segments:
                ax[0].axvspan(seg_start, seg_end, color='green', alpha=0.3, label='Detected Call')
            ax[0].set_title("Waveform and Detected Call Segments")
            ax[0].set_xlabel("Time (s)")
            ax[0].set_ylabel("Amplitude")
            ax[0].legend(loc="upper right")
            ax[1].plot(times, 20 * np.log10(rms + 1e-8), label="Frame Energy (dB)")
            ax[1].axhline(20 * np.log10(threshold), color='r', linestyle='--', label="Energy Threshold")
            ax[1].set_title("Short-term Energy and Threshold")
            ax[1].set_xlabel("Time (s)")
            ax[1].set_ylabel("Energy (dB)")
            ax[1].legend(loc="upper right")
            plt.tight_layout()
            plt.show()
            plt.figure(figsize=(10, 4))
            librosa.display.specshow(S_db, sr=sr, hop_length=hop_length, x_axis='time', y_axis='hz', cmap='magma')
            plt.colorbar(label='Intensity (dB)')
            plt.title("Spectrogram (dB)")
            for (seg_start, seg_end) in segments:
                plt.axvspan(seg_start, seg_end, color='cyan', alpha=0.2, label='Detected Call')
            plt.legend(loc='upper right')
            plt.show()
        except Exception as e:
            log.debug("Plot debug failed: %s", e)
    return quality_score


def spectrogram(in_file, title, comment, raw=False):
    fd, tmp_file = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    args = ['sox', '-V1', f'{in_file}', '-n', 'remix', '1', 'rate', '24k', 'spectrogram',
            '-t', '', '-c', '', '-o', tmp_file]
    args += ['-r'] if raw else []
    result = subprocess.run(args, check=True, capture_output=True)
    ret = result.stdout.decode('utf-8')
    err = result.stderr.decode('utf-8')
    if err:
        raise RuntimeError(f'{ret}:\n {err}')
    img = Image.open(tmp_file)
    height = img.size[1]
    width = img.size[0]
    draw = ImageDraw.Draw(img)
    title_font = ImageFont.truetype(get_font()['path'], 13)
    _, _, w, _ = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((width-w)/2, 6), title, fill="white", font=title_font)

    comment_font = ImageFont.truetype(get_font()['path'], 11)
    _, _, _, h = draw.textbbox((0, 0), comment, font=comment_font)
    draw.text((1, height - (h + 1)), comment, fill="white", font=comment_font)
    img.save(f'{in_file}.png')
    os.remove(tmp_file)


def extract_detection(file: ParseFileName, detection: Detection):
    conf = get_settings()
    new_file_name = f'{detection.common_name_safe}-{detection.confidence_pct}-{detection.date}-birdnet-{file.RTSP_id}{detection.time}.{conf["AUDIOFMT"]}'
    new_dir = os.path.join(conf['EXTRACTED'], 'By_Date', f'{detection.date}', f'{detection.common_name_safe}')
    new_file = os.path.join(new_dir, new_file_name)
    if os.path.isfile(new_file):
        log.warning('Extraction exists. Moving on: %s', new_file)
    else:
        os.makedirs(new_dir, exist_ok=True)
        extract_safe(file.file_name, new_file, detection.start, detection.stop)
        spectrogram(new_file, detection.common_name, new_file.replace(os.path.expanduser('~/'), ''))
    return new_file


def write_to_db(file: ParseFileName, detection: Detection):
    conf = get_settings()
    # Connect to SQLite Database
    for attempt_number in range(3):
        try:
            con = sqlite3.connect(DB_PATH)
            cur = con.cursor()
            try:
                cur.execute("ALTER TABLE detections ADD COLUMN snr REAL")
            except sqlite3.OperationalError:
                pass
            cur.execute(
                "INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    detection.date,
                    detection.time,
                    detection.scientific_name,
                    detection.common_name,
                    detection.confidence,
                    conf['LATITUDE'],
                    conf['LONGITUDE'],
                    conf['CONFIDENCE'],
                    str(detection.week),
                    conf['SENSITIVITY'],
                    conf['OVERLAP'],
                    os.path.basename(detection.file_name_extr),
                    detection.snr,
                ),
            )
            # (Date, Time, Sci_Name, Com_Name, Confidence,
            #  Lat, Lon, Cutoff, Week, Sens,
            #  Overlap, File_Name, SNR)

            con.commit()
            con.close()
            break
        except BaseException as e:
            log.warning("Database busy: %s", e)
            sleep(2)


def summary(file: ParseFileName, detection: Detection):
    # Date;Time;Sci_Name;Com_Name;Confidence;Lat;Lon;Cutoff;Week;Sens;Overlap;SNR1;SNR2
    # 2023-03-03;12:48:01;Phleocryptes melanops;Wren-like Rushbird;0.76950216;-1;-1;0.7;9;1.25;0.0;12.34;11.11
    conf = get_settings()
    snr1 = f'{detection.snr:.2f}' if detection.snr is not None else ''
    snr2 = f'{detection.snr_quality:.2f}' if detection.snr_quality is not None else ''
    s = (
        f'{detection.date};{detection.time};{detection.scientific_name};{detection.common_name};'
        f'{detection.confidence};'
        f'{conf["LATITUDE"]};{conf["LONGITUDE"]};{conf["CONFIDENCE"]};{detection.week};{conf["SENSITIVITY"]};'
        f'{conf["OVERLAP"]};{snr1};{snr2}'
    )
    return s


def write_to_file(file: ParseFileName, detection: Detection):
    with open(os.path.expanduser('~/BirdNET-Pi/BirdDB.txt'), 'a') as rfile:
        rfile.write(f'{summary(file, detection)}\n')


def update_json_file(file: ParseFileName, detections: [Detection]):
    if file.RTSP_id is None:
        mask = f'{os.path.dirname(file.file_name)}/*.json'
    else:
        mask = f'{os.path.dirname(file.file_name)}/*{file.RTSP_id}*.json'
    for f in glob.glob(mask):
        log.debug(f'deleting {f}')
        os.remove(f)
    write_to_json_file(file, detections)


def write_to_json_file(file: ParseFileName, detections: [Detection]):
    conf = get_settings()
    json_file = f'{file.file_name}.json'
    log.debug(f'WRITING RESULTS TO {json_file}')
    dets = {'file_name': os.path.basename(json_file), 'timestamp': file.iso8601, 'delay': conf['RECORDING_LENGTH'],
            'detections': [{"start": det.start, "common_name": det.common_name, "confidence": det.confidence} for det in
                           detections]}
    with open(json_file, 'w') as rfile:
        rfile.write(json.dumps(dets))
    log.debug(f'DONE! WROTE {len(detections)} RESULTS.')


def apprise(file: ParseFileName, detections: [Detection]):
    species_apprised_this_run = []
    conf = get_settings()

    for detection in detections:
        # Apprise of detection if not already alerted this run.
        if detection.species not in species_apprised_this_run:
            try:
                sendAppriseNotifications(detection.species, str(detection.confidence), str(detection.confidence_pct),
                                         os.path.basename(detection.file_name_extr), detection.date, detection.time, str(detection.week),
                                         conf['LATITUDE'], conf['LONGITUDE'], conf['CONFIDENCE'], conf['SENSITIVITY'],
                                         conf['OVERLAP'], dict(conf), DB_PATH)
            except BaseException as e:
                log.exception('Error during Apprise:', exc_info=e)

            species_apprised_this_run.append(detection.species)


def bird_weather(file: ParseFileName, detections: [Detection]):
    conf = get_settings()
    if conf['BIRDWEATHER_ID'] == "":
        return
    if detections:
        try:
            data, samplerate = soundfile.read(file.file_name)
            buf = io.BytesIO()
            soundfile.write(buf, data, samplerate, format='FLAC')
            flac_data = buf.getvalue()
        except Exception as e:
            log.error("Error during FLAC conversion: %s", e)
            return

        # POST soundscape to server
        soundscape_url = (f'https://app.birdweather.com/api/v1/stations/'
                          f'{conf["BIRDWEATHER_ID"]}/soundscapes?timestamp={file.iso8601}')

        try:
            response = requests.post(url=soundscape_url, data=flac_data, timeout=30,
                                     headers={'Content-Type': 'audio/flac'})
            log.info("Soundscape POST Response Status - %d", response.status_code)
            sdata = response.json()
        except BaseException as e:
            log.error("Cannot POST soundscape: %s", e)
            return
        if not sdata.get('success'):
            log.error(sdata.get('message'))
            return
        soundscape_id = sdata['soundscape']['id']

        for detection in detections:
            # POST detection to server
            detection_url = f'https://app.birdweather.com/api/v1/stations/{conf["BIRDWEATHER_ID"]}/detections'

            data = {'timestamp': detection.iso8601, 'lat': conf['LATITUDE'], 'lon': conf['LONGITUDE'],
                    'soundscapeId': soundscape_id,
                    'soundscapeStartTime': detection.start, 'soundscapeEndTime': detection.stop,
                    'commonName': detection.common_name, 'scientificName': detection.scientific_name,
                    'algorithm': '2p4' if conf['MODEL'] == 'BirdNET_GLOBAL_6K_V2.4_Model_FP16' else 'alpha',
                    'confidence': detection.confidence}

            log.debug(data)
            try:
                response = requests.post(detection_url, json=data, timeout=20)
                log.info("Detection POST Response Status - %d", response.status_code)
            except BaseException as e:
                log.error("Cannot POST detection: %s", e)


def heartbeat():
    conf = get_settings()
    if conf['HEARTBEAT_URL']:
        try:
            result = requests.get(url=conf['HEARTBEAT_URL'], timeout=10)
            log.info('Heartbeat: %s', result.text)
        except BaseException as e:
            log.error('Error during heartbeat: %s', e)
