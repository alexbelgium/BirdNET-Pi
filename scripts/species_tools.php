<?php
/* Basic input sanitation */
$_GET  = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING)  ?: [];
$_POST = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING) ?: [];

require_once __DIR__ . '/common.php';
ensure_authenticated();

$home = get_home();

/* ---------- disk species counts (AJAX endpoint) ---------- */
if (isset($_GET['diskcounts'])) {
    header('Content-Type: application/json');
    $script = __DIR__ . '/disk_species_count.sh';
    $cmd    = 'HOME=' . escapeshellarg($home) . ' bash ' . escapeshellarg($script) . ' 2>&1';
    $output = @shell_exec($cmd);
    $counts = [];
    if ($output !== null) {
        foreach (preg_split('/\\r?\\n/', $output) as $line) {
            $line = trim($line);
            if ($line === '') continue;
            if (preg_match('/^([0-9]+(?:\\.[0-9]+)?)(k?)\\s*:\\s*(.+)$/i', $line, $m)) {
                $num = (float)$m[1];
                if (strtolower($m[2]) === 'k') $num *= 1000;
                $counts[$m[3]] = (int)round($num);
            }
        }
    }
    echo json_encode($counts, JSON_UNESCAPED_UNICODE);
    exit;
}

/* ---------- DB open (RO unless deleting) ---------- */
$flags = isset($_GET['delete']) ? SQLITE3_OPEN_READWRITE : SQLITE3_OPEN_READONLY;
$db   = new SQLite3(__DIR__ . '/birds.db', $flags);
$db->busyTimeout(1000);
$db->exec("
  PRAGMA journal_mode=WAL;       -- safe read concurrency
  PRAGMA synchronous=NORMAL;     -- cheaper fsyncs (read-mostly)
  PRAGMA temp_store=MEMORY;      -- temp data stays in RAM
  PRAGMA cache_size=-80000;     -- ~80MB page cache (tune to your RAM)
  PRAGMA mmap_size=268435456;    -- 256MB mmap (set 0 if kernel disallows)
  PRAGMA foreign_keys=OFF;       -- if you don't need them during this read
");

/* Paths / lists */
$base_symlink   = $home . '/BirdSongs/Extracted/By_Date';
$base           = realpath($base_symlink); // safety checks

$confirm_file   = __DIR__ . '/confirmed_species_list.txt';
$exclude_file   = __DIR__ . '/exclude_species_list.txt';
$whitelist_file = __DIR__ . '/whitelist_species_list.txt';

foreach ([$confirm_file, $exclude_file, $whitelist_file] as $file) {
    if (!file_exists($file)) touch($file);
}

$confirmed_species   = file_exists($confirm_file)   ? file($confirm_file,   FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];
$excluded_species    = file_exists($exclude_file)   ? file($exclude_file,   FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];
$whitelisted_species = file_exists($whitelist_file) ? file($whitelist_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];

$config    = get_config();
$sf_thresh = isset($config['SF_THRESH']) ? (float)$config['SF_THRESH'] : 0.0;

/* ---------- helpers ---------- */
function join_path(...$parts): string { return preg_replace('#/+#', '/', implode('/', $parts)); }
function can_unlink(string $p): bool { return is_link($p) || is_file($p); }
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

/* Collect files/dirs for a species */
function collect_species_targets(SQLite3 $db, string $species, string $home, $base): array {
  $stmt = $db->prepare('SELECT Date, Com_Name, Sci_Name, File_Name FROM detections WHERE Com_Name = :name');
  ensure_db_ok($stmt);
  $stmt->bindValue(':name', $species, SQLITE3_TEXT);
  $res = $stmt->execute();

  $count = 0; $files = []; $dirs = []; $sci = null;
  while ($row = $res->fetchArray(SQLITE3_ASSOC)) {
    $count++; if ($sci === null) $sci = $row['Sci_Name'];
    $dir = str_replace([' ', "'"], ['_', ''], $row['Com_Name']);
    $candidates = [
      join_path($home, 'BirdSongs/Extracted/By_Date',         $row['Date'], $dir, $row['File_Name']),
      join_path($home, 'BirdSongs/Extracted/By_Date/shifted', $row['Date'], $dir, $row['File_Name']),
    ];
    foreach ($candidates as $c) {
      if (can_unlink($c) && under_base($c, $base)) { $files[$c] = true; $dirs[] = dirname($c); continue; }
      $d = realpath(dirname($c));
      if ($d !== false) {
        $alt = $d . DIRECTORY_SEPARATOR . basename($c);
        if (can_unlink($alt) && under_base($alt, $base)) { $files[$alt] = true; $dirs[] = dirname($alt); }
      }
    }
  }
  return ['count'=>$count, 'files'=>array_keys($files), 'dirs'=>array_values(array_unique($dirs)), 'sci'=>$sci];
}

/* ---------- toggle exclude/whitelist/confirmed ---------- */
if (isset($_GET['toggle'], $_GET['species'], $_GET['action'])) {
  $list    = $_GET['toggle'];
  $species = htmlspecialchars_decode($_GET['species'], ENT_QUOTES);

  if     ($list === 'exclude')   { $file = $exclude_file; }
  elseif ($list === 'whitelist') { $file = $whitelist_file; }
  elseif ($list === 'confirmed') { $file = $confirm_file; }
  else { header('Content-Type: text/plain'); echo 'Invalid list type'; exit; }

  $lines = file_exists($file) ? file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];
  if ($_GET['action'] === 'add') {
    if (!in_array($species, $lines, true)) $lines[] = $species;
  } else {
    $lines = array_values(array_filter($lines, fn($l) => $l !== $species));
  }
  file_put_contents($file, implode("\n", $lines) . (empty($lines) ? "" : "\n"));
  header('Content-Type: text/plain'); echo 'OK'; exit;
}

