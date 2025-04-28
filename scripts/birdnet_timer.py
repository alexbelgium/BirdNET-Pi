#!/usr/bin/env python3

import time
import subprocess
from datetime import datetime, date
from suntime import Sun
from dateutil import tz
from utils.helpers import get_settings

CONFIG_FILE    = '/etc/birdnet/birdnet.conf'
RESTART_SCRIPT = '/home/pi/BirdNET-Pi/scripts/restart_services.sh'

def update_analysis_mode(new_mode: str):
    """Write ANALYSIS_MODE=new_mode into the config, leaving all other lines intact."""
    lines = []
    with open(CONFIG_FILE, 'r') as f:
        for line in f:
            if line.startswith('ANALYSIS_MODE='):
                lines.append(f'ANALYSIS_MODE={new_mode}\n')
            else:
                lines.append(line)
    with open(CONFIG_FILE, 'w') as f:
        f.writelines(lines)

def restart_services():
    subprocess.run(["bash", RESTART_SCRIPT], check=True)

def get_today_sunrise_sunset():
    conf = get_settings()
    sun = Sun(conf.getfloat('LATITUDE'), conf.getfloat('LONGITUDE'))
    local_tz = tz.tzlocal()
    midnight = datetime.combine(datetime.now().date(), datetime.min.time())
    sr = sun.get_sunrise_time(midnight, local_tz)
    ss = sun.get_sunset_time(midnight, local_tz)
    return sr.strftime("%H:%M"), ss.strftime("%H:%M")

def time_to_minutes(t: str) -> int:
    h, m = map(int, t.split(':'))
    return h * 60 + m

if __name__ == "__main__":
    conf = get_settings()

    # if TIMER is disabled, sleep indefinitely
    if conf.getint('TIMER', fallback=0) == 0:
        while True:
            time.sleep(3600)

    logic = conf.get('TIMER_LOGIC', fallback='Alternate').lower()

    # default windows for TIMER_START/STOP
    if logic == 'bats':
        default_start, default_stop = "18:00", "06:00"
    else:
        default_start, default_stop = "06:00", "18:00"

    # load and resolve any sunrise/sunset keywords
    timer_start = conf.get('TIMER_START', fallback=default_start)
    timer_end   = conf.get('TIMER_STOP',  fallback=default_stop)
    sunrise, sunset = get_today_sunrise_sunset()

    if timer_start in ("Sunrise", "Sunset"):
        timer_start = sunrise if timer_start == "Sunrise" else sunset
    if timer_end   in ("Sunrise", "Sunset"):
        timer_end   = sunrise if timer_end   == "Sunrise" else sunset

    print(f"TIMER_LOGIC={logic}, window {timer_start} → {timer_end}")

    start_min = time_to_minutes(timer_start)
    stop_min  = time_to_minutes(timer_end)

    # read existing mode (fallback to BirdNET)
    current_mode = conf.get('ANALYSIS_MODE', fallback='BirdNET')
    today_date   = date.today()

    while True:
        now = datetime.now()
        now_min = now.hour * 60 + now.minute

        # after midnight, recompute and reload
        if now.date() != today_date:
            today_date = now.date()
            sunrise, sunset = get_today_sunrise_sunset()
            conf = get_settings()
            timer_start = conf.get('TIMER_START', fallback=default_start)
            timer_end   = conf.get('TIMER_STOP',  fallback=default_stop)
            if timer_start in ("Sunrise", "Sunset"):
                timer_start = sunrise if timer_start == "Sunrise" else sunset
            if timer_end   in ("Sunrise", "Sunset"):
                timer_end   = sunrise if timer_end   == "Sunrise" else sunset
            start_min = time_to_minutes(timer_start)
            stop_min  = time_to_minutes(timer_end)
            print(f"[New day] window now {timer_start} → {timer_end}")

        # determine in‐window
        if start_min < stop_min:
            in_window = start_min <= now_min < stop_min
        else:
            in_window = now_min >= start_min or now_min < stop_min

        # map to the three new mode names
        if logic == 'bats':
            desired_mode = 'BattyBirdNET' if in_window else 'BirdNET'
        elif logic == 'birds':
            desired_mode = 'BirdNET'
        else:  # Alternate
            desired_mode = 'BirdNET' if in_window else 'BattyBirdNET'

        if desired_mode != current_mode:
            print(f"Switching ANALYSIS_MODE → {desired_mode}")
            update_analysis_mode(desired_mode)
            restart_services()
            current_mode = desired_mode

        time.sleep(60)
