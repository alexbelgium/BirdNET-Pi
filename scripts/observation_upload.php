<?php

/* Prevent XSS input */
$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

error_reporting(E_ERROR);
ini_set('display_errors',1);
require_once 'scripts/common.php';
$home = get_home();
$config = get_config();
$user = get_user();

$db = new SQLite3('./scripts/birds.db', SQLITE3_OPEN_READONLY);
$db->busyTimeout(1000);

// Open observation file
if(isset($_GET['filename'])){
    $name = $_GET['filename'];
    $statement2 = $db->prepare("SELECT * FROM detections where File_name == \"$name\" ORDER BY Date DESC, Time DESC");
    ensure_db_ok($statement2);
    $result2 = $statement2->execute();
    while($results=$result2->fetchArray(SQLITE3_ASSOC))
    {
        $sciname = $results['Sci_Name'];
        $comname = $results['Com_Name'];
        $confidence = $results['Confidence'];
        $filename = $results['File_Name'];
        $date = $results['Date'];
        $time = $results['Time'];
        $week = $results['Week'];
        $latitude = $results['Lat'];
        $longitude = $results['Lon'];
        $cutoff = $results['Cutoff'];
        $sens = $results['Sens'];
        $overlap = $results['Overlap'];
    }

    // Define variables
    $OBS_UUID = "<replace_with_uuid>"; // replace with your uuid
    $server = "observation.org"

    // Prepare new observation data
    $data = array(
        'species' => '<replace_with_species>', // replace with your species
        'date' => $date,
        'time' => $time,
        'point' => "POINT($latitude $longitude)",
        'method' => 'heard'
    );
    // If audio file exists, add it to upload
    $cfile = new CURLFile($filename, 'audio/mpeg', basename($filename));
    $data['upload_sounds'] = $cfile;
    $oauth_token = "<oauth2 token>"; // replace with your oauth2 token
    // upload observation
    $url = "https:" .$server . "/api/v1/observations/create/";
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
        "Authorization: Bearer " . $oauth_token,
        "Content-Type: multipart/form-data"
    ));

    $response = curl_exec($ch);

    if($response === false)
        echo 'Error: ' . curl_error($ch);
    else
        echo 'Response: ' . $response;
    curl_close($ch);
}
?>