/* ---------- count ---------- */
if (isset($_GET['getcounts'])) {
  header('Content-Type: application/json');
  if ($base === false) { http_response_code(500); exit(json_encode(['error' => 'Base directory not found'])); }
  $species = htmlspecialchars_decode($_GET['getcounts'], ENT_QUOTES);
  $info = collect_species_targets($db, $species, $home, $base);
  echo json_encode(['count' => $info['count'], 'files' => count($info['files'])]); exit;
}

/* ---------- delete ---------- */
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
      foreach ([$fp . '.png', preg_replace('/\.[^.]+$/', '.png', $fp)] as $png) {
        if (can_unlink($png)) @unlink($png);
      }
    }
  }
  foreach ($info['dirs'] as $dir) { if (under_base($dir, $base)) @rmdir($dir); }

  $del = $db->prepare('DELETE FROM detections WHERE Com_Name = :name');
  ensure_db_ok($del);
  $del->bindValue(':name', $species, SQLITE3_TEXT);
  $del->execute();
  $lines_deleted = $db->changes();

  if ($info['sci'] !== null && file_exists($confirm_file)) {
    $identifier = str_replace("'", '', $info['sci']);
    $lines = array_values(array_filter($confirmed_species, fn($l) => $l !== $identifier));
    file_put_contents($confirm_file, implode("\n", $lines) . (empty($lines) ? "" : "\n"));
  }

  echo json_encode(['lines' => $lines_deleted, 'files' => $deleted]); exit;
}

/* ---------- query species aggregates ---------- */
$sql = <<<SQL
SELECT Com_Name, Sci_Name, COUNT(*) AS Count, MAX(Confidence) AS MaxConfidence, MAX(Date) AS LastSeen
FROM detections
GROUP BY Com_Name, Sci_Name;
SQL;
$result = $db->query($sql);
?>
<style>
  .circle-icon{display:inline-block;width:12px;height:12px;border:1px solid #777;border-radius:50%;cursor:pointer;}
  .centered{max-width:1100px;margin:0 auto}
  #speciesTable th{cursor:pointer}
  .toolbar{display:flex;gap:8px;align-items:center;margin:8px 0}
  .toolbar input[type="text"]{padding:6px 8px;min-width:260px}
</style>

<div class="centered">
  <!-- Search with persistence -->
  <div class="toolbar">
    <input id="q" type="text" placeholder="Filter species… (name, scientific)" title="Type to filter; persists across reloads">
    <small id="matchCount"></small>
  </div>

  <table id="speciesTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Common Name</th>
        <th onclick="sortTable(1)">Scientific Name</th>
        <th onclick="sortTable(2)">Identifications</th>
        <th onclick="sortTable(3)">Max Confidence</th>
        <th onclick="sortTable(4)">Last Seen</th>
        <th onclick="sortTable(5)">Probability</th>
        <th onclick="sortTable(6)">Confirmed</th>
        <th onclick="sortTable(7)">Excluded</th>
        <th onclick="sortTable(8)">Whitelisted</th>
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

  $lastSeen = $row['LastSeen'] ?? '';
  $lastSeenSort = $lastSeen ? (strtotime($lastSeen) ?: 0) : 0;
  $lastSeenDisplay = htmlspecialchars($lastSeen, ENT_QUOTES);

  $common_link = "<a href='views.php?view=Recordings&species=" . rawurlencode($row['Sci_Name']) . "'>{$common}</a>";

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

  echo "<tr data-comname=\"{$common}\">"
     . "<td>{$common_link}</td>"
     . "<td><i>{$scient}</i></td>"
     . "<td>{$count}</td>"
     . "<td data-sort='{$max_confidence}'>{$max_confidence}%</td>"
     . "<td data-sort=\"{$lastSeenSort}\">{$lastSeenDisplay}</td>"
     . "<td class='threshold' data-sort='0'>0.0000</td>"
     . "<td data-sort='".($is_confirmed?0:1)."'>".$confirm_cell."</td>"
     . "<td data-sort='".($is_excluded?0:1)."'>".$excl_cell."</td>"
     . "<td data-sort='".($is_whitelisted?0:1)."'>".$white_cell."</td>"
     . "<td><img style='cursor:pointer;max-width:20px' src='images/delete.svg' onclick=\"deleteSpecies('".addslashes($row['Com_Name'])."')\"></td>"
     . "</tr>";
} ?>
    </tbody>
  </table>
