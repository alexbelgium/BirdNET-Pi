#!/bin/bash

source /etc/birdnet/birdnet.conf
base_dir="$HOME/BirdSongs/Extracted/By_Date"
cd "$base_dir" || exit 1

MAX_FILE_SPECIES="${MAX_FILE_SPECIES:-1000}"

# Get bird names from the database
bird_names=$(sqlite3 -readonly "$HOME"/BirdNET-Pi/scripts/birds.db <<EOF
.headers off
.mode list
SELECT DISTINCT Com_Name FROM detections;
EOF
)

# Sanitize names
sanitized_names="$(echo "$bird_names" | tr ' ' '_' | tr -d "'" | grep '[[:alnum:]]')"
sanitized_names=$(echo "$sanitized_names" | sed 's/_*$//')

# Handle date format
dateformat=""
if date -d "-7 days" '+%Y-%m-%d' >/dev/null 2>&1; then
    dateformat=" days"
fi

# Count species
species_count=$(echo "$sanitized_names" | wc -l)
current=0
total_file_count=0

# Temp files
data_file=$(mktemp)
output_file=$(mktemp)

# Loop and compute
while read -r species; do
    current=$((current + 1))

    # Progress bar
    percent=$((current * 100 / species_count))
    bar_width=30
    filled=$((percent * bar_width / 100))
    unfilled=$((bar_width - filled))
    bar=$(printf "%0.s#" $(seq 1 $filled))
    space=$(printf "%0.s " $(seq 1 $unfilled))
    printf "\rProcessing: [%-${bar_width}s] %3d%%" "$bar$space" "$percent"

    # Count total files
    total=$(find */"$species" -type f -name "*[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*.*" \
        -not -iname "*.png" | wc -l)
    total_file_count=$((total_file_count + total))

    # Format count to "X.Xk" if over 1000
    if [ "$total" -ge 1000 ]; then
        total_display=$(awk "BEGIN { printf \"%.1fk\", $total/1000 }")
    else
        total_display="$total"
    fi

    # Count protected files
    protected=$(find */"$species" -type f -name "*[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*.*" \
        -not -iname "*.png" \
        -not -iname "*$(date -d "-7$dateformat" '+%Y-%m-%d')*" \
        -not -iname "*$(date -d "-6$dateformat" '+%Y-%m-%d')*" \
        -not -iname "*$(date -d "-5$dateformat" '+%Y-%m-%d')*" \
        -not -iname "*$(date -d "-4$dateformat" '+%Y-%m-%d')*" \
        -not -iname "*$(date -d "-3$dateformat" '+%Y-%m-%d')*" \
        -not -iname "*$(date -d "-2$dateformat" '+%Y-%m-%d')*" \
        -not -iname "*$(date -d "-1$dateformat" '+%Y-%m-%d')*" \
        -not -iname "*$(date '+%Y-%m-%d')*" \
        | grep -vFf "$HOME/BirdNET-Pi/scripts/disk_check_exclude.txt" | wc -l)

    # Save padded sort key + display line
    printf "%05d %s : %s files (%d protected)\n" "$total" "$species" "$total_display" "$protected" >> "$data_file"
done <<<"$sanitized_names"

# Final newline after progress
echo

# Build final output
{
    echo "================================================"
    echo "Distribution of BirdSongs stored on your drive"
    echo "================================================"
    echo "Total number of species : $species_count"
    echo "Total number of files   : $total_file_count"
    echo "Total size used         : $(du -sh . | cut -f1)"
    echo "================================================"
    sort -r "$data_file" | sed 's/^[0-9]* //'
    echo "================================================"
} > "$output_file"

clear
cat "$output_file"

rm -f "$data_file" "$output_file"
