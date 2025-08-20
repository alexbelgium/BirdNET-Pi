<?php

/* Prevent XSS input */
$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

require_once __DIR__ . '/common.php';
ensure_authenticated();

$home = get_home();
$db = new SQLite3(__DIR__ . '/birds.db', SQLITE3_OPEN_READWRITE);
$db->busyTimeout(1000);

$base_symlink = $home . '/BirdSongs/Extracted/By_Date';
$base = realpath($base_symlink);

$confirm_file = __DIR__ . '/confirmed_species_list.txt';
$confirmed_species = [];
if (file_exists($confirm_file)) {
    $confirmed_species = file($confirm_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
}

$exclude_file = __DIR__ . '/exclude_species_list.txt';
$excluded_species = [];
if (file_exists($exclude_file)) {
    $excluded_species = file($exclude_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
}

$whitelist_file = __DIR__ . '/whitelist_species_list.txt';
$whitelisted_species = [];
if (file_exists($whitelist_file)) {
    $whitelisted_species = file($whitelist_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
}

$config = get_config();
$sf_thresh = isset($config['SF_THRESH']) ? floatval($config['SF_THRESH']) : 0;

if (isset($_GET['toggle']) && isset($_GET['species']) && isset($_GET['action'])) {
    $list = $_GET['toggle'];
    $species = htmlspecialchars_decode($_GET['species'], ENT_QUOTES);
    $file = ($list === 'exclude') ? $exclude_file : $whitelist_file;
    $lines = file_exists($file) ? file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];
    if ($_GET['action'] === 'add') {
        if (!in_array($species, $lines)) {
            $lines[] = $species;
        }
    } else {
        $lines = array_filter($lines, function($line) use ($species) { return $line !== $species; });
    }
    file_put_contents($file, implode("\n", $lines) . "\n");
    echo 'OK';
    exit;
}

if (isset($_GET['getcounts'])) {
    if ($base === false) {
        http_response_code(500);
        exit(json_encode(['error' => 'Base directory not found']));
    }

    $species = htmlspecialchars_decode($_GET['getcounts'], ENT_QUOTES);
    $stmt = $db->prepare('SELECT Date, Com_Name, Sci_Name, File_Name FROM detections WHERE Com_Name = :name');
    ensure_db_ok($stmt);
    $stmt->bindValue(':name', $species, SQLITE3_TEXT);
    $res = $stmt->execute();
    $count = 0;
    $files = [];
    while ($row = $res->fetchArray(SQLITE3_ASSOC)) {
        $count++;
        $dir = str_replace([' ', "'"], ['_', ''], $row['Com_Name']);
        foreach ([
            $home.'/BirdSongs/Extracted/By_Date/'.$row['Date'].'/'.$dir.'/'.$row['File_Name'],
            $home.'/BirdSongs/Extracted/By_Date/shifted/'.$row['Date'].'/'.$dir.'/'.$row['File_Name'],
        ] as $candidate) {
            $candDir = realpath(dirname($candidate));
            if ($candDir === false) {
                error_log('Missing dir: '.$candidate);
                continue;
            }
            $abs = $candDir . DIRECTORY_SEPARATOR . basename($candidate);
            if (strpos($abs, $base . DIRECTORY_SEPARATOR) === 0) {
                if (is_file($abs)) { $files[$abs] = true; }
            } else {
                error_log('File outside base: '.$abs);
            }
        }
    }
    echo json_encode(['count' => $count, 'files' => count($files)]);
    exit;
}

if (isset($_GET['delete'])) {
    if ($base === false) {
        http_response_code(500);
        exit(json_encode(['error' => 'Base directory not found']));
    }

    $species = htmlspecialchars_decode($_GET['delete'], ENT_QUOTES);
    $stmt = $db->prepare('SELECT Date, Com_Name, Sci_Name, File_Name FROM detections WHERE Com_Name = :name');
    ensure_db_ok($stmt);
    $stmt->bindValue(':name', $species, SQLITE3_TEXT);
    $res = $stmt->execute();
    $files = [];
    $sci_name = null;
    while ($row = $res->fetchArray(SQLITE3_ASSOC)) {
        if (!$sci_name) { $sci_name = $row['Sci_Name']; }
        $dir = str_replace([' ', "'"], ['_', ''], $row['Com_Name']);
        foreach ([
            $home.'/BirdSongs/Extracted/By_Date/'.$row['Date'].'/'.$dir.'/'.$row['File_Name'],
            $home.'/BirdSongs/Extracted/By_Date/shifted/'.$row['Date'].'/'.$dir.'/'.$row['File_Name'],
        ] as $candidate) {
            $candDir = realpath(dirname($candidate));
            if ($candDir === false) {
                error_log('Missing dir: '.$candidate);
                continue;
            }
            $abs = $candDir . DIRECTORY_SEPARATOR . basename($candidate);
            if (strpos($abs, $base . DIRECTORY_SEPARATOR) === 0) {
                $files[$abs] = true;
            } else {
                error_log('File outside base: '.$abs);
            }
        }
    }
    $deleted_files = 0;
    foreach (array_keys($files) as $fp) {
        if (is_file($fp) && @unlink($fp)) {
            $deleted_files++;
            $png = $fp . '.png';
            if (is_file($png)) { @unlink($png); }
        } else {
            if (is_file($fp)) { error_log('Failed to delete file: '.$fp); }
        }
    }
    $del = $db->prepare('DELETE FROM detections WHERE Com_Name = :name');
    ensure_db_ok($del);
    $del->bindValue(':name', $species, SQLITE3_TEXT);
    $del->execute();
    $lines_deleted = $db->changes();
    if (file_exists($confirm_file) && $sci_name !== null) {
        $identifier = str_replace("'", '', $sci_name.'_'.$species);
        $lines = array_filter($confirmed_species, function($line) use ($identifier) {
            return $line !== $identifier;
        });
        file_put_contents($confirm_file, implode("\n", $lines));
    }
    echo json_encode(['lines' => $lines_deleted, 'files' => $deleted_files]);
    exit;
}

$result = fetch_species_array('alphabetical');
?>
<style>
.circle-icon { display:inline-block;width:12px;height:12px;border:1px solid #777;border-radius:50%;cursor:pointer; }
</style>
<div class="centered">
<table id="speciesTable">
  <thead>
    <tr>
      <th onclick="sortTable(0)">Common Name</th>
      <th onclick="sortTable(1)">Scientific Name</th>
      <th onclick="sortTable(2)">Identifications</th>
      <th onclick="sortTable(3)">Excluded</th>
      <th onclick="sortTable(4)">Whitelisted</th>
      <th onclick="sortTable(5)">Threshold</th>
      <th>Delete</th>
    </tr>
  </thead>
  <tbody>
<?php while($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $common = htmlspecialchars($row['Com_Name'], ENT_QUOTES);
    $scient = htmlspecialchars($row['Sci_Name'], ENT_QUOTES);
    $count = $row['Count'];
    $identifier = str_replace("'", '', $row['Sci_Name'].'_'.$row['Com_Name']);

    $is_excluded = in_array($identifier, $excluded_species);
    $is_whitelisted = in_array($identifier, $whitelisted_species);
    $excl_cell = $is_excluded
        ? "<img style='cursor:pointer;max-width:12px;max-height:12px' src='images/check.svg' onclick=\"toggleSpecies('exclude','".str_replace("'", '', $identifier)."','del')\">"
        : "<span class='circle-icon' onclick=\"toggleSpecies('exclude','".str_replace("'", '', $identifier)."','add')\"></span>";

    $white_cell = $is_whitelisted
        ? "<img style='cursor:pointer;max-width:12px;max-height:12px' src='images/check.svg' onclick=\"toggleSpecies('whitelist','".str_replace("'", '', $identifier)."','del')\">"
        : "<span class='circle-icon' onclick=\"toggleSpecies('whitelist','".str_replace("'", '', $identifier)."','add')\"></span>";

    echo "<tr data-comname=\"".$common."\"><td>".$common."</td><td><i>".$scient."</i></td><td>".$count."</td>".
         "<td data-sort='".($is_excluded?1:0)."'>".$excl_cell."</td>".
         "<td data-sort='".($is_whitelisted?1:0)."'>".$white_cell."</td>".
         "<td class='threshold' data-sort='0'>0.0000</td>".
         "<td><img style='cursor:pointer;max-width:20px' src='images/delete.svg' onclick=\"deleteSpecies('".addslashes($row['Com_Name'])."')\"></td></tr>";
} ?>
  </tbody>
</table>
</div>
<script>
const scriptsBase = '../scripts/';
const sfThresh = <?php echo $sf_thresh; ?>;

function loadThresholds() {
  const xhttp = new XMLHttpRequest();
  xhttp.onload = function() {
    const text = this.responseText || '';
    const lines = text.split(/\r?\n/);
    const map = Object.create(null);

    for (const line of lines) {
      // Match "... - 0.1234" anywhere in the line
      const m = line.match(/^(.*)\s-\s([0-9.]+)\s*$/);
      if (!m) continue;

      const left = m[1].trim();          // could be "Sci_Common" or just "Common"
      const val  = parseFloat(m[2]);
      if (isNaN(val)) continue;

      // If there is an underscore, assume "Sci_Common" and take Common part
      const underscoreIdx = left.lastIndexOf('_');
      const common = underscoreIdx >= 0 ? left.slice(underscoreIdx + 1) : left;

      // Store by Common Name (what your table uses)
      map[common] = val;

      // (Optional) also store the raw left side in case some rows ever use it
      map[left] = val;
    }

    // decode entities from data-comname
    const decoder = document.createElement('textarea');
    document.querySelectorAll('#speciesTable tbody tr').forEach(row => {
      decoder.innerHTML = row.getAttribute('data-comname') || '';
      const commonName = decoder.value;
      if (commonName in map) {
        const v = map[commonName];
        const cell = row.querySelector('td.threshold');
        cell.textContent = v.toFixed(4);
        cell.style.color = v >= sfThresh ? 'green' : 'red';
        cell.dataset.sort = v.toFixed(4);
      }
    });
  };
  xhttp.open('GET', scriptsBase + 'config.php?threshold=0', true);
  xhttp.send();
}

document.addEventListener('DOMContentLoaded', loadThresholds);

function toggleSpecies(list, species, action) {
  const xhttp = new XMLHttpRequest();
  xhttp.onload = function() {
    if (this.responseText == 'OK') { location.reload(); }
  };
  xhttp.open('GET', scriptsBase + 'species_tools.php?toggle=' + list + '&species=' + encodeURIComponent(species) + '&action=' + action, true);
  xhttp.send();
}
function deleteSpecies(species) {
  const xhttp = new XMLHttpRequest();
  xhttp.onload = function() {
    const info = JSON.parse(this.responseText);
    if (confirm('Delete ' + info.count + ' detections and ' + info.files + ' files for ' + species + '?')) {
      const xhttp2 = new XMLHttpRequest();
      xhttp2.onload = function() {
        try {
          const res = JSON.parse(this.responseText);
          alert('Deleted ' + res.lines + ' detections and ' + res.files + ' files for ' + species);
        } catch (e) {
          alert('Deletion complete');
        }
        location.reload();
      };
      xhttp2.open('GET', scriptsBase + 'species_tools.php?delete=' + encodeURIComponent(species), true);
      xhttp2.send();
    }
  };
  xhttp.open('GET', scriptsBase + 'species_tools.php?getcounts=' + encodeURIComponent(species), true);
  xhttp.send();
}
function sortTable(n) {
  const table = document.getElementById('speciesTable');
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const asc = table.getAttribute('data-sort-' + n) !== 'asc';
  rows.sort(function(a, b) {
    let x = a.cells[n].dataset.sort ?? a.cells[n].innerText.toLowerCase();
    let y = b.cells[n].dataset.sort ?? b.cells[n].innerText.toLowerCase();
    const nx = parseFloat(x), ny = parseFloat(y);
    if (!isNaN(nx) && !isNaN(ny)) { x = nx; y = ny; }
    if (x < y) return asc ? -1 : 1;
    if (x > y) return asc ? 1 : -1;
    return 0;
  });
  rows.forEach(row => tbody.appendChild(row));
  table.setAttribute('data-sort-' + n, asc ? 'asc' : 'desc');
}
</script>

