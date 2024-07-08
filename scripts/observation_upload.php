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

// List of functions
//getOBSToken
//getOBSObservation
//getOBSSound
//postOBS
//updateOBS

$filename = $_GET['filename'];

function getOBSToken() {
    $CLIENT_ID = getenv('CLIENT_ID');
    $MAIL = getenv('MAIL');
    $PASSWORD = getenv('PASSWORD');

    $ch = curl_init();

    curl_setopt($ch, CURLOPT_URL, 'https://observation.org/api/v1/oauth2/token/');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query(array('client_id' => $CLIENT_ID, 'grant_type' => 'password', 'email' => $MAIL, 'password' => $PASSWORD)));

    $headers = array();
    $headers[] = 'Content-Type: application/x-www-form-urlencoded';
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $result = curl_exec($ch);
    if (curl_errno($ch)) {
        echo 'Error:' . curl_error($ch);
    }
    curl_close($ch);

    $result_array = json_decode($result, true);
    $OBS_TOKEN = $result_array['access_token'];

    return $OBS_TOKEN;
}

function getObservationData() {
    $db = new SQLite3('./scripts/birds.db', SQLITE3_OPEN_READONLY);
    $db->busyTimeout(5000);
    $statement2 = $db->prepare("SELECT * FROM detections where File_name == \"$filename\" ORDER BY Date DESC, Time DESC");
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
    $server = "observation.org";

    // Prepare new observation data
    $OBS_DATA = array(
        'species' => '<replace_with_species>', // replace with your species
        'date' => $date,
        'time' => $time,
        'point' => "POINT($latitude $longitude)",
        'method' => 'heard'
    );

    return $OBS_DATA;
}

function getObservationSound() {
    if (file_exists($filename)) {
        $file_parts = pathinfo($filename);
    if ($file_parts['extension'] == 'mp3' || $file_parts['extension'] == 'wav') {
        $cfile = new CURLFile($filename, 'audio/mpeg', basename($filename));
        $OBS_DATA['upload_sounds'] = $cfile;
        return $OBS_DATA;
    } else {
        echo '<script type="text/javascript">alert("The file is not a MP3 or WAV file.");</script>';
    }
    } else {
        echo '<script type="text/javascript">alert("The file does not exist.");</script>';
    }
}

function postOBS {
    $headers = array('Authorization: Bearer ' . getOBSToken());
    $url = "https:" .$server . "/api/v1/observations/create/";
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
        $OBS_HEADERS,
        "Content-Type: multipart/form-data"
    ));

    $response = curl_exec($ch);

    if($response === false)
        echo 'Error: ' . curl_error($ch);
    else
        echo 'Response: ' . $response;
    curl_close($ch);
}

$OBSTOKEN = getOBSToken();
$data = getObservationData();
$data = getObservationSound();
postOBS();

?>
