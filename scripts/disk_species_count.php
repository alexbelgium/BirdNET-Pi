<?php
require_once "scripts/common.php";
$home = get_home();
$config = get_config();
$user = get_user();
$max_files_species = isset($config['MAX_FILE_SPECIES']) ? $config['MAX_FILE_SPECIES'] : 1000;
$base_dir = realpath("$home/BirdSongs/Extracted/By_Date");
if (!$base_dir || !is_dir($base_dir)) {
    echo "ERROR: BirdSongs directory not found at $base_dir\n";
    exit;
}

// Get bird names from SQLite
$db_path = "$home/BirdNET-Pi/scripts/birds.db";
$bird_names = [];
if (file_exists($db_path)) {
    $db = new SQLite3($db_path, SQLITE3_OPEN_READONLY);
    $results = $db->query("SELECT DISTINCT Com_Name FROM detections;");
    while ($row = $results->fetchArray(SQLITE3_ASSOC)) {
        $bird_names[] = $row['Com_Name'];
    }
    $db->close();
}

// Sanitize names
$sanitized_names = array_filter(array_map(function ($name) {
    return rtrim(preg_replace("/[^A-Za-z0-9_]/", '', str_replace(' ', '_', $name)), '_');
}, $bird_names));

$species_count = count($sanitized_names);
$total_file_count = 0;
$species_summary = [];

foreach ($sanitized_names as $name) {
    $pattern = escapeshellarg("$base_dir/*/$name/*");
    $cmd = "find $pattern -type f -not -iname '*.png' | wc -l";
    $count = (int)trim(shell_exec($cmd));
    $total_file_count += $count;

    $species_summary[] = [
        'name' => str_replace('_', ' ', $name),
        'count' => $count,
        'display' => $count >= 1000 ? number_format($count / 1000, 1) . 'k' : $count
    ];
}

usort($species_summary, fn($a, $b) => $b['count'] <=> $a['count']);

$free_space = shell_exec("df -h " . escapeshellarg($base_dir) . " | awk 'NR==2 {print $4}'");
$disk_size = shell_exec("du -sh " . escapeshellarg($base_dir) . " | cut -f1");
$total_files_display = $total_file_count >= 1000 ? number_format($total_file_count / 1000, 1) . 'k' : $total_file_count;

header("Content-Type: text/plain");

echo "BirdSongs stored on your drive. This number is higher than the MAX_FILE_SPECIES specified ($max_files_species) as files from the last 7 days are protected, as well as files specifically notified in the disk_check_exclude.txt\n";
echo "==============================\n";
echo "Location      : $base_dir\n";
echo "Free space    : $free_space";
echo "Total species : $species_count\n";
echo "Total files   : $total_files_display\n";
echo "Total size    : $disk_size\n";
echo "==============================\n";

foreach ($species_summary as $entry) {
    echo $entry['name'] . " : " . $entry['display'] . "\n";
}
