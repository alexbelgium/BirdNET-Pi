#!/usr/bin/env python3

import re
import time
import subprocess
import os
import logging
import sys
import signal
from datetime import datetime, date
from suntime import Sun
from dateutil import tz
from utils.helpers import get_settings

# Graceful shutdown flag
shutdown = False

# Configure logging
log = logging.getLogger(__name__)

def setup_logging():
    """Set up root logger to output to stdout with a simple format."""
    logger = logging.getLogger()
    formatter = logging.Formatter("[%(name)s][%(levelname)s] %(message)s")
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    global log
    log = logging.getLogger('birdnet_timer')

# Configuration paths
CONFIG_FILE    = '/etc/birdnet/birdnet.conf'
RESTART_SCRIPT = os.path.expanduser('~/BirdNET-Pi/scripts/restart_services.sh')
STOP_SCRIPT    = os.path.expanduser('~/BirdNET-Pi/scripts/stop_core_services.sh')

# Signal handler

def sig_handler(sig_num, frame):
    global shutdown
    log.info('Caught shutdown signal %d', sig_num)
    shutdown = True

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
    """Restart BirdNET services via the configured script."""
    subprocess.run(["bash", RESTART_SCRIPT], check=True)


def stop_services():
    """Stop BirdNET core services via the configured script."""
    subprocess.run(["bash", STOP_SCRIPT], check=True)


def is_service_active():
    """Return True if the birdnet_analysis systemd service is active."""
    res = subprocess.run(
        ['systemctl', 'is-active', 'birdnet_analysis'],
        capture_output=True, text=True
    )
    return res.stdout.strip() == 'active'


def get_sun_times():
    """Return today's sunrise and sunset times as 'HH:MM'."""
    conf = get_settings()
    if 'LATITUDE' not in conf or 'LONGITUDE' not in conf:
        error_and_sleep("Missing LATITUDE or LONGITUDE in configuration.")
    lat = conf.getfloat('LATITUDE')
    lon = conf.getfloat('LONGITUDE')
    sun = Sun(lat, lon)
    local_tz = tz.tzlocal()
    today_dt = datetime.combine(date.today(), datetime.min.time())
    sr = sun.get_sunrise_time(today_dt, local_tz).strftime("%H:%M")
    ss = sun.get_sunset_time(today_dt, local_tz).strftime("%H:%M")
    return sr, ss


def error_and_sleep(msg):
    """Log an error message, then sleep forever."""
    log.error(msg)
    while not shutdown:
        time.sleep(3600)
    sys.exit(1)


def parse_time_field(field_name, value, sunrise, sunset):
    """
    Parse a TIMER_* value into an 'HH:MM' string.
    Accepts 'Sunrise', 'Sunset', or explicit 'HH:MM'.
    Otherwise logs error and sleeps indefinitely.
    """
    if value == 'Sunrise':
        return sunrise
    if value == 'Sunset':
        return sunset
    if isinstance(value, str) and re.match(r'^\d{2}:\d{2}$', value):
        return value
    error_and_sleep(f"Invalid {field_name}: '{value}' (must be 'Sunrise', 'Sunset' or HH:MM)")


def time_to_minutes(timestr):
    """Convert 'HH:MM' to minutes since midnight."""
    h, m = map(int, timestr.split(':'))
    return h * 60 + m


if __name__ == '__main__':
    setup_logging()
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        conf = get_settings()

        # 1) If TIMER is 0, sleep forever
        if not conf.has_option('DEFAULT', 'TIMER'):
            error_and_sleep("Missing TIMER in configuration.")
        timer_enabled = conf.getint('TIMER')
        if timer_enabled == 0:
            log.info("Timer disabled: sleeping until restart...")
            while not shutdown:
                time.sleep(3600)
            sys.exit(0)

        # 2) Compute start/stop times (error if missing)
        if not conf.has_option('DEFAULT', 'TIMER_START') or not conf.has_option('DEFAULT', 'TIMER_STOP'):
            error_and_sleep("Missing TIMER_START or TIMER_STOP in configuration.")
        sunrise, sunset = get_sun_times()
        raw_start = conf.get('TIMER_START')
        raw_stop  = conf.get('TIMER_STOP')

        start_str = parse_time_field('TIMER_START', raw_start, sunrise, sunset)
        stop_str  = parse_time_field('TIMER_STOP',  raw_stop,  sunrise, sunset)

        # 3) Ensure they differ
        if start_str == stop_str:
            error_and_sleep("TIMER_START and TIMER_STOP cannot be the same.")

        # 4) Read TIMER_SWITCH (error if missing)
        if not conf.has_option('DEFAULT', 'TIMER_SWITCH'):
            error_and_sleep("Missing TIMER_SWITCH in configuration.")
        timer_switch = conf.getboolean('TIMER_SWITCH')

        start_min = time_to_minutes(start_str)
        stop_min  = time_to_minutes(stop_str)

        log.info("Timer configured: start=%s, stop=%s, switch=%s",
                 start_str, stop_str, 'ON' if timer_switch else 'OFF')
    except Exception as e:
        log.exception("Initialization error")
        sys.exit(1)

    # Main loop
    today = date.today()
    while not shutdown:
        try:
            now = datetime.now()
            now_min = now.hour * 60 + now.minute

            # Reload sunrise/sunset at midnight
            if now.date() != today:
                sunrise, sunset = get_sun_times()
                today = now.date()
                raw_start = conf.get('TIMER_START')
                raw_stop  = conf.get('TIMER_STOP')
                start_str = parse_time_field('TIMER_START', raw_start, sunrise, sunset)
                stop_str  = parse_time_field('TIMER_STOP', raw_stop,  sunrise, sunset)
                start_min = time_to_minutes(start_str)
                stop_min  = time_to_minutes(stop_str)
                log.info("[New day] start=%s, stop=%s", start_str, stop_str)

            # Determine if within active window
            if start_min < stop_min:
                in_window = start_min <= now_min < stop_min
            else:
                in_window = now_min >= start_min or now_min < stop_min

            service_active = is_service_active()

            if in_window:
                # should be active
                if not service_active:
                    log.info("Window start: service inactive -> restarting")
                    restart_services()
            else:
                # should be inactive
                if service_active and not timer_switch:
                    log.info("Window end: service active -> stopping")
                    stop_services()
        except BaseException:
            log.exception("Unexpected error in main loop")
        time.sleep(60)