</div>

<script>
const scriptsBase = 'scripts/';
const sfThresh = <?php echo json_encode($sf_thresh, JSON_UNESCAPED_UNICODE); ?>;
const get = (url) => fetch(url, {cache:'no-store'}).then(r => r.text());

/* ---------- Probability (thresholds) auto-load ---------- */
function loadThresholds() {
  return get(scriptsBase + 'config.php?threshold=0').then(text => {
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
  }).catch(() => {
    console.warn('Probability load failed.');
  });
}

/* ---------- Files on Disk column auto-load ---------- */
function addDiskCounts() {
  return get(scriptsBase + 'species_tools.php?diskcounts=1').then(t => {
    let counts; try { counts = JSON.parse(t); } catch { console.warn('Could not parse disk counts'); return; }

    const table = document.getElementById('speciesTable');
    const headerRow = table.tHead.rows[0];

    // Insert header before last column (Delete)
    const deleteHeader = headerRow.lastElementChild;
    const th = document.createElement('th');
    th.textContent = 'Files on Disk';
    headerRow.insertBefore(th, deleteHeader);

    const colIndex = headerRow.cells.length - 2; // new column index
    th.addEventListener('click', () => sortTable(colIndex));

    const decoder = document.createElement('textarea');
    document.querySelectorAll('#speciesTable tbody tr').forEach(tr => {
      decoder.innerHTML = tr.getAttribute('data-comname') || '';
      const name = decoder.value;
      const lookup = name.replace(/'/g, '');
      const count = counts[lookup] || 0;
      const td = document.createElement('td');
      td.textContent = count;
      td.dataset.sort = count;
      tr.insertBefore(td, tr.lastElementChild); // before Delete cell
    });
  }).catch(() => {
    console.warn('Disk counts load failed.');
  });
}

/* ---------- toggles / delete ---------- */
function toggleSpecies(list, species, action) {
  get(scriptsBase + 'species_tools.php?toggle=' + list + '&species=' + encodeURIComponent(species) + '&action=' + action)
    .then(t => { if (t.trim() === 'OK') location.reload(); });
}
function deleteSpecies(species) {
  get(scriptsBase + 'species_tools.php?getcounts=' + encodeURIComponent(species)).then(t => {
    let info; try { info = JSON.parse(t); } catch { alert('Could not parse count response'); return; }
    if (!confirm('Delete ' + info.count + ' detections and local audio and png files for ' + species + '?')) return;
    get(scriptsBase + 'species_tools.php?delete=' + encodeURIComponent(species)).then(t2 => {
      try { const res = JSON.parse(t2); alert('Deleted ' + res.lines + ' detections and ' + res.files + ' files for ' + species); }
      catch { alert('Deletion complete'); }
      location.reload();
    });
  });
}

/* ---------- Sorting with persistence ---------- */
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
  try { localStorage.setItem('speciesSortCol', String(n)); localStorage.setItem('speciesSortAsc', asc ? '1' : '0'); } catch(e){}
}
function applySavedSort() {
  const table = document.getElementById('speciesTable');
  const col = parseInt(localStorage.getItem('speciesSortCol') || '', 10);
  const asc = localStorage.getItem('speciesSortAsc');
  if (!Number.isFinite(col)) return;
  sortTable(col);
  const isAscNow = table.getAttribute('data-sort-' + col) === 'asc';
  if ((asc === '1') !== isAscNow) sortTable(col);
}

/* ---------- Search with persistence ---------- */
const q = document.getElementById('q');
const matchCount = document.getElementById('matchCount');
function applyFilter() {
  const needle = (q.value || '').trim().toLowerCase();
  let shown = 0, total = 0;
  document.querySelectorAll('#speciesTable tbody tr').forEach(tr => {
    total++;
    const txt = tr.innerText.toLowerCase();
    const vis = txt.includes(needle);
    tr.style.display = vis ? '' : 'none';
    if (vis) shown++;
  });
  matchCount.textContent = total ? `${shown} / ${total}` : '';
  try { localStorage.setItem('speciesFilter', q.value); } catch(e){}
}
q.addEventListener('input', applyFilter);

/* ---------- boot ---------- */
document.addEventListener('DOMContentLoaded', () => {
  try { const saved = localStorage.getItem('speciesFilter'); if (saved !== null) q.value = saved; } catch(e){}
  applyFilter();
  applySavedSort();
  // Auto-load both heavy enrichments
  loadThresholds();
  addDiskCounts();
});
</script>
