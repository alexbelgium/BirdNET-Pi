<?php
/* Prevent XSS input */
$_GET  = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

require_once 'scripts/common.php';
$home   = get_home();
$config = get_config();

// Connect to database
$db = new SQLite3('./scripts/birds.db', SQLITE3_OPEN_READONLY);
$db->busyTimeout(1000);

if(isset($_GET['filename'])) {
    $name = $_GET['filename'];
    $fileBase = basename($name);

    $statement = $db->prepare('SELECT * FROM detections WHERE File_name == :file LIMIT 1');
    ensure_db_ok($statement);
    $statement->bindValue(':file', $fileBase, SQLITE3_TEXT);
    $result = $statement->execute();
    $details = $result->fetchArray(SQLITE3_ASSOC);

    if($details) {
        $date = $details['Date'];
        $time = $details['Time'];
        $lat  = $details['Lat'];
        $lon  = $details['Lon'];
        $species = $details['Com_Name'];

        $query = http_build_query([
            'species' => $species,
            'date'    => $date,
            'time'    => $time,
            'lat'     => $lat,
            'lon'     => $lon
        ]);
        $obsUrl = 'https://observation.org/observation/create?' . $query;
        $audioPath = '../BirdSongs/Extracted/By_Date/' . $name;
    } else {
        $obsUrl = '';
        $audioPath = '';
    }
}
?>
<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<title>Upload observation</title>
</head>
<body>
<script>
window.onload = function() {
<?php if(!empty($obsUrl)): ?>
  window.open('<?php echo $obsUrl; ?>', '_blank');
  var link = document.createElement('a');
  link.href = '<?php echo $audioPath; ?>';
  link.download = '<?php echo basename($name ?? 'audio.mp3'); ?>';
  document.body.appendChild(link);
  link.click();
<?php endif; ?>
};
</script>
<p>Preparing observation...</p>
</body>
</html>
