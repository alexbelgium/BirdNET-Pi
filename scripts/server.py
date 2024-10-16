import datetime
import logging
import math
import operator
import os
import time

import librosa
import numpy as np

from utils.helpers import get_settings, Detection
from scipy.signal import butter, sosfilt

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['CUDA_VISIBLE_DEVICES'] = ''

try:
    import tflite_runtime.interpreter as tflite
except BaseException:
    from tensorflow import lite as tflite

log = logging.getLogger(__name__)


userDir = os.path.expanduser('~')
INTERPRETER, M_INTERPRETER, INCLUDE_LIST, EXCLUDE_LIST = (None, None, None, None)
PREDICTED_SPECIES_LIST = []
model, priv_thresh, sf_thresh = (None, None, None)

mdata, mdata_params = (None, None)


def loadModel():

    global INPUT_LAYER_INDEX
    global OUTPUT_LAYER_INDEX
    global MDATA_INPUT_INDEX
    global CLASSES

    log.info('LOADING TF LITE MODEL...')

    # Load TFLite model and allocate tensors.
    # model will either be BirdNET_GLOBAL_6K_V2.4_Model_FP16 (new) or BirdNET_6K_GLOBAL_MODEL (old)
    modelpath = userDir + '/BirdNET-Pi/model/'+model+'.tflite'
    myinterpreter = tflite.Interpreter(model_path=modelpath, num_threads=2)
    myinterpreter.allocate_tensors()

    # Get input and output tensors.
    input_details = myinterpreter.get_input_details()
    output_details = myinterpreter.get_output_details()

    # Get input tensor index
    INPUT_LAYER_INDEX = input_details[0]['index']
    if model == "BirdNET_6K_GLOBAL_MODEL":
        MDATA_INPUT_INDEX = input_details[1]['index']
    OUTPUT_LAYER_INDEX = output_details[0]['index']

    # Load labels
    CLASSES = []
    labelspath = userDir + '/BirdNET-Pi/model/labels.txt'
    with open(labelspath, 'r') as lfile:
        for line in lfile.readlines():
            CLASSES.append(line.replace('\n', ''))

    log.info('LOADING DONE!')

    return myinterpreter


def loadMetaModel():

    global M_INTERPRETER
    global M_INPUT_LAYER_INDEX
    global M_OUTPUT_LAYER_INDEX

    if get_settings().getint('DATA_MODEL_VERSION') == 2:
        data_model = 'BirdNET_GLOBAL_6K_V2.4_MData_Model_V2_FP16.tflite'
    else:
        data_model = 'BirdNET_GLOBAL_6K_V2.4_MData_Model_FP16.tflite'

    # Load TFLite model and allocate tensors.
    M_INTERPRETER = tflite.Interpreter(model_path=os.path.join(userDir, 'BirdNET-Pi/model', data_model))
    M_INTERPRETER.allocate_tensors()

    # Get input and output tensors.
    input_details = M_INTERPRETER.get_input_details()
    output_details = M_INTERPRETER.get_output_details()

    # Get input tensor index
    M_INPUT_LAYER_INDEX = input_details[0]['index']
    M_OUTPUT_LAYER_INDEX = output_details[0]['index']

    log.info("loaded META model")


def predictFilter(lat, lon, week):

    global M_INTERPRETER

    # Does interpreter exist?
    if M_INTERPRETER is None:
        loadMetaModel()

    # Prepare mdata as sample
    sample = np.expand_dims(np.array([lat, lon, week], dtype='float32'), 0)

    # Run inference
    M_INTERPRETER.set_tensor(M_INPUT_LAYER_INDEX, sample)
    M_INTERPRETER.invoke()

    return M_INTERPRETER.get_tensor(M_OUTPUT_LAYER_INDEX)[0]


def explore(lat, lon, week):

    # Make filter prediction
    l_filter = predictFilter(lat, lon, week)

    # Apply threshold
    l_filter = np.where(l_filter >= float(sf_thresh), l_filter, 0)

    # Zip with labels
    l_filter = list(zip(l_filter, CLASSES))

    # Sort by filter value
    l_filter = sorted(l_filter, key=lambda x: x[0], reverse=True)

    return l_filter


def predictSpeciesList(lat, lon, week):

    l_filter = explore(lat, lon, week)
    for s in l_filter:
        if s[0] >= float(sf_thresh):
            # if there's a custom user-made include list, we only want to use the species in that
            if (len(INCLUDE_LIST) == 0):
                PREDICTED_SPECIES_LIST.append(s[1])
    WHITELIST_LIST = loadCustomSpeciesList(os.path.expanduser("~/BirdNET-Pi/whitelist_species_list.txt"))
    for species in WHITELIST_LIST:
        PREDICTED_SPECIES_LIST.append(species)


