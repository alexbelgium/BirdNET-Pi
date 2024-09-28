<?php
/* Prevent XSS input */
$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

error_reporting(E_ERROR);
ini_set('display_errors', 1);
require_once(__ROOT__.'/scripts/common.php');

$config = get_config();
$home = get_home();
$user = get_user();
$CLIENT_ID = 'birdnet-pi'; // Ensure this matches your registered application
$UPLOADSITE_USER = $config['UPLOADSITE_USER'];
$UPLOADSITE_PASS = $config['UPLOADSITE_PASS'];
$UPLOADSITE_SITE = $config['UPLOADSITE_SITE'];
$cmd = "cd " . escapeshellarg($home . "/BirdNET-Pi") . " && sudo -u " . escapeshellarg($user) . " git rev-list --max-count=1 HEAD";
$curr_hash = trim(shell_exec($cmd));
$observationorgsites = ["observation.org", "waarneming.nl", "waarnemingen.be", "observations.be"];

// Path to store iNaturalist tokens securely
define('INAT_TOKENS_FILE', __ROOT__.'/tokens.json'); // Path for tokens

// Function to get the URL of the uploaded observation
function getOBSURL($UPLOADSITE_SITE, $UUID) {
    global $observationorgsites;
    if (in_array($UPLOADSITE_SITE, $observationorgsites)) {
        return "https://" . $UPLOADSITE_SITE . "/observation/" . $UUID;
    } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
        return "https://www.inaturalist.org/observations/" . $UUID;
    }
    return null;
}

// Function to fetch the OAuth2 token based on the upload site
function getOBSToken($UPLOADSITE_SITE) {
    global $CLIENT_ID, $UPLOADSITE_USER, $UPLOADSITE_PASS, $observationorgsites, $curr_hash;

    if (in_array($UPLOADSITE_SITE, $observationorgsites)) {
        // Existing authentication for observation.org and related sites
        $ch = curl_init();

        curl_setopt($ch, CURLOPT_URL, 'https://' . $UPLOADSITE_SITE . '/api/v1/oauth2/token/');
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query([
            'client_id'    => $CLIENT_ID,
            'grant_type'   => 'password',
            'email'        => $UPLOADSITE_USER,
            'password'     => $UPLOADSITE_PASS
        ]));

        $headers = [
            'Content-Type: application/x-www-form-urlencoded',
            'User-Agent: BirdNet-Pi/' . $curr_hash
        ];
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

        $result = curl_exec($ch);
        if (curl_errno($ch)) {
            echo 'Error fetching token: ' . curl_error($ch);
            curl_close($ch);
            return null;
        }
        curl_close($ch);

        $result_array = json_decode($result, true);
        if (isset($result_array['access_token'])) {
            return $result_array['access_token'];
        } else {
            echo "Error: Unable to retrieve access token from " . htmlspecialchars($UPLOADSITE_SITE) . ". Response: " . htmlspecialchars($result);
            return null;
        }
    } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
        // Authentication for iNaturalist

        // Load tokens from the tokens file
        if (!file_exists(INAT_TOKENS_FILE)) {
            echo "Error: iNaturalist tokens file not found. Please run oauth_callback.php to authorize the application.\n";
            return null;
        }

        $tokens = json_decode(file_get_contents(INAT_TOKENS_FILE), true);
        if (!$tokens || !isset($tokens['access_token'], $tokens['refresh_token'], $tokens['expires_at'])) {
            echo "Error: Invalid tokens file. Please reauthorize the application.\n";
            return null;
        }

        // Check if access token is expired
        if (time() >= $tokens['expires_at']) {
            // Refresh the access token
            $new_tokens = refreshINAToken($tokens['refresh_token']);
            if (!$new_tokens) {
                echo "Error: Failed to refresh iNaturalist access token.\n";
                return null;
            }
            // Update tokens file
            file_put_contents(INAT_TOKENS_FILE, json_encode($new_tokens));
            return $new_tokens['access_token'];
        }

        return $tokens['access_token'];
    }
    return null;
}

