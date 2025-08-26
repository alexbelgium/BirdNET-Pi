<?php
/* Basic input sanitation */
$_GET  = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING)  ?: [];
$_POST = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING) ?: [];

require_once __DIR__ . '/common.php';
ensure_authenticated();

$home = get_home();
$db   = new SQLite3(__DIR__ . '/birds.db', SQLITE3_OPEN_READWRITE);
$db->busyTimeout(1000);

/* Paths / lists */
$base_symlink   = $home . '/BirdSongs/Extracted/By_Date';
$base           = realpath($base_symlink); // used only for safety checks

$confirm_file   = __DIR__ . '/confirmed_species_list.txt';
$exclude_file   = __DIR__ . '/exclude_species_list.txt';
$whitelist_file = __DIR__ . '/whitelist_species_list.txt';

foreach ([$confirm_file, $exclude_file, $whitelist_file] as $file) {
    if (!file_exists($file)) {
        touch($file);
    }
}

$confirmed_species   = file_exists($confirm_file)   ? file($confirm_file,   FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];
$excluded_species    = file_exists($exclude_file)   ? file($exclude_file,   FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];
$whitelisted_species = file_exists($whitelist_file) ? file($whitelist_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];

$config    = get_config();
$sf_thresh = isset($config['SF_THRESH']) ? (float)$config['SF_THRESH'] : 0.0;

/* ---------- helpers (tiny, single-purpose) ---------- */
function join_path(...$parts): string {
  return preg_replace('#/+#', '/', implode('/', $parts));
}
function can_unlink(string $p): bool {
  // unlink-able: symlink (even dangling) or regular file
  return is_link($p) || is_file($p);
}
function under_base(string $path, string $base): bool {
  if ($base === false) return false;
  $baseReal = rtrim(realpath($base) ?: $base, DIRECTORY_SEPARATOR);

  $resolved = realpath($path);
  if ($resolved === false) {
    $parent = realpath(dirname($path));
    if ($parent === false) return false;
    $resolved = $parent . DIRECTORY_SEPARATOR . basename($path);
  }
  return $resolved === $baseReal || strpos($resolved, $baseReal . DIRECTORY_SEPARATOR) === 0;
}

/**
 * Collect detection count, files to delete (unique), first scientific name,
 * and dirs to try rmdir later — for a given species.
 */
function collect_species_targets(SQLite3 $db, string $species, string $home, $base): array {
  $stmt = $db->prepare('SELECT Date, Com_Name, Sci_Name, File_Name FROM detections WHERE Com_Name = :name');
  ensure_db_ok($stmt);
  $stmt->bindValue(':name', $species, SQLITE3_TEXT);
  $res = $stmt->execute();

  $count = 0;
  $files = [];
  $dirs  = [];
  $sci   = null;

  while ($row = $res->fetchArray(SQLITE3_ASSOC)) {
    $count++;
    if ($sci === null) $sci = $row['Sci_Name'];
    $dir = str_replace([' ', "'"], ['_', ''], $row['Com_Name']);

    $candidates = [
      join_path($home, 'BirdSongs/Extracted/By_Date',        $row['Date'], $dir, $row['File_Name']),
      join_path($home, 'BirdSongs/Extracted/By_Date/shifted', $row['Date'], $dir, $row['File_Name']),
    ];

    foreach ($candidates as $c) {
      if (can_unlink($c) && under_base($c, $base)) {
        $files[$c] = true; $dirs[] = dirname($c); continue;
      }
      $d = realpath(dirname($c));
      if ($d !== false) {
        $alt = $d . DIRECTORY_SEPARATOR . basename($c);
        if (can_unlink($alt) && under_base($alt, $base)) {
          $files[$alt] = true; $dirs[] = dirname($alt);
        }
      }
    }
  }
  return [
    'count' => $count,
    'files' => array_keys($files),
    'dirs'  => array_values(array_unique($dirs)),
    'sci'   => $sci,
  ];
}

/* ---------- toggle exclude/whitelist/confirmed ---------- */
if (isset($_GET['toggle'], $_GET['species'], $_GET['action'])) {
  $list    = $_GET['toggle'];
  $species = htmlspecialchars_decode($_GET['species'], ENT_QUOTES);
  
  if ($list === 'exclude') {
    $file = $exclude_file;
  } elseif ($list === 'whitelist') {
    $file = $whitelist_file;
  } elseif ($list === 'confirmed') {
    $file = $confirm_file;
  } else {
    header('Content-Type: text/plain'); echo 'Invalid list type'; exit;
  }

  $lines = file_exists($file) ? file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];
  if ($_GET['action'] === 'add') {
    if (!in_array($species, $lines, true)) $lines[] = $species;
  } else {
    $lines = array_values(array_filter($lines, fn($l) => $l !== $species));
  }
  file_put_contents($file, implode("\n", $lines) . (empty($lines) ? "" : "\n"));
  header('Content-Type: text/plain'); echo 'OK'; exit;
}

