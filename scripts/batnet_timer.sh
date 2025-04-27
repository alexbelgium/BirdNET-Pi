#!/usr/bin/env bash
# BattyBirdNET-Pi: Timer service to switch BATS_ANALYSIS mode

source /etc/birdnet/birdnet.conf

# Default times
if [ "${BATS_ANALYSIS}" == "1" ]; then
    default_start="18:00"
    default_stop="06:00"
else
    default_start="06:00"
    default_stop="18:00"
fi

timer_start="${TIMER_START:-$default_start}"
timer_end="${TIMER_STOP:-$default_stop}"

echo "Timer active: will switch at $timer_start and $timer_end."

# Convert HH:MM to minutes since midnight
time_to_minutes() {
    IFS=: read -r hour minute <<< "$1"
    echo $((10#$hour * 60 + 10#$minute))
}

start_minutes=$(time_to_minutes "$timer_start")
stop_minutes=$(time_to_minutes "$timer_end")

current_mode="$BATS_ANALYSIS"  # Track current mode (1=bats, 0=birds)

# Function to update BATS_ANALYSIS and restart services
switch_mode() {
    new_mode=$1

    echo "Switching BATS_ANALYSIS to $new_mode."

    sudo sed -i "s/^BATS_ANALYSIS=.*/BATS_ANALYSIS=$new_mode/" /etc/birdnet/birdnet.conf

    echo "Restarting BirdNET services..."
    bash "$HOME/BirdNET-Pi/scripts/restart_services.sh"
}

# Main loop
while true; do
    now_minutes=$(date +%H)*60+$(date +%M)
    now_minutes=$(( now_minutes ))

    if [ $start_minutes -lt $stop_minutes ]; then
        # Timer window does NOT cross midnight
        if [ $now_minutes -ge $start_minutes ] && [ $now_minutes -lt $stop_minutes ]; then
            desired_mode=1
        else
            desired_mode=0
        fi
    else
        # Timer window crosses midnight
        if [ $now_minutes -ge $start_minutes ] || [ $now_minutes -lt $stop_minutes ]; then
            desired_mode=1
        else
            desired_mode=0
        fi
    fi

    if [ "$desired_mode" != "$current_mode" ]; then
        switch_mode "$desired_mode"
        current_mode="$desired_mode"
    fi

    sleep 60  # Check once per minute
done