// Function to refresh iNaturalist access token using refresh token
function refreshINAToken($refresh_token) {
    global $CLIENT_ID;

    // Load client secret from config or define it here
    $client_secret = '<YOUR_CLIENT_SECRET>'; // Replace with your client secret

    $token_url = 'https://www.inaturalist.org/oauth/token';
    $params = [
        'client_id'     => $CLIENT_ID,
        'client_secret' => $client_secret,
        'grant_type'    => 'refresh_token',
        'refresh_token' => $refresh_token
    ];

    $ch = curl_init($token_url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($params));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

    $response = curl_exec($ch);
    if (curl_errno($ch)) {
        echo 'Token Refresh Error: ' . curl_error($ch);
        curl_close($ch);
        return null;
    }
    curl_close($ch);

    $token_data = json_decode($response, true);
    if (isset($token_data['access_token'], $token_data['refresh_token'], $token_data['expires_in'])) {
        return [
            'access_token'  => $token_data['access_token'],
            'refresh_token' => $token_data['refresh_token'],
            'expires_at'    => time() + $token_data['expires_in']
        ];
    } else {
        echo "Error: Unable to refresh access token. Response: " . htmlspecialchars($response);
        return null;
    }
}

// Function to fetch species ID based on scientific or common name
function getSpeciesId($UPLOADSITE_SITE, $sciname, $comname) {
    // Define the API URLs based on the upload site
    if (in_array($UPLOADSITE_SITE, ["observation.org", "waarneming.nl", "waarnemingen.be", "observations.be"])) {
        $urlSciname = "https://observation.org/api/v1/species/search/?q=" . urlencode($sciname);
        $urlComname = "https://observation.org/api/v1/species/search/?q=" . urlencode($comname);
    } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
        $urlSciname = "https://api.inaturalist.org/v1/taxa?q=" . urlencode($sciname);
        $urlComname = "https://api.inaturalist.org/v1/taxa?q=" . urlencode($comname);
    } else {
        return "Error: Unsupported upload site.";
    }

    // Function to perform the cURL request
    function performCurlRequest($url) {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        // For iNaturalist, you might need to set specific headers or authentication
        curl_setopt($ch, CURLOPT_HTTPHEADER, ['Accept: application/json']);
        $response = curl_exec($ch);
        if (curl_errno($ch)) {
            echo 'cURL Error: ' . curl_error($ch);
            curl_close($ch);
            return null;
        }
        curl_close($ch);
        return $response;
    }

    // Search by scientific name
    $response = performCurlRequest($urlSciname);
    if ($response === null) return "Error: Failed to fetch species by scientific name.";
    $data = json_decode($response, true);

    // Check if the response contains data and has exactly one match
    if (in_array($UPLOADSITE_SITE, ["observation.org", "waarneming.nl", "waarnemingen.be", "observations.be"])) {
        if (!empty($data) && isset($data['results']) && count($data['results']) === 1) {
            return $data['results'][0]['id'];
        }
    } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
        if (!empty($data) && isset($data['results']) && count($data['results']) === 1) {
            return $data['results'][0]['id'];
        }
    }

    // If no unique match found, try searching by common name
    $response = performCurlRequest($urlComname);
    if ($response === null) return "Error: Failed to fetch species by common name.";
    $data = json_decode($response, true);

    if (in_array($UPLOADSITE_SITE, ["observation.org", "waarneming.nl", "waarnemingen.be", "observations.be"])) {
        if (!empty($data) && isset($data['results']) && count($data['results']) === 1) {
            return $data['results'][0]['id'];
        }
    } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
        if (!empty($data) && isset($data['results']) && count($data['results']) === 1) {
            return $data['results'][0]['id'];
        }
    }

    // Return an error message if no unique match found in either search
    return "Error: No unique match found for either scientific name or common name.";
}

// Prepare the observation data
function getObservationData($UPLOADSITE_SITE, $filename) {
    global $home;
    $db = new SQLite3($home . '/scripts/birds.db', SQLITE3_OPEN_READONLY);
    $db->busyTimeout(5000);
    $statement2 = $db->prepare('SELECT * FROM detections WHERE File_name = :filename ORDER BY Date DESC, Time DESC');
    $statement2->bindValue(':filename', $filename, SQLITE3_TEXT);
    ensure_db_ok($statement2);
    $result2 = $statement2->execute();

    // Initialize variables
    $comname = $date = $time = $latitude = $longitude = null;

    while ($results = $result2->fetchArray(SQLITE3_ASSOC)) {
        $comname = $results['Com_Name'];
        $sciname = $results['Sci_Name'];
        $filename_db = $results['File_Name']; // To avoid confusion with function parameter
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

    // Get species ID
    $OBS_ID = getSpeciesId($UPLOADSITE_SITE, $sciname, $comname);
    if (strpos($OBS_ID, "Error:") === 0) {
        echo "Error: Cannot fetch Species ID with message: " . htmlspecialchars($OBS_ID);
        return null;
    }

    // Prepare observation data based on the upload site
    if (in_array($UPLOADSITE_SITE, ["observation.org", "waarneming.nl", "waarnemingen.be", "observations.be"])) {
        $OBS_DATA = [
            'species'               => $OBS_ID,
            'date'                  => $date, // Format: YYYY-MM-DD
            'time'                  => $time, // Format: HH:MM:SS
            'point'                 => "POINT($latitude $longitude)",
            'external_reference'    => $filename_db,
            'method'                => 'heard'
        ];
    } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
        $OBS_DATA = [
            'observation[species_guess]'    => $sciname,
            'observation[observed_on]'      => $date,       // Format: YYYY-MM-DD
            'observation[time_observed_at]' => $time,       // Format: HH:MM:SS (24-hour)
            'observation[latitude]'         => $latitude,
            'observation[longitude]'        => $longitude,
            'observation[description]'      => 'Confidence: ' . $results['Confidence'],
            'observation[place_guess]'      => 'Your Place Guess', // Optional: Modify as needed
            'observation[method]'           => 'heard'            // As per original script
        ];
    } else {
        echo "Error: Unsupported upload site.";
        return null;
    }

    // Add sound if relevant
    $comname_sanitized = preg_replace('/\s+/', '_', $comname);
    $filepath = $home . "/BirdSongs/Extracted/By_Date/" . $date . "/" . $comname_sanitized . "/" . $filename;

    if (file_exists($filepath)) {
        $file_parts = pathinfo($filepath);
        $extension = strtolower($file_parts['extension']);
        if (in_array($extension, ['mp3', 'wav'])) {
            $mime_type = ($extension === 'mp3') ? 'audio/mpeg' : 'audio/wav';
            $cfile = new CURLFile($filepath, $mime_type, basename($filepath));

            if (in_array($UPLOADSITE_SITE, ["observation.org", "waarneming.nl", "waarnemingen.be", "observations.be"])) {
                $OBS_DATA['upload_sounds'] = $cfile;
            } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
                $OBS_DATA['observation[sound_files][]'] = $cfile;
            }
        } else {
            echo 'Warning: Audio file is not a MP3 or WAV file, it will not be added (' . htmlspecialchars($filename) . ').';
        }
    } else {
        echo 'Warning: Audio file does not exist (' . htmlspecialchars($filepath) . ').';
    }

    return $OBS_DATA;
}

// Function to save the uploaded observation details to a local file
function postfile($OBS_ID, $UPLOADSITE_SITE, $filename) {
    global $home;
    $file_path = $home . '/BirdNET-Pi/scripts/uploaded_observations_list.txt';

    // Check if the file exists; if not, create it with headers
    if (!file_exists($file_path)) {
        $header = "uuid;uploadsite;filename\n";
        $result = file_put_contents($file_path, $header);
        if ($result === false) {
            echo "Failed to create or write to file: " . htmlspecialchars($file_path) . ".";
            return false;
        }
    }

    // Check if the filename already exists in the file
    $existing_content = file_get_contents($file_path);
    if (strpos($existing_content, $filename) !== false) {
        echo "File '" . htmlspecialchars($filename) . "' already exists in the list.\n";
        return true; // No need to add duplicate content
    }

    // Verify that all fields have data
    if (empty($OBS_ID) || empty($UPLOADSITE_SITE) || empty($filename)) {
        echo "Invalid data: OBS_ID, UPLOADSITE_SITE, or filename is empty.\n";
        return false;
    }

    // Append the new data
    $data = "$OBS_ID;$UPLOADSITE_SITE;$filename\n";
    $result = file_put_contents($file_path, $data, FILE_APPEND);
    if ($result === false) {
        echo "Failed to append data to file: " . htmlspecialchars($file_path) . ".";
        return false;
    }

    return true;
}

