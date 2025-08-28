import json
import logging
import os
from typing import Iterable

import requests

from .helpers import get_settings

log = logging.getLogger(__name__)

# Path to log already-uploaded audio files
# matches other configuration text files in scripts/
UPLOAD_LOG = os.path.expanduser('~/BirdNET-Pi/scripts/ebirds_upload_log.txt')


def _load_uploaded() -> set:
    """Return a set of audio file paths that were already uploaded."""
    if not os.path.isfile(UPLOAD_LOG):
        # create log file if it doesn't exist
        open(UPLOAD_LOG, 'a').close()
        return set()
    try:
        with open(UPLOAD_LOG, 'r') as handle:
            return {line.strip() for line in handle if line.strip()}
    except Exception as e:  # pragma: no cover - log and start fresh
        log.warning("Could not read upload log: %s", e)
        return set()


def _save_uploaded(uploaded: set) -> None:
    with open(UPLOAD_LOG, 'w') as handle:
        for path in sorted(uploaded):
            handle.write(f"{path}\n")


def _post_to_ebird(audio_file: str, species: str, date: str, time: str, token: str) -> None:
    url = 'https://ebird.org/media/upload'
    files = {'media': open(audio_file, 'rb')}
    data = {'species': species, 'obsDt': f'{date} {time}'}
    headers = {'X-eBirdApiToken': token}
    response = requests.post(url, headers=headers, data=data, files=files, timeout=30)
    response.raise_for_status()


def ebird_upload(file, detections: Iterable) -> None:
    """Upload detections to eBird including their audio clips.

    Each detection is uploaded only once.  Uploaded file paths are stored
    in ``UPLOAD_LOG`` to avoid duplicates.
    """
    conf = get_settings()
    token = conf.get('EBIRD_API_TOKEN', '')
    if not token:
        return

    uploaded = _load_uploaded()
    changed = False

    for det in detections:
        audio_path = det.file_name_extr
        if audio_path in uploaded:
            log.debug('Skipping already uploaded file %s', audio_path)
            continue
        try:
            _post_to_ebird(audio_path, det.scientific_name, det.date, det.time, token)
            uploaded.add(audio_path)
            changed = True
            log.info('Uploaded %s to eBird', audio_path)
        except Exception as e:
            log.error('Failed to upload %s: %s', audio_path, e)

    if changed:
        _save_uploaded(uploaded)