def loadCustomSpeciesList(path):

    slist = []
    if os.path.isfile(path):
        with open(path, 'r') as csfile:
            for line in csfile.readlines():
                slist.append(line.replace('\r', '').replace('\n', ''))

    return slist


def splitSignal(sig, rate, overlap, seconds=3.0, minlen=1.5):

    # Split signal with overlap
    sig_splits = []
    for i in range(0, len(sig), int((seconds - overlap) * rate)):
        split = sig[i:i + int(seconds * rate)]

        # End of signal?
        if len(split) < int(minlen * rate):
            break

        # Signal chunk too short? Fill with zeros.
        if len(split) < int(rate * seconds):
            temp = np.zeros((int(rate * seconds)))
            temp[:len(split)] = split
            split = temp

        sig_splits.append(split)

    return sig_splits


def readAudioData(path, overlap, sample_rate=48000):

    log.info('READING AUDIO DATA...')

    # Open file with librosa (uses ffmpeg or libav)
    sig, rate = librosa.load(path, sr=sample_rate, mono=True, res_type='kaiser_fast')

    # Split audio into 3-second chunks
    chunks = splitSignal(sig, rate, overlap)

    log.info('READING DONE! READ %d CHUNKS.', len(chunks))

    return chunks


def convertMetadata(m):

    # Convert week to cosine
    if m[2] >= 1 and m[2] <= 48:
        m[2] = math.cos(math.radians(m[2] * 7.5)) + 1
    else:
        m[2] = -1

    # Add binary mask
    mask = np.ones((3,))
    if m[0] == -1 or m[1] == -1:
        mask = np.zeros((3,))
    if m[2] == -1:
        mask[2] = 0.0

    return np.concatenate([m, mask])


def custom_sigmoid(x, sensitivity=1.0):
    return 1 / (1.0 + np.exp(-sensitivity * x))


def predict(sample, sensitivity):
    global INTERPRETER
    # Make a prediction
    INTERPRETER.set_tensor(INPUT_LAYER_INDEX, np.array(sample[0], dtype='float32'))
    if model == "BirdNET_6K_GLOBAL_MODEL":
        INTERPRETER.set_tensor(MDATA_INPUT_INDEX, np.array(sample[1], dtype='float32'))
    INTERPRETER.invoke()
    prediction = INTERPRETER.get_tensor(OUTPUT_LAYER_INDEX)[0]

    # Apply custom sigmoid
    p_sigmoid = custom_sigmoid(prediction, sensitivity)

    # Get label and scores for pooled predictions
    p_labels = dict(zip(CLASSES, p_sigmoid))

    # Sort by score
    p_sorted = sorted(p_labels.items(), key=operator.itemgetter(1), reverse=True)

    human_cutoff = max(10, int(len(p_sorted) * priv_thresh / 100.0))

    log.debug("DATABASE SIZE: %d", len(p_sorted))
    log.debug("HUMAN-CUTOFF AT: %d", human_cutoff)

    for i in range(min(10, len(p_sorted))):
        if p_sorted[i][0] == 'Human_Human':
            with open(userDir + '/BirdNET-Pi/HUMAN.txt', 'a') as rfile:
                rfile.write(str(datetime.datetime.now()) + str(p_sorted[i]) + ' ' + str(human_cutoff) + '\n')

    return p_sorted[:human_cutoff]


def calculate_snr(audio_signal, sample_rate=48000, bands=[(200, 500), (500, 1000), (1000, 8000)], percentile=20):
    # Calculate the SNR by selecting the best frequency band and comparing it against a complementary noise band.
    def bandpass_filter(signal, low_freq, high_freq):
        sos = butter(4, [low_freq, high_freq], btype='bandpass', fs=sample_rate, output='sos')
        return sosfilt(sos, signal)
    def estimate_modulation(signal):
        return np.std(signal) + np.max(np.abs(signal))
    # Normalize the audio signal
    audio_signal = audio_signal / np.max(np.abs(audio_signal))
    # 1. Select the best frequency band based on modulation
    modulation_metrics = {}
    for band in bands:
        filtered_signal = bandpass_filter(audio_signal, band[0], band[1])
        modulation_metrics[band] = estimate_modulation(filtered_signal)
    # Identify the band with the highest modulation
    best_band = max(modulation_metrics, key=modulation_metrics.get)
    # 2. Choose a noise band different from the selected signal band
    remaining_bands = [b for b in bands if b != best_band]
    noise_band = remaining_bands[0] if remaining_bands else bands[-1]  # Fallback to any band if needed
    # 3. Apply bandpass filters to both the selected signal band and the noise band
    filtered_signal = bandpass_filter(audio_signal, best_band[0], best_band[1])
    filtered_noise = bandpass_filter(audio_signal, noise_band[0], noise_band[1])
    # 4. Calculate power of the signal and noise
    signal_power = np.mean(filtered_signal ** 2)
    quiet_threshold = np.percentile(np.abs(filtered_noise), percentile)
    quiet_section_noise = filtered_noise[np.abs(filtered_noise) < quiet_threshold]
    # Use fallback noise power if the quiet section is sparse
    noise_power = np.mean(quiet_section_noise ** 2) if len(quiet_section_noise) > 0 else signal_power * 0.1
    # 5. Compute SNR
    snr = 10 * np.log10(signal_power / noise_power)
    return round(snr, 6)


