<?php

/* Prevent XSS input */
$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

require_once 'scripts/common.php';
set_timezone();

$date = isset($_GET['date']) ? $_GET['date'] : date('Y-m-d');

$db = new SQLite3('./scripts/birds.db', SQLITE3_OPEN_READONLY);
$db->busyTimeout(1000);

$statement = $db->prepare('SELECT Com_Name, CAST(strftime("%H", Time) as INTEGER) AS Hour, COUNT(*) AS Count, MAX(Confidence) AS MaxConf FROM detections WHERE Date == :date GROUP BY Com_Name, Hour');
$statement->bindValue(':date', $date, SQLITE3_TEXT);
ensure_db_ok($statement);
$result = $statement->execute();

$data = [];
while($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $name = $row['Com_Name'];
    $hour = intval($row['Hour']);
    $count = intval($row['Count']);
    $conf = floatval($row['MaxConf']);
    if(!isset($data[$name])) {
        $data[$name] = [
            'name' => $name,
            'max_confidence' => $conf,
            'total' => 0,
            'hours' => array_fill(0, 24, 0)
        ];
    }
    $data[$name]['hours'][$hour] = $count;
    $data[$name]['total'] += $count;
    if($conf > $data[$name]['max_confidence']) {
        $data[$name]['max_confidence'] = $conf;
    }
}

header('Content-Type: application/json');
echo json_encode(['date' => $date, 'species' => array_values($data)]);
