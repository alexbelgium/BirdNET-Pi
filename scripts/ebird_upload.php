<?php
/* Prevent XSS input */
$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

error_reporting(E_ERROR);
ini_set('display_errors',1);
require_once 'scripts/common.php';
$home = get_home();
$config = get_config();

ensure_authenticated('You must be authenticated to upload.');

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

$log_file = $home . "/BirdNET-Pi/scripts/ebirds_upload_log.txt";
if(!file_exists($log_file)) {
    touch($log_file);
}
$uploaded = file($log_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
if(in_array($relative, $uploaded)) {
    echo 'Already uploaded';
    exit;
}

$db = new SQLite3('./scripts/birds.db', SQLITE3_OPEN_READONLY);
$db->busyTimeout(1000);
$statement = $db->prepare('SELECT Sci_Name, Date, Time FROM detections WHERE File_Name = :file_name LIMIT 1');
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
$db->close();

$token = $config['EBIRD_API_TOKEN'] ?? '';
if($token == '') {
    echo 'Missing token';
    exit;
}

$ch = curl_init('https://ebird.org/media/upload');
$ext = pathinfo($full_path, PATHINFO_EXTENSION);
$mime = $ext === 'wav' ? 'audio/wav' : 'application/octet-stream';
$post = [
    'species' => $sciname,
    'obsDt' => $date . ' ' . $time,
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

file_put_contents($log_file, $relative . "\n", FILE_APPEND);
echo 'OK';
?>