/* ---------- count (keeps your old "getcounts=" API) ---------- */
if (isset($_GET['getcounts'])) {
  header('Content-Type: application/json');
  if ($base === false) { http_response_code(500); exit(json_encode(['error' => 'Base directory not found'])); }
  $species = htmlspecialchars_decode($_GET['getcounts'], ENT_QUOTES);
  $info = collect_species_targets($db, $species, $home, $base);
  echo json_encode(['count' => $info['count'], 'files' => count($info['files'])]); exit;
}

/* ---------- delete (keeps your old "delete=" API) ---------- */
if (isset($_GET['delete'])) {
  header('Content-Type: application/json');
  if ($base === false) { http_response_code(500); exit(json_encode(['error' => 'Base directory not found'])); }
  $species = htmlspecialchars_decode($_GET['delete'], ENT_QUOTES);
  $info = collect_species_targets($db, $species, $home, $base);

  $deleted = 0;
  foreach ($info['files'] as $fp) {
    if (!under_base($fp, $base)) continue;
    if (can_unlink($fp) && @unlink($fp)) {
      $deleted++;
      // thumbnails: "file.wav.png" and "file.png"
      foreach ([$fp . '.png', preg_replace('/\.[^.]+$/', '.png', $fp)] as $png) {
        if (can_unlink($png)) @unlink($png);
      }
    }
  }
  foreach ($info['dirs'] as $dir) {
    if (under_base($dir, $base)) @rmdir($dir); // best effort
  }

  // DB rows
  $del = $db->prepare('DELETE FROM detections WHERE Com_Name = :name');
  ensure_db_ok($del);
  $del->bindValue(':name', $species, SQLITE3_TEXT);
  $del->execute();
  $lines_deleted = $db->changes();

  // Remove from confirmed list
  if ($info['sci'] !== null && file_exists($confirm_file)) {
    $identifier = str_replace("'", '', $info['sci']);
    $lines = array_values(array_filter($confirmed_species, fn($l) => $l !== $identifier));
    file_put_contents($confirm_file, implode("\n", $lines) . (empty($lines) ? "" : "\n"));
  }

  echo json_encode(['lines' => $lines_deleted, 'files' => $deleted]); exit;
}

/* ---------- page (unchanged semantics; minor tidy) ---------- */
$result = fetch_species_array('alphabetical');
?>
<style>
  .circle-icon{display:inline-block;width:12px;height:12px;border:1px solid #777;border-radius:50%;cursor:pointer;}
  .centered{max-width:1100px;margin:0 auto}
  #speciesTable th{cursor:pointer}
</style>

<div class="centered">
<table id="speciesTable">
  <thead>
    <tr>
      <th onclick="sortTable(0)">Common Name</th>
      <th onclick="sortTable(1)">Scientific Name</th>
      <th onclick="sortTable(2)">Identifications</th>
      <th onclick="sortTable(3)">Max Confidence</th>
      <th onclick="sortTable(4)">Threshold</th>
      <th onclick="sortTable(5)">Confirmed</th>
      <th onclick="sortTable(6)">Excluded</th>
      <th onclick="sortTable(7)">Whitelisted</th>
      <th>Delete</th>
    </tr>
  </thead>
  <tbody>
<?php while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
  $common = htmlspecialchars($row['Com_Name'], ENT_QUOTES);
  $scient = htmlspecialchars($row['Sci_Name'], ENT_QUOTES);
  $count  = (int)$row['Count'];
  $max_confidence = round((float)$row['MaxConfidence'] * 100, 1);
  $identifier = str_replace("'", '', $row['Sci_Name'].'_'.$row['Com_Name']);
  $identifier_sci = str_replace("'", '', $row['Sci_Name']);

  $common_link = "<a href='views.php?view=Recordings&species="
    . rawurlencode($row['Sci_Name']) . "'>{$common}</a>";

  $is_confirmed   = in_array($identifier_sci, $confirmed_species, true);
  $is_excluded    = in_array($identifier, $excluded_species, true);
  $is_whitelisted = in_array($identifier, $whitelisted_species, true);

  $confirm_cell = $is_confirmed
    ? "<img style='cursor:pointer;max-width:12px;max-height:12px' src='images/check.svg' onclick=\"toggleSpecies('confirmed','".str_replace("'", '', $identifier_sci)."','del')\">"
    : "<span class='circle-icon' onclick=\"toggleSpecies('confirmed','".str_replace("'", '', $identifier_sci)."','add')\"></span>";

  $excl_cell = $is_excluded
    ? "<img style='cursor:pointer;max-width:12px;max-height:12px' src='images/check.svg' onclick=\"toggleSpecies('exclude','".str_replace("'", '', $identifier)."','del')\">"
    : "<span class='circle-icon' onclick=\"toggleSpecies('exclude','".str_replace("'", '', $identifier)."','add')\"></span>";

  $white_cell = $is_whitelisted
    ? "<img style='cursor:pointer;max-width:12px;max-height:12px' src='images/check.svg' onclick=\"toggleSpecies('whitelist','".str_replace("'", '', $identifier)."','del')\">"
    : "<span class='circle-icon' onclick=\"toggleSpecies('whitelist','".str_replace("'", '', $identifier)."','add')\"></span>";

  echo "<tr data-comname=\"{$common}\"><td>{$common_link}</td><td><i>{$scient}</i></td><td>{$count}</td>"
     . "<td data-sort='{$max_confidence}'>{$max_confidence}%</td>"
     . "<td class='threshold' data-sort='0'>0.0000</td>"
     . "<td data-sort='".($is_confirmed?0:1)."'>".$confirm_cell."</td>"
     . "<td data-sort='".($is_excluded?0:1)."'>".$excl_cell."</td>"
     . "<td data-sort='".($is_whitelisted?0:1)."'>".$white_cell."</td>"
     . "<td><img style='cursor:pointer;max-width:20px' src='images/delete.svg' onclick=\"deleteSpecies('".addslashes($row['Com_Name'])."')\"></td></tr>";
} ?>
  </tbody>