def analyzeAudioData(chunks, lat, lon, week, sens, overlap,):
    global INTERPRETER

    sensitivity = max(0.5, min(1.0 - (sens - 1.0), 1.5))

    detections = {}
    start = time.time()
    log.info('ANALYZING AUDIO...')

    if model == "BirdNET_GLOBAL_6K_V2.4_Model_FP16":
        if len(PREDICTED_SPECIES_LIST) == 0 or len(INCLUDE_LIST) != 0:
            predictSpeciesList(lat, lon, week)

    mdata = get_metadata(lat, lon, week)

    # Parse every chunk
    pred_start = 0.0
    for c in chunks:

        # Prepare as input signal
        sig = np.expand_dims(c, 0)

        # Make prediction
        p = predict([sig, mdata], sensitivity)
#        print("PPPPP",p)
        HUMAN_DETECTED = False

        # Catch if Human is recognized
        for x in range(len(p)):
            if "Human" in p[x][0]:
                HUMAN_DETECTED = True

        # Save result and timestamp
        pred_end = pred_start + 3.0

        # If human detected set all detections to human to make sure voices are not saved
        if HUMAN_DETECTED is True:
            p = [('Human_Human', 0.0)] * 10

        detections[str(pred_start) + ';' + str(pred_end)] = p

        pred_start = pred_end - overlap

    log.info('DONE! Time %.2f SECONDS', time.time() - start)
    return detections


def get_metadata(lat, lon, week):
    global mdata, mdata_params
    if mdata_params != [lat, lon, week]:
        mdata_params = [lat, lon, week]
        # Convert and prepare metadata
        mdata = convertMetadata(np.array([lat, lon, week]))
        mdata = np.expand_dims(mdata, 0)

    return mdata


def load_global_model():
    global INTERPRETER
    global model, priv_thresh, sf_thresh
    conf = get_settings()
    model = conf['MODEL']
    priv_thresh = conf.getfloat('PRIVACY_THRESHOLD')
    sf_thresh = conf.getfloat('SF_THRESH')
    INTERPRETER = loadModel()


def run_analysis(file):
    global INCLUDE_LIST, EXCLUDE_LIST
    INCLUDE_LIST = loadCustomSpeciesList(os.path.expanduser("~/BirdNET-Pi/include_species_list.txt"))
    EXCLUDE_LIST = loadCustomSpeciesList(os.path.expanduser("~/BirdNET-Pi/exclude_species_list.txt"))

    conf = get_settings()

    # Read audio data & handle errors
    try:
        audio_data = readAudioData(file.file_name, conf.getfloat('OVERLAP'))
    except (NameError, TypeError) as e:
        log.error("Error with the following info: %s", e)
        return []

    # Process audio data and get detections
    raw_detections = analyzeAudioData(audio_data, conf.getfloat('LATITUDE'), conf.getfloat('LONGITUDE'), file.week,
                                      conf.getfloat('SENSITIVITY'), conf.getfloat('OVERLAP'))
    confident_detections = []
    if audio_data:
        global_snr = calculate_snr(np.concatenate(audio_data))
    else:
        global_snr = 0
    for time_slot, entries in raw_detections.items():
        log.info('%s-%s', time_slot, entries[0])
        for entry in entries:
            if entry[1] >= conf.getfloat('CONFIDENCE'):
                if entry[0] not in INCLUDE_LIST and len(INCLUDE_LIST) != 0:
                    log.warning("Excluded as INCLUDE_LIST is active but this species is not in it: %s", entry[0])
                elif entry[0] in EXCLUDE_LIST and len(EXCLUDE_LIST) != 0:
                    log.warning("Excluded as species in EXCLUDE_LIST: %s", entry[0])
                elif entry[0] not in PREDICTED_SPECIES_LIST and len(PREDICTED_SPECIES_LIST) != 0:
                    log.warning("Excluded as below Species Occurrence Frequency Threshold: %s", entry[0])
                else:
                    d = Detection(time_slot.split(';')[0], time_slot.split(';')[1], entry[0], entry[1], global_snr)
                    confident_detections.append(d)
    return confident_detections
