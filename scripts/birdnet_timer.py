#!/usr/bin/env python3

import time
import subprocess
from datetime import datetime, date
from suntime import Sun
from dateutil import tz
from utils.helpers import get_settings

CONFIG_FILE   = '/etc/birdnet/birdnet.conf'
RESTART_SCRIPT = '/home/pi/BirdNET-Pi/scripts/restart_services.sh'

def update_analysis_mode(new_mode: str):
    """Write ANALYSIS_MODE=new_mode into the config, leaving other lines intact."""
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
    subprocess.run(["bash", RESTART_SCRIPT])

def get_today_sunrise_sunset():
    conf = get_settings()
    lat = conf.getfloat('LATITUDE')
    lon = conf.getfloat('LONGITUDE')
    sun = Sun(lat, lon)
    local_tz = tz.tzlocal()

    today_midnight = datetime.combine(datetime.now().date(), datetime.min.time())
    sr = sun.get_sunrise_time(today_midnight, local_tz)
    ss = sun.get_sunset_time (today_midnight, local_tz)
    return sr.strftime("%H:%M"), ss.strftime("%H:%M")

def time_to_minutes(t: str) -> int:
    h, m = map(int, t.split(':'))
    return h * 60 + m

if __name__ == "__main__":
    conf = get_settings()

    # if TIMER is disabled, do nothing forever
    if conf.getint('TIMER', fallback=0) == 0:
        while True:
            time.sleep(3600)

    # read timer logic: "Bats", "Birds" or "Alternate"
    logic = conf.get('TIMER_LOGIC', fallback='Alternate').lower()

    # choose defaults if TIMER_START/STOP not set
    if logic == 'bats':
        default_start, default_stop = "18:00", "06:00"
    else:
        # for "birds" or "alternate", default to daytime window
        default_start, default_stop = "06:00", "18:00"

    # load (or default) start/end and resolve sunrise/sunset
    timer_start = conf.get('TIMER_START', fallback=default_start)
    timer_end   = conf.get('TIMER_STOP',  fallback=default_stop)
    sunrise, sunset = get_today_sunrise_sunset()

    if timer_start in ("Sunrise","Sunset"):
        timer_start = sunrise if timer_start=="Sunrise" else sunset
    if timer_end   in ("Sunrise","Sunset"):
        timer_end   = sunrise if timer_end  =="Sunrise" else sunset

    print(f"TIMER_LOGIC={logic}, window {timer_start} → {timer_end}")

    start_min = time_to_minutes(timer_start)
    stop_min  = time_to_minutes(timer_end)

    # fetch current ANALYSIS_MODE so we know when it flips
    current_mode = conf.get('ANALYSIS_MODE', fallback='Birds')
    today_date   = date.today()

    while True:
        now = datetime.now()
        now_min = now.hour * 60 + now.minute

        # at midnight, recompute sunrise/sunset & reload overrides
        if now.date() != today_date:
            today_date = now.date()
            sunrise, sunset = get_today_sunrise_sunset()
            conf = get_settings()
            timer_start = conf.get('TIMER_START', fallback=default_start)
            timer_end   = conf.get('TIMER_STOP',  fallback=default_stop)
            if timer_start in ("Sunrise","Sunset"):
                timer_start = sunrise if timer_start=="Sunrise" else sunset
            if timer_end   in ("Sunrise","Sunset"):
                timer_end   = sunrise if timer_end  =="Sunrise" else sunset
            start_min = time_to_minutes(timer_start)
            stop_min  = time_to_minutes(timer_end)
            print(f"[New day] window now {timer_start} → {timer_end}")

        # are we inside the “on” window?
        if start_min < stop_min:
            in_window = (start_min <= now_min < stop_min)
        else:
            # window crosses midnight
            in_window = (now_min >= start_min or now_min < stop_min)

        # map (logic, in_window) → desired ANALYSIS_MODE
        if logic == 'bats':
            desired_mode = 'Bats'  if in_window else 'Birds'
        elif logic == 'birds':
            desired_mode = 'Birds'
        else:  # Alternate
            desired_mode = 'Birds' if in_window else 'Bats'

        # if it changed, write and restart
        if desired_mode != current_mode:
            print(f"Switching ANALYSIS_MODE → {desired_mode}")
            update_analysis_mode(desired_mode)
            restart_services()
            current_mode = desired_mode

        time.sleep(60)