</table>
</div>

<script>
const scriptsBase = 'scripts/';
const sfThresh = <?php echo json_encode($sf_thresh, JSON_UNESCAPED_UNICODE); ?>;

// tiny fetch helper
const get = (url) => fetch(url, {cache:'no-store'}).then(r => r.text());

function loadThresholds() {
  get(scriptsBase + 'config.php?threshold=0').then(text => {
    const lines = (text || '').split(/\r?\n/);
    const map = Object.create(null);
    for (const line of lines) {
      const m = line.match(/^(.*)\s-\s([0-9.]+)\s*$/);
      if (!m) continue;
      const left = m[1].trim();
      const val  = parseFloat(m[2]);
      if (Number.isNaN(val)) continue;
      const u = left.lastIndexOf('_');
      const common = u >= 0 ? left.slice(u + 1) : left;
      map[common] = val; map[left] = val;
    }
    const decoder = document.createElement('textarea');
    document.querySelectorAll('#speciesTable tbody tr').forEach(row => {
      decoder.innerHTML = row.getAttribute('data-comname') || '';
      const commonName = decoder.value;
      if (Object.prototype.hasOwnProperty.call(map, commonName)) {
        const v = map[commonName];
        const cell = row.querySelector('td.threshold');
        cell.textContent = v.toFixed(4);
        cell.style.color = v >= sfThresh ? 'green' : 'red';
        cell.dataset.sort = v.toFixed(4);
      }
    });
  });
}
document.addEventListener('DOMContentLoaded', loadThresholds);

function toggleSpecies(list, species, action) {
  get(scriptsBase + 'species_tools.php?toggle=' + list + '&species=' + encodeURIComponent(species) + '&action=' + action)
    .then(t => { if (t.trim() === 'OK') location.reload(); });
}

function deleteSpecies(species) {
  get(scriptsBase + 'species_tools.php?getcounts=' + encodeURIComponent(species)).then(t => {
    let info; try { info = JSON.parse(t); } catch { alert('Could not parse count response'); return; }
    if (!confirm('Delete ' + info.count + ' detections and ' + info.files + ' files for ' + species + '?')) return;
    get(scriptsBase + 'species_tools.php?delete=' + encodeURIComponent(species)).then(t2 => {
      try {
        const res = JSON.parse(t2);
        alert('Deleted ' + res.lines + ' detections and ' + res.files + ' files for ' + species);
      } catch { alert('Deletion complete'); }
      location.reload();
    });
  });
}

function sortTable(n) {
  const table = document.getElementById('speciesTable');
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const asc = table.getAttribute('data-sort-' + n) !== 'asc';
  rows.sort((a, b) => {
    let x = a.cells[n].dataset.sort ?? a.cells[n].innerText.toLowerCase();
    let y = b.cells[n].dataset.sort ?? b.cells[n].innerText.toLowerCase();
    const nx = parseFloat(x), ny = parseFloat(y);
    if (!Number.isNaN(nx) && !Number.isNaN(ny)) { x = nx; y = ny; }
    return (x < y ? (asc ? -1 : 1) : (x > y ? (asc ? 1 : -1) : 0));
  });
  rows.forEach(r => tbody.appendChild(r));
  table.setAttribute('data-sort-' + n, asc ? 'asc' : 'desc');
}
</script>
