<?php
/* Toggle species confirmation status.
 * POST parameter: sci_name
 * Outputs: 'confirmed' or 'unconfirmed'
 */
$_POST = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);
$sci = isset($_POST['sci_name']) ? trim($_POST['sci_name']) : '';
$file = __DIR__ . '/confirmed_species_list.txt';
$species = [];
if (file_exists($file)) {
    $species = array_map('trim', file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES));
}
$status = 'unconfirmed';
if ($sci !== '') {
    if (in_array($sci, $species)) {
        $species = array_values(array_diff($species, [$sci]));
        $status = 'unconfirmed';
    } else {
        $species[] = $sci;
        $status = 'confirmed';
    }
    file_put_contents($file, implode(PHP_EOL, $species) . (count($species) ? PHP_EOL : ''));
}
echo $status;
?>
