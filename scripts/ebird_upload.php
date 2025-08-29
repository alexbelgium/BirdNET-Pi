<?php
/* Prevent XSS input */
$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

error_reporting(E_ERROR);
ini_set('display_errors',1);
require_once __DIR__ . '/common.php';
require_once __DIR__ . '/ebird.php';
$home = get_home();
$config = get_config();
$log_file = $home . "/BirdNET-Pi/scripts/ebirds_upload_log.txt";

header('Content-Type: text/plain');

ensure_authenticated('You must be authenticated to upload.');

// Return list of already-uploaded files
if(isset($_GET['list'])) {
    if(!file_exists($log_file)) {
        touch($log_file);
    }
    echo file_get_contents($log_file);
    exit;
}

if(!isset($_GET['uploadfile'])) {
    echo 'Missing file';
    exit;
}

$relative = $_GET['uploadfile'];
$full_path = $home . "/BirdSongs/Extracted/By_Date/" . $relative;
if(!file_exists($full_path)) {
    echo 'File not found';
    exit;
}

if(!file_exists($log_file)) {
    touch($log_file);
}
$uploaded = [];
foreach(file($log_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
    [$file, $site, $id] = array_pad(explode('|', $line, 3), 3, '');
    if($site === 'ebird') {
        $uploaded[$file] = $id;
    }
}
if(array_key_exists($relative, $uploaded)) {
    echo 'Already uploaded';
    exit;
}

$db = new SQLite3(__DIR__ . '/birds.db', SQLITE3_OPEN_READONLY);
$db->busyTimeout(1000);
$statement = $db->prepare('SELECT Sci_Name, Date, Time, Lat, Lon FROM detections WHERE File_Name = :file_name LIMIT 1');
ensure_db_ok($statement);
$statement->bindValue(':file_name', basename($relative));
$result = $statement->execute();
$row = $result->fetchArray(SQLITE3_ASSOC);
if(!$row) {
    echo 'Not found';
    exit;
}
$sciname = $row['Sci_Name'];
$date = $row['Date'];
$time = $row['Time'];
$lat = $row['Lat'];
$lon = $row['Lon'];
$db->close();

$token = $config['EBIRD_API_TOKEN'] ?? '';
if($token == '') {
    echo 'Missing token';
    exit;
}

$ch = curl_init('https://ebird.org/media/upload');
$ext = pathinfo($full_path, PATHINFO_EXTENSION);
$mime = $ext === 'wav' ? 'audio/wav' : 'application/octet-stream';
$species_code = $ebirds[$sciname] ?? '';
$post = [
    'species' => $sciname,
    'speciesCode' => $species_code,
    'obsDt' => $date . ' ' . $time,
    'lat' => $lat,
    'lng' => $lon,
    'media' => new CURLFile($full_path, $mime, basename($full_path))
];
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $post);
curl_setopt($ch, CURLOPT_HTTPHEADER, ['X-eBirdApiToken: ' . $token]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
if($response === false || $code >= 400) {
    $error = curl_error($ch);
    curl_close($ch);
    echo 'Upload failed: ' . ($error ? $error : $response);
    exit;
}
curl_close($ch);

$obsUrl = '';
$obsId = '';
$data = json_decode($response, true);
if(is_array($data) && isset($data['url'])) {
    $obsUrl = $data['url'];
} elseif(preg_match('~https://ebird.org/[^"\s]+~', $response, $m)) {
    $obsUrl = $m[0];
}
if($obsUrl === '') {
    echo 'Upload failed: unexpected response';
    exit;
}
if(preg_match('~/(S\d+)~', $obsUrl, $m)) {
    $obsId = $m[1];
}
file_put_contents($log_file, $relative . '|ebird|' . $obsId . "\n", FILE_APPEND);
echo $obsUrl;
?>
