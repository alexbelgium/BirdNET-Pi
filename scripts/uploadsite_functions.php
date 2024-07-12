<?php

/* Prevent XSS input */
$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

error_reporting(E_ERROR);
ini_set('display_errors', 1);
require_once 'scripts/common.php';
require_once 'functions.php'; // Assuming this file contains the get_home function

$config = get_config();
$home = get_home();
$user = get_user();
$CLIENT_ID = 'birdnet-pi';
$UPLOADSITE_USER = $config['UPLOADSITE_USER'];
$UPLOADSITE_PASS = $config['UPLOADSITE_PASS'];
$UPLOADSITE_SITE = $config['UPLOADSITE_SITE'];
$observationorgsites = ["observation.org", "waarneming.nl", "waarnemingen.be", "observations.be"];

// Get the url corresponding to the already uploaded observation
function getOBSURL($UPLOADSITE_SITE, $UUID) {
    global $observationorgsites;
    if (in_array($UPLOADSITE_SITE, $observationorgsites)) {
        return "https://" . $UPLOADSITE_SITE . "/observation/" . $UUID;
    } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
        return "https://www.inaturalist.org/observations/" . $UUID;
    }
    return null; // Return null if no matching site is found
}

// Fetch the token
function getOBSToken($UPLOADSITE_SITE) {
    global $CLIENT_ID, $UPLOADSITE_USER, $UPLOADSITE_PASS, $observationorgsites;
    if (in_array($UPLOADSITE_SITE, $observationorgsites)) {
        $ch = curl_init();

        curl_setopt($ch, CURLOPT_URL, 'https://' . $UPLOADSITE_SITE . '/api/v1/oauth2/token/');
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query(array('client_id' => $CLIENT_ID, 'grant_type' => 'password', 'email' => $UPLOADSITE_USER, 'password' => $UPLOADSITE_PASS)));

        $headers = array();
        $headers[] = 'Content-Type: application/x-www-form-urlencoded';
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

        $result = curl_exec($ch);
        if (curl_errno($ch)) {
            echo 'Error:' . curl_error($ch);
            curl_close($ch);
            return null;
        }
        curl_close($ch);

        $result_array = json_decode($result, true);
        return $result_array['access_token'];
    }
    return null;
}

// Prepare the observation data
function getObservationData($filename) {
    global $home;
    $db = new SQLite3('./scripts/birds.db', SQLITE3_OPEN_READONLY);
    $db->busyTimeout(5000);
    $statement2 = $db->prepare('SELECT * FROM detections WHERE File_name = :filename ORDER BY Date DESC, Time DESC');
    $statement2->bindValue(':filename', $filename);
    ensure_db_ok($statement2);
    $result2 = $statement2->execute();
    
    // Initialize variables to null
    $comname = $date = $time = $latitude = $longitude = null;
    
    while ($results = $result2->fetchArray(SQLITE3_ASSOC)) {
        $comname = $results['Com_Name'];
        $filename = $results['File_Name'];
        $date = $results['Date'];
        $time = $results['Time'];
        $latitude = $results['Lat'];
        $longitude = $results['Lon'];
    }

    // Check if required data is available
    if (!$date || !$time || !$latitude || !$longitude) {
        echo 'Warning: Required observation data is missing.';
        return null;
    }

    // Prepare new observation data
    $OBS_DATA = array(
        'species' => '<replace_with_species>', // needed from observation.org dev
        'date' => $date,
        'time' => $time,
        'point' => "POINT($latitude $longitude)",
        'method' => 'heard'
    );

    // Add sound if relevant
    $comname = preg_replace('/ /', '_', $comname);
    $filepath = $home . "/BirdSongs/Extracted/By_Date/" . $date . "/" . $comname . "/" . $filename;
    if (file_exists($filepath)) {
        $file_parts = pathinfo($filepath);
        if ($file_parts['extension'] == 'mp3' || $file_parts['extension'] == 'wav') {
            $cfile = new CURLFile($filepath, 'audio/mpeg', basename($filepath));
            $OBS_DATA['upload_sounds'] = $cfile;
        } else {
            echo 'Warning: audio file is not a MP3 or WAV file, it will not be added (' . $filename . ')';
        }
    } else {
        echo 'Warning: audio file does not exist (' . $filepath . ')';
    }

    // Return json value
    return $OBS_DATA;
}

// Post the observation data
function postOBS($UPLOADSITE_SITE, $OBSTOKEN, $OBS_DATA) {
    global $observationorgsites;
    if (in_array($UPLOADSITE_SITE, $observationorgsites)) {
        $headers = array('Authorization: Bearer ' . $OBSTOKEN);
        $url = "https://" . $UPLOADSITE_SITE . "/api/v1/observations/create/";
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $OBS_DATA);
        curl_setopt($ch, CURLOPT_HTTPHEADER, array_merge($headers, array("Content-Type: multipart/form-data")));

        $response = curl_exec($ch);

        if ($response === false)
            echo 'Error: ' . curl_error($ch);
        else
            echo 'Response: ' . $response;
        // need to write uuid & observation site to file
        curl_close($ch);
    }
}

?>
