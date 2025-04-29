#!/usr/bin/env python3

import re
import time
import subprocess
from datetime import datetime, date
from suntime import Sun
from dateutil import tz
from utils.helpers import get_settings
import os

# Configuration
CONFIG_FILE = '/etc/birdnet/birdnet.conf'
RESTART_SCRIPT = os.path.expanduser('~/BirdNET-Pi/scripts/restart_services.sh')
STOP_SCRIPT    = os.path.expanduser('~/BirdNET-Pi/scripts/stop_core_services.sh')

# Helpers

def update_bats_analysis(new_value):
    """Write BATS_ANALYSIS=<new_value> into the config file."""
    with open(CONFIG_FILE, 'r') as f:
        lines = f.readlines()
    with open(CONFIG_FILE, 'w') as f:
        for line in lines:
            if line.startswith('BATS_ANALYSIS='):
                f.write(f'BATS_ANALYSIS={new_value}\n')
            else:
                f.write(line)


def restart_services():
    subprocess.run(["bash", RESTART_SCRIPT], check=True)


def stop_services():
    subprocess.run(["bash", STOP_SCRIPT], check=True)


def is_service_active():
    """Return True if birdnet_analysis service is active."""
    res = subprocess.run(
        ['systemctl', 'is-active', 'birdnet_analysis'],
        capture_output=True, text=True
    )
    return res.stdout.strip() == 'active'


def get_sun_times():
    """Returns (sunrise_str, sunset_str) for today in HH:MM format."""
    conf = get_settings()
    lat = conf.getfloat('LATITUDE')
    lon = conf.getfloat('LONGITUDE')
    sun = Sun(lat, lon)
    local_tz = tz.tzlocal()
    today_dt = datetime.combine(date.today(), datetime.min.time())
    sr = sun.get_sunrise_time(today_dt, local_tz).strftime("%H:%M")
    ss = sun.get_sunset_time(today_dt, local_tz).strftime("%H:%M")
    return sr, ss


def error_and_sleep(msg):
    print(f"[ERROR] {msg}")
    while True:
        time.sleep(3600)


def parse_time_field(field_name, value, sunrise, sunset):
    """
    Parse a config time value:
      - "Sunrise"  -> sunrise
      - "Sunset"   -> sunset
      - "HH:MM"    -> itself
      - otherwise   -> error + sleep
    """
    if value == 'Sunrise':
        return sunrise
    if value == 'Sunset':
        return sunset
    if re.match(r'^\d{2}:\d{2}$', value):
        return value
    error_and_sleep(f"Invalid {field_name}: '{value}' (must be 'Sunrise', 'Sunset' or HH:MM)")


def time_to_minutes(timestr):
    h, m = map(int, timestr.split(':'))
    return h * 60 + m


if __name__ == '__main__':
    conf = get_settings()
    timer_enabled = conf.getint('TIMER', fallback=0)

    # 1) If TIMER is 0, sleep forever
    if timer_enabled == 0:
        print("Timer disabled: sleeping until restart...")
        while True:
            time.sleep(3600)

    # 2) Compute start/stop times
    sunrise, sunset = get_sun_times()
    raw_start = conf.get('TIMER_START', fallback=None)
    raw_stop  = conf.get('TIMER_STOP',  fallback=None)

    start_str = parse_time_field('TIMER_START', raw_start, sunrise, sunset)
    stop_str  = parse_time_field('TIMER_STOP',  raw_stop,  sunrise, sunset)

    # 3) Ensure they differ
    if start_str == stop_str:
        error_and_sleep("TIMER_START and TIMER_STOP cannot be the same.")

    # 4) Read TIMER_SWITCH
    timer_switch = conf.getboolean('TIMER_SWITCH', fallback=False)

    start_min = time_to_minutes(start_str)
    stop_min  = time_to_minutes(stop_str)

    print(f"Timer: start={start_str}, stop={stop_str}, switch={'ON' if timer_switch else 'OFF'}")

    # Main loop
    today = date.today()
    while True:
        now = datetime.now()
        now_min = now.hour * 60 + now.minute

        # Reload sunrise/sunset at midnight
        if now.date() != today:
            sunrise, sunset = get_sun_times()
            today = now.date()
            # re-parse fields
            raw_start = conf.get('TIMER_START', fallback=None)
            raw_stop  = conf.get('TIMER_STOP',  fallback=None)
            start_str = parse_time_field('TIMER_START', raw_start, sunrise, sunset)
            stop_str  = parse_time_field('TIMER_STOP',  raw_stop,  sunrise, sunset)
            start_min = time_to_minutes(start_str)
            stop_min  = time_to_minutes(stop_str)
            print(f"[New day] start={start_str}, stop={stop_str}")

        # Determine if within active window
        if start_min < stop_min:
            in_window = start_min <= now_min < stop_min
        else:
            in_window = now_min >= start_min or now_min < stop_min

        service_active = is_service_active()

        if in_window:
            # should be active
            if not service_active:
                print(f"[{now}] Window start: service inactive -> restarting")
                restart_services()
        else:
            # should be inactive
            if service_active and not timer_switch:
                print(f"[{now}] Window end: service active -> stopping")
                stop_services()

        time.sleep(60)
