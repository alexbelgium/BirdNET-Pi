<?php

/* Prevent XSS input */
$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

//error_reporting(E_ERROR);
error_reporting(E_ALL);
ini_set('display_errors',1);
require_once 'scripts/common.php';
//$home = get_home();
$config = get_config();
$user = get_user();
$CLIENT_ID = 'birdnet-pi';
$OBS_EMAIL = $config['OBS_EMAIL'];
$OBS_PASS= $config['OBS_PASSWORD'];
$OBS_SITE = $config['OBS_SITE'];
$filename = filter_input(INPUT_GET, 'filename', FILTER_SANITIZE_STRING);
$uuid = filter_input(INPUT_GET, 'uuid', FILTER_SANITIZE_STRING);

// List of functions
//getOBSToken
//getOBSObservation
//getOBSSound
//postOBS
//updateOBS

//function getUUIDFromFile($filename) {
//    $observations_filename = $home."/BirdNET-Pi/scripts/observations_uploaded_list.txt";
//    if (!file_exists($observations_filename) || filesize($observations_filename) == 0) {
//      file_put_contents($observations_filename, "# List of uploaded species to observations and UUID\n");
//    }

//    $file = fopen($observations_filename, 'r'); // replace 'yourfile.txt' with your actual file path
//    while (($line = fgets($file)) !== false) {
//        list($uuid, $file_name) = explode(';', trim($line));
//        if ($file_name == $filename) {
//            fclose($file);
//            return $uuid;
//        }
//    }
//
//    fclose($file);
//    return '';
//}
    
function getOBSToken($filename) {
    global $filename;
    global $OBS_SITE, $CLIENT_ID, $OBS_EMAIL, $OBS_PASS;
    
    $ch = curl_init();
    
    curl_setopt($ch, CURLOPT_URL, 'https://' . $OBS_SITE . '/api/v1/oauth2/token/');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query(array('client_id' => $CLIENT_ID, 'grant_type' => 'password', 'email' => $OBS_EMAIL, 'password' => $OBS_PASS)));

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
    global $filename;
    $db = new SQLite3('./scripts/birds.db', SQLITE3_OPEN_READONLY);
    $db->busyTimeout(5000);
    $statement2 = $db->prepare('SELECT * FROM detections WHERE File_name = :filename ORDER BY Date DESC, Time DESC');
    $statement2->bindValue(':filename', $filename);
    ensure_db_ok($statement2);
    $result2 = $statement2->execute();
    while($results=$result2->fetchArray(SQLITE3_ASSOC))
    {
        //$sciname = $results['Sci_Name'];
        //$comname = $results['Com_Name'];
        //$confidence = $results['Confidence'];
        $filename = $results['File_Name'];
        $date = $results['Date'];
        $time = $results['Time'];
        //$week = $results['Week'];
        $latitude = $results['Lat'];
        $longitude = $results['Lon'];
        //$cutoff = $results['Cutoff'];
        //$sens = $results['Sens'];
        //$overlap = $results['Overlap'];
    }

    // Prepare new observation data
    $OBS_DATA = array(
        'species' => '<replace_with_species>', // needed from observation.org dev
        'date' => $date,
        'time' => $time,
        'point' => "POINT($latitude $longitude)",
        'method' => 'heard'
    );

    return $OBS_DATA;
}

function getObservationSound($OBS_DATA) {
    global $filename;
    if (file_exists($filename)) {
        $file_parts = pathinfo($filename);
    if ($file_parts['extension'] == 'mp3' || $file_parts['extension'] == 'wav') {
        $cfile = new CURLFile($filename, 'audio/mpeg', basename($filename));
        $OBS_DATA['upload_sounds'] = $cfile;
    } else {
        echo '<script type="text/javascript">alert("The file is not a MP3 or WAV file.");</script>';
    }
    } else {
        echo '<script type="text/javascript">alert("The file does not exist.");</script>';
    }
    return $OBS_DATA;
}

function postOBS($OBSTOKEN, $OBS_DATA) {
    global $server;
    $headers = array('Authorization: Bearer ' . $OBSTOKEN);
    $url = "https:" .$server . "/api/v1/observations/create/";
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $OBS_DATA);
    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
        implode("\r\n", $headers),
        "Content-Type: multipart/form-data"
    ));

    $response = curl_exec($ch);

    if($response === false)
        echo 'Error: ' . curl_error($ch);
    else
        echo 'Response: ' . $response;
    // need to write uuid & observation site to file
    curl_close($ch);
}



?>