// Function to fetch and sync existing observations from the upload site
function getOBSUploaded($UPLOADSITE_SITE, $UPLOADSITE_USER) {
    global $CLIENT_ID, $observationorgsites, $home;

    // Check if both input variables are provided
    if (empty($UPLOADSITE_SITE) || empty($UPLOADSITE_USER)) {
        echo "Error: Both UPLOADSITE_SITE and UPLOADSITE_USER must be specified. Have you clicked on the save button in the settings?\n";
        return;
    }

    if (in_array($UPLOADSITE_SITE, $observationorgsites)) {
        $url = "https://$UPLOADSITE_SITE/api/v1/user/$UPLOADSITE_USER/observations/";
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        // Add authentication if required
        // Example: curl_setopt($ch, CURLOPT_HTTPHEADER, ['Authorization: Bearer ' . $your_token]);
        $output = curl_exec($ch);
        if (curl_errno($ch)) {
            echo "cURL Error: " . curl_error($ch) . "\n";
            curl_close($ch);
            return;
        }
        curl_close($ch);
        $data = json_decode($output, true);

        if (isset($data['results']) && is_array($data['results'])) {
            foreach ($data['results'] as $observation) {
                if (isset($observation['external_reference']) && !empty($observation['external_reference'])) {
                    if (strpos($observation['external_reference'], 'birdnet') !== false) {
                        postfile($observation['id'], $UPLOADSITE_SITE, $observation['external_reference']);
                    }
                }
            }
            echo "All observations in $UPLOADSITE_SITE were synced to the local database.\n";
        } else {
            echo "No uploaded observations found in $UPLOADSITE_SITE for user $UPLOADSITE_USER.\n";
        }
    } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
        // Fetch observations from iNaturalist
        $url = "https://api.inaturalist.org/v1/observations?user_id=" . urlencode($UPLOADSITE_USER);
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        // Add authentication if required
        $OBSTOKEN = getOBSToken($UPLOADSITE_SITE);
        if ($OBSTOKEN) {
            curl_setopt($ch, CURLOPT_HTTPHEADER, ['Authorization: Bearer ' . $OBSTOKEN]);
        }
        $output = curl_exec($ch);
        if (curl_errno($ch)) {
            echo "cURL Error: " . curl_error($ch) . "\n";
            curl_close($ch);
            return;
        }
        curl_close($ch);
        $data = json_decode($output, true);

        if (isset($data['results']) && is_array($data['results'])) {
            foreach ($data['results'] as $observation) {
                if (isset($observation['external_reference']) && !empty($observation['external_reference'])) {
                    if (strpos($observation['external_reference'], 'birdnet') !== false) {
                        postfile($observation['id'], $UPLOADSITE_SITE, $observation['external_reference']);
                    }
                }
            }
            echo "All observations in $UPLOADSITE_SITE were synced to the local database.\n";
        } else {
            echo "No uploaded observations found in $UPLOADSITE_SITE for user $UPLOADSITE_USER.\n";
        }
    } else {
        echo "Invalid site: $UPLOADSITE_SITE\n";
    }
}

