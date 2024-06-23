#!/bin/bash
set -x

# KEEP ONLY THE NUMBER OF FILES PER SPECIES DEFINED IN THE OPTIONS

source /etc/birdnet/birdnet.conf
base_dir="$HOME/BirdSongs/Extracted/By_Date"
max_files_species="${MAX_FILES_SPECIES:-1000}"
cd "$base_dir" || true

# If max_files_species is not higher than 1, exit
if [[ "$max_files_species" -lt 1 ]]; then
    exit 0
fi

# Get unique species
bird_names=$(
    sqlite3 "$HOME"/BirdNET-Pi/scripts/birds.db <<EOF
.mode column
.headers off
SELECT DISTINCT Com_Name FROM detections;
.quit
EOF
)

# Sanitize the bird names (remove single quotes and replace spaces with underscores)
sanitized_names="$(echo "$bird_names" | tr ' ' '_' | tr -d "'" | grep '[[:alnum:]]')"
# Remove trailing underscores
sanitized_names=$(echo "$sanitized_names" | sed 's/_*$//')

# Read each line from the variable and echo the species
while read -r species; do
    echo -n "$species"
    species_san="${species/-/=}"
    find */"$species" -type f -name "*[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*.*" \
        -not -name "*.png" \
        -not -name "$(date -d "-7 days" '+%Y-%m-%d')*" \
        -not -name "$(date -d "-6 days" '+%Y-%m-%d')*" \
        -not -name "$(date -d "-5 days" '+%Y-%m-%d')*" \
        -not -name "$(date -d "-4 days" '+%Y-%m-%d')*" \
        -not -name "$(date -d "-3 days" '+%Y-%m-%d')*" \
        -not -name "$(date -d "-2 days" '+%Y-%m-%d')*" \
        -not -name "$(date -d "-1 days" '+%Y-%m-%d')*" \
        -not -name "$(date '+%Y-%m-%d')" |
        grep -vFf "$HOME/BirdNET-Pi/scripts/disk_check_exclude.txt" |
        sed "s|$species|$species_san|g" |
        sort -t'-' -k4,4nr -k5,5n -k1,1nr -k2,2nr -k3,3nr |
        tail -n +"$((max_files_species + 1))" |
        sed "s|$species_san|$species|g" |
        xargs -I {} bash -c 'name={}; sudo rm ".$species/$name" && sudo rm ".$species/$name.png"' && echo " : success" || { exit 1; echo " : failed ($?)"; }
# rm to be changed to touch or echo if you want to test without deletion
done <<<"$sanitized_names"