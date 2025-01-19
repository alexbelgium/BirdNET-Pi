#!/usr/bin/env bash
set -x

source /etc/birdnet/birdnet.conf
used="$(df -h ${EXTRACTED} | tail -n1 | awk '{print $5}')"

if [ "${used//%}" -ge 95 ]; then

  case $FULL_DISK in
    purge) echo "Removing data to stay below threshold"
        max_files_species="1000"
        safe_purge_threshold="$((95 * 9 / 10))"
        while [ "$(df -h "${EXTRACTED}" | tail -n1 | awk '{print $5}' | tr -d '%')" -ge "$safe_purge_threshold" ]; do
            ./disk_species_clean.sh "$max_files_species"
            max_files_species=$((max_files_species * 9 / 10))
        done;;
      
    keep) echo "Stopping Core Services"
       /usr/local/bin/stop_core_services.sh;;
  esac
fi
