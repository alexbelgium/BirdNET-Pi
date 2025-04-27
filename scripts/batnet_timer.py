#!/usr/bin/env python3

import time
import subprocess
from datetime import datetime, date
from sun import Sun
from dateutil import tz
from utils.helpers import get_settings

CONFIG_FILE = '/etc/birdnet/birdnet.conf'
RESTART_SCRIPT = '/home/pi/BirdNET-Pi/scripts/restart_services.sh'

def update_bats_analysis(new_value):
    with open(CONFIG_FILE, 'r') as f:
        lines = f.readlines()
    with open(CONFIG_FILE, 'w') as f:
        for line in lines:
            if line.startswith('BATS_ANALYSIS='):
                f.write(f'BATS_ANALYSIS={new_value}\n')
            else:
                f.write(line)

def restart_services():
    subprocess.run(["bash", RESTART_SCRIPT])

def get_today_sunrise_sunset():
    conf = get_settings()
    latitude = conf.getfloat('LATITUDE')
    longitude = conf.getfloat('LONGITUDE')

    sun = Sun(latitude, longitude)
    local_timezone = tz.tzlocal()
    today = datetime.now().date()
    current_datetime = datetime.combine(today, datetime.min.time())

    sunrise_dt = sun.get_sunrise_time(current_datetime, local_timezone)
    sunset_dt = sun.get_sunset_time(current_datetime, local_timezone)

    sunrise_time = sunrise_dt.strftime("%H:%M")
    sunset_time = sunset_dt.strftime("%H:%M")
    return sunrise_time, sunset_time

def time_to_minutes(timestr):
    h, m = map(int, timestr.split(':'))
    return h * 60 + m

if __name__ == "__main__":
    conf = get_settings()

    if conf.getint('TIMER', fallback=0) == 0:
        while True:
            time.sleep(3600)

    bats_analysis = conf.getint('BATS_ANALYSIS', fallback=0)
    default_start = "18:00" if bats_analysis == 1 else "06:00"
    default_stop = "06:00" if bats_analysis == 1 else "18:00"

    timer_start = conf.get('TIMER_START', fallback=default_start)
    timer_end = conf.get('TIMER_STOP', fallback=default_stop)

    sunrise, sunset = get_today_sunrise_sunset()
    today = date.today()

    if timer_start == "Sunrise":
        timer_start = sunrise
    elif timer_start == "Sunset":
        timer_start = sunset

    if timer_end == "Sunrise":
        timer_end = sunrise
    elif timer_end == "Sunset":
        timer_end = sunset

    print(f"Timer active: will switch at {timer_start} and {timer_end}.")

    start_minutes = time_to_minutes(timer_start)
    stop_minutes = time_to_minutes(timer_end)
    current_mode = bats_analysis

    while True:
        now = datetime.now()
        now_minutes = now.hour * 60 + now.minute

        # Reload sunrise/sunset after midnight
        if now.date() != today:
            sunrise, sunset = get_today_sunrise_sunset()
            today = now.date()

            conf = get_settings()
            timer_start = conf.get('TIMER_START', fallback=default_start)
            timer_end = conf.get('TIMER_STOP', fallback=default_stop)

            if timer_start == "Sunrise":
                timer_start = sunrise
            elif timer_start == "Sunset":
                timer_start = sunset

            if timer_end == "Sunrise":
                timer_end = sunrise
            elif timer_end == "Sunset":
                timer_end = sunset

            start_minutes = time_to_minutes(timer_start)
            stop_minutes = time_to_minutes(timer_end)

            print(f"[New day] Updated times: start at {timer_start}, end at {timer_end}")

        if start_minutes < stop_minutes:
            # Timer window does NOT cross midnight
            desired_mode = 1 if (start_minutes <= now_minutes < stop_minutes) else 0
        else:
            # Timer window crosses midnight
            desired_mode = 1 if (now_minutes >= start_minutes or now_minutes < stop_minutes) else 0

        if desired_mode != current_mode:
            print(f"Switching BATS_ANALYSIS to {desired_mode}")
            update_bats_analysis(desired_mode)
            restart_services()
            current_mode = desired_mode

        time.sleep(60)