// Function to post the observation data to the appropriate upload site
function postOBS($UPLOADSITE_SITE, $OBSTOKEN, $filename, $uploadnotes) {
    global $observationorgsites, $version, $home;

    // Fetch observation data
    $OBS_DATA = getObservationData($UPLOADSITE_SITE, $filename);

    // Check if OBS_DATA is not empty or null
    if (!$OBS_DATA) {
        echo 'Error: Observation data is missing or invalid.';
        return;
    }

    // Append notes if provided
    if (!empty($uploadnotes)) {
        if (in_array($UPLOADSITE_SITE, ["observation.org", "waarneming.nl", "waarnemingen.be", "observations.be"])) {
            $OBS_DATA['notes'] = $uploadnotes;
        } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
            $OBS_DATA['observation[description]'] = $uploadnotes;
        }
    }

    // Initialize cURL
    $ch = curl_init();

    if (in_array($UPLOADSITE_SITE, $observationorgsites)) {
        // Prepare headers for observation.org and related sites
        $headers = [
            'Authorization: Bearer ' . $OBSTOKEN,
            'User-Agent: BirdNet-Pi/' . $version
            // Note: Do NOT set the Content-Type header manually when uploading files
        ];
        $url = "https://" . $UPLOADSITE_SITE . "/api/v1/observations/create/";

        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $OBS_DATA);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
        // Prepare headers for iNaturalist
        $headers = [
            'Authorization: Bearer ' . $OBSTOKEN,
            'User-Agent: BirdNet-Pi/' . $version
            // Note: Do NOT set the Content-Type header manually when uploading files
        ];
        $url = "https://api.inaturalist.org/v1/observations";

        // iNaturalist expects observation data within an 'observation' key
        // Already handled in getObservationData by prefixing keys with 'observation[...]'

        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $OBS_DATA);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    } else {
        echo "Error: Unsupported upload site.";
        return;
    }

    // Execute cURL request
    $response = curl_exec($ch);
    $http_status = curl_getinfo($ch, CURLINFO_HTTP_CODE);

    // Check for errors
    if ($response === false) {
        echo 'cURL Error: ' . curl_error($ch);
    } else {
        // Decode the JSON response
        $json_response = json_decode($response, true);

        if (in_array($UPLOADSITE_SITE, $observationorgsites)) {
            // Handle response for observation.org and related sites
            if ($http_status == 201 || $http_status == 200) {
                $permalink = isset($json_response['permalink']) ? $json_response['permalink'] : 'N/A';
                echo 'OK : upload successful to ' . htmlspecialchars($permalink) . "\n";

                // Extract ID if available
                $OBS_ID = isset($json_response['id']) ? $json_response['id'] : null;
                if ($OBS_ID) {
                    // Save to file
                    $posted = postfile($OBS_ID, $UPLOADSITE_SITE, $filename);
                    if ($posted) {
                        echo "Data posted successfully.\n";
                    } else {
                        echo "Failed to post data to local file.\n";
                    }
                }
            } else {
                $error_message = isset($json_response['error']) ? $json_response['error'] : 'Unknown error';
                echo 'Error: ' . htmlspecialchars($http_status) . ' - ' . htmlspecialchars($error_message) . "\n";
            }
        } elseif ($UPLOADSITE_SITE == "inaturalist.org") {
            // Handle response for iNaturalist
            if ($http_status == 200 || $http_status == 201) {
                if (isset($json_response['results'][0])) {
                    $observation = $json_response['results'][0];
                    $permalink = isset($observation['uri']) ? $observation['uri'] : 'N/A';
                    echo 'OK : upload successful to ' . htmlspecialchars($permalink) . "\n";

                    // Extract ID if available
                    $OBS_ID = isset($observation['id']) ? $observation['id'] : null;
                    if ($OBS_ID) {
                        // Save to file
                        $posted = postfile($OBS_ID, $UPLOADSITE_SITE, $filename);
                        if ($posted) {
                            echo "Data posted successfully.\n";
                        } else {
                            echo "Failed to post data to local file.\n";
                        }
                    }
                } else {
                    echo 'Error: Unexpected API response: ' . htmlspecialchars($response) . "\n";
                }
            } else {
                $error_message = isset($json_response['error']) ? $json_response['error'] : 'Unknown error';
                echo 'Error: ' . htmlspecialchars($http_status) . ' - ' . htmlspecialchars($error_message) . "\n";
            }
        }
    }

    // Close cURL
    curl_close($ch);
}

// Example usage:
// Assuming you have a filename to upload and upload notes
/*
$filename = 'example.mp3'; // Replace with the actual filename
$uploadnotes = 'This is an example observation.'; // Replace with actual notes if any

$OBSTOKEN = getOBSToken($UPLOADSITE_SITE);
if ($OBSTOKEN) {
    postOBS($UPLOADSITE_SITE, $OBSTOKEN, $filename, $uploadnotes);
} else {
    echo "Error: Unable to obtain OAuth token.";
}
*/

// Additional Functions
// You may need to implement or include the following functions based on your original script:
// - ensure_db_ok(): To handle database errors
// - get_com_en_name(): To retrieve the English common name based on the scientific name
// Ensure these functions are defined in your 'scripts/common.php' or elsewhere.

?>
