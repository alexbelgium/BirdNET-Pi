<?php

/* Prevent XSS input */
$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

ini_set('user_agent', 'PHP_ImageProvider/1.0');
error_reporting(E_ERROR);
ini_set('display_errors', 0);
require_once 'scripts/common.php';
$home = get_home();
$config = get_config();
$image_provider_name = strtolower($config["IMAGE_PROVIDER"] ?? 'wikipedia');

$db = new SQLite3('./scripts/birds.db', SQLITE3_OPEN_READONLY);
$db->busyTimeout(1000);

if(isset($_GET['sort']) && $_GET['sort'] == "occurrences") {
  
  $statement = $db->prepare('SELECT Date, Time, File_Name, Com_Name, COUNT(*), MAX(Confidence) FROM detections GROUP BY Com_Name ORDER BY COUNT(*) DESC');
  ensure_db_ok($statement);
  $result = $statement->execute();

  $statement2 = $db->prepare('SELECT Date, Time, File_Name, Com_Name, COUNT(*), MAX(Confidence) FROM detections GROUP BY Com_Name ORDER BY COUNT(*) DESC');
  ensure_db_ok($statement2);
  $result2 = $statement2->execute();

} else if(isset($_GET['sort']) && $_GET['sort'] == "confidence") {
  $statement = $db->prepare('SELECT Date, Time, File_Name, Com_Name, COUNT(*), MAX(Confidence) FROM detections GROUP BY Com_Name ORDER BY MAX(Confidence) DESC');
  ensure_db_ok($statement);
  $result = $statement->execute();

  $statement2 = $db->prepare('SELECT Date, Time, File_Name, Com_Name, COUNT(*), MAX(Confidence) FROM detections GROUP BY Com_Name ORDER BY MAX(Confidence) DESC');
  ensure_db_ok($statement2);
  $result2 = $statement2->execute();

} else {

  $statement = $db->prepare('SELECT Date, Time, File_Name, Com_Name, COUNT(*), MAX(Confidence) FROM detections GROUP BY Com_Name ORDER BY Com_Name ASC');
  ensure_db_ok($statement);
  $result = $statement->execute();

  $statement2 = $db->prepare('SELECT Date, Time, File_Name, Com_Name, COUNT(*), MAX(Confidence) FROM detections GROUP BY Com_Name ORDER BY Com_Name ASC');
  ensure_db_ok($statement2);
  $result2 = $statement2->execute();
}


if(isset($_GET['species'])){
  $selection = htmlspecialchars_decode($_GET['species'], ENT_QUOTES);
  $statement3 = $db->prepare("SELECT Com_Name, Sci_Name, COUNT(*), MAX(Confidence), File_Name, Date, Time from detections WHERE Com_Name = \"$selection\"");
  ensure_db_ok($statement3);
  $result3 = $statement3->execute();
}

if(!file_exists($home."/BirdNET-Pi/scripts/disk_check_exclude.txt") || strpos(file_get_contents($home."/BirdNET-Pi/scripts/disk_check_exclude.txt"),"##start") === false) {
  file_put_contents($home."/BirdNET-Pi/scripts/disk_check_exclude.txt", "");
  file_put_contents($home."/BirdNET-Pi/scripts/disk_check_exclude.txt", "##start\n##end\n");
}

if (get_included_files()[0] === __FILE__) {
  echo '<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BirdNET-Pi DB</title>
</head>';
}
?>

<div class="stats">
<div class="column">
<div style="width: auto;
   text-align: center">
   <form action="views.php" method="GET">
    <input type="hidden" name="sort" value="<?php if(isset($_GET['sort'])){echo $_GET['sort'];}?>">
      <input type="hidden" name="view" value="Species Stats">
      <button <?php if(!isset($_GET['sort']) || $_GET['sort'] == "alphabetical"){ echo "class='sortbutton active'";} else { echo "class='sortbutton'"; }?> type="submit" name="sort" value="alphabetical">
         <img src="images/sort_abc.svg" title="Sort by alphabetical" alt="Sort by alphabetical">
      </button>
      <button <?php if(isset($_GET['sort']) && $_GET['sort'] == "occurrences"){ echo "class='sortbutton active'";} else { echo "class='sortbutton'"; }?> type="submit" name="sort" value="occurrences">
         <img src="images/sort_occ.svg" title="Sort by occurrences" alt="Sort by occurrences">
      </button>
      <button <?php if(isset($_GET['sort']) && $_GET['sort'] == "confidence"){ echo "class='sortbutton active'";} else { echo "class='sortbutton'"; }?> type="submit" name="sort" value="confidence">
         <img src="images/sort_conf.svg" title="Sort by confidence" alt="Sort by confidence">
      </button>
      <button <?php if(isset($_GET['sort']) && $_GET['sort'] == "date"){ echo "class='sortbutton active'";} else { echo "class='sortbutton'"; }?> type="submit" name="sort" value="date">
         <img src="images/sort_date.svg" title="Sort by date" alt="Sort by date">
      </button>
   </form>
</div>
<br>
<form action="views.php" method="GET">
<input type="hidden" name="sort" value="<?php if(isset($_GET['sort'])){echo $_GET['sort'];}?>">
<input type="hidden" name="view" value="Species Stats">
<table>
  <?php
  $birds = array();
  $values = array();

  while($results=$result2->fetchArray(SQLITE3_ASSOC))
  {
    $comname = preg_replace('/ /', '_', $results['Com_Name']);
    $comname = preg_replace('/\'/', '', $comname);
    $filename = "/By_Date/".$results['Date']."/".$comname."/".$results['File_Name'];
    $birds[] = $results['Com_Name'];
    if ($_GET['sort'] == "confidence") {
        $values[] = ' (' . round($results['MAX(Confidence)'] * 100) . '%)';
    } elseif ($_GET['sort'] == "occurrences") {
        $valuescount = $results['COUNT(*)'];
        if ($valuescount >= 1000) {
            $values[] = ' (' . round($valuescount / 1000, 1) . 'k)';
        } else {
            $values[] = ' (' . $valuescount . ')';
        }
    } elseif ($_GET['sort'] == "date") {
        $values[] = ' (' . $results['Date'] . ')';
    }
  }

  if(count($birds) > 45) {
    $num_cols = 3;
  } else {
    $num_cols = 1;
  }
  $num_rows = ceil(count($birds) / $num_cols);

  for ($row = 0; $row < $num_rows; $row++) {
    echo "<tr>";

    for ($col = 0; $col < $num_cols; $col++) {
      $index = $row + $col * $num_rows;

      if ($index < count($birds)) {
        ?>
        <td>
            <button type="submit" name="species" value="<?php echo $birds[$index];?>"><?php echo $birds[$index].$values[$index];?></button>
        </td>
        <?php
      } else {
        echo "<td></td>";
      }
    }

    echo "</tr>";
  }
  ?>
</table>
</form>
</div>
<dialog style="margin-top: 5px;max-height: 95vh;
  overflow-y: auto;overscroll-behavior:contain" id="attribution-dialog">
  <h1 id="modalHeading"></h1>
  <p id="modalText"></p>
  <button onclick="hideDialog()">Close</button>
</dialog>
<script src="static/dialog-polyfill.js"></script>
<script src="static/Chart.bundle.js"></script>
<script src="static/chartjs-plugin-trendline.min.js"></script>
<script src="static/custom-audio-player.js" defer></script>
<script>
var dialog = document.querySelector('dialog');
dialogPolyfill.registerDialog(dialog);

function showDialog() {
  document.getElementById('attribution-dialog').showModal();
}

function hideDialog() {
  document.getElementById('attribution-dialog').close();
}

function setModalText(iter, title, text, authorlink) {
  document.getElementById('modalHeading').innerHTML = "Photo "+iter+": \""+title+"\" Attribution";
  document.getElementById('modalText').innerHTML = "<div style='white-space:nowrap'>Image link: <a target='_blank' href="+text+">"+text+"</a><br>Author link: <a target='_blank' href="+authorlink+">"+authorlink+"</a></div>";
  showDialog();
}

function showSpeciesModal(title, text, authorlink, photolink, licenseurl) {
  document.getElementById('modalHeading').innerHTML = "Photo: \""+decodeURIComponent(title.replaceAll("+"," "))+"\" Attribution";
  document.getElementById('modalText').innerHTML = "<div><img style='border-radius:5px;max-height: calc(100vh - 15rem);display:block;margin:0 auto;' src='"+photolink+"'></div><br><div style='white-space:nowrap'>Image link: <a target='_blank' href="+text+">"+text+"</a><br>Author link: <a target='_blank' href="+authorlink+">"+authorlink+"</a><br>License URL: <a target='_blank' href="+licenseurl+">"+licenseurl+"</a></div>";
  showDialog();
}

function generateMiniGraph(elem, comname, days = 30) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/todays_detections.php?comname=' + comname + '&days=' + days);
  xhr.onload = function() {
    if (xhr.status === 200) {
      var detections = JSON.parse(xhr.responseText);
      if (typeof(window.chartWindow) != 'undefined') {
        document.body.removeChild(window.chartWindow);
        window.chartWindow = undefined;
      }
      var chartWindow = document.createElement('div');
      chartWindow.className = "chartdiv";
      document.body.appendChild(chartWindow);

      var canvas = document.createElement('canvas');
      chartWindow.appendChild(canvas);

      var range = document.createElement('div');
      range.className = 'graph-range';
      range.innerHTML = "<span data-days='30'>1m</span> | <span data-days='180'>3m</span> | <span data-days='360'>1y</span>";
      range.addEventListener('click', function(ev){
        if (ev.target.dataset.days) {
          generateMiniGraph(elem, comname, ev.target.dataset.days);
        }
      });
      chartWindow.appendChild(range);

      canvas.width = chartWindow.offsetWidth;
      canvas.height = chartWindow.offsetHeight - range.offsetHeight;

      var ctx = canvas.getContext('2d');
      var chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: detections.map(item => item.date),
          datasets: [{
            label: 'Detections',
            data: detections.map(item => item.count),
            backgroundColor: '#9fe29b',
            borderColor: '#77c487',
            borderWidth: 1,
            lineTension: 0.3,
            pointRadius: 1,
            pointHitRadius: 10,
            trendlineLinear: {
              style: "rgba(55, 99, 64, 0.5)",
              lineStyle: "solid",
              width: 1.5
            }
          }]
        },
        options: {
          layout: { padding: { right: 10 } },
          title: { display: true, text: 'Detections Over ' + days + 'd' },
          legend: { display: false },
          scales: {
            xAxes: [{ display: false, gridLines: { display: false }, ticks: { autoSkip: true, maxTicksLimit: 2 } }],
            yAxes: [{ gridLines: { display: false }, ticks: { beginAtZero: true, precision: 0, stepSize: 1 } }]
          }
        }
      });

      var buttonRect = elem.getBoundingClientRect();
      var chartRect = chartWindow.getBoundingClientRect();
      if (window.innerWidth < 700) {
        chartWindow.style.left = 'calc(75% - ' + (chartRect.width / 2) + 'px)';
      } else {
        chartWindow.style.left = (buttonRect.right + 10) + 'px';
      }
      var buttonCenter = buttonRect.top + (buttonRect.height / 2);
      var chartHeight = chartWindow.offsetHeight;
      var chartTop = buttonCenter - (chartHeight / 2);
      chartWindow.style.top = chartTop + 'px';

      var closeButton = document.createElement('button');
      closeButton.id = "chartcb";
      closeButton.innerText = 'X';
      closeButton.style.position = 'absolute';
      closeButton.style.top = '5px';
      closeButton.style.right = '5px';
      closeButton.addEventListener('click', function() {
        document.body.removeChild(chartWindow);
        window.chartWindow = undefined;
      });
      chartWindow.appendChild(closeButton);
      window.chartWindow = chartWindow;
    }
  };
  xhr.send();
}

window.addEventListener('scroll', function() {
  var charts = document.querySelectorAll('.chartdiv');
  charts.forEach(function(chart) {
    chart.parentNode.removeChild(chart);
    window.chartWindow = undefined;
  });
});
</script>  
<div class="column center">
<?php if(!isset($_GET['species'])){
?><p class="centered">Choose a species to load images from <?php echo ucfirst($image_provider_name); ?>.</p>
<?php
};?>
<?php if(isset($_GET['species'])){
  $species = $_GET['species'];
  $iter=0;
  $image_provider = null;
  if ($image_provider_name === 'flickr' && ! empty($config["FLICKR_API_KEY"])) {
    $image_provider = new Flickr();
    if (isset($_SESSION["FLICKR_FILTER_EMAIL"]) && $_SESSION["FLICKR_FILTER_EMAIL"] !== $image_provider->get_uid_from_db()['uid']) {
      $_SESSION["FLICKR_FILTER_EMAIL"] = $image_provider->get_uid_from_db()['uid'];
    }
  } else {
    $image_provider = new Wikipedia();
  }
while($results=$result3->fetchArray(SQLITE3_ASSOC)){
  $count = $results['COUNT(*)'];
  $maxconf = round((float)round($results['MAX(Confidence)'],2) * 100 ) . '%';
  $date = $results['Date'];
  $time = $results['Time'];
  $name = $results['Com_Name'];
  $sciname = $results['Sci_Name'];
  $dbsciname = preg_replace('/ /', '_', $sciname);
  $comname = preg_replace('/ /', '_', $results['Com_Name']);
  $comname = preg_replace('/\'/', '', $comname);
  $linkname = preg_replace('/_/', '+', $dbsciname);
  $filename = "/By_Date/".$date."/".$comname."/".$results['File_Name'];
  $engname = get_com_en_name($sciname);

  $info_url = get_info_url($results['Sci_Name']);
  $url = $info_url['URL'];
  $url_title = $info_url['TITLE'];
  $cache = $image_provider->get_image($sciname);
  $image_html = '';
  if (!empty($cache['image_url'])) {
  $image_html = "<img class='species-thumb' onclick=\"showSpeciesModal('".urlencode($cache['title'])."','{$cache['photos_url']}','{$cache['author_url']}','{$cache['image_url']}','{$cache['license_url']}')\" src='{$cache['image_url']}'>";
  }
  $comnamegraph = str_replace("'", "\\'", $species);
  echo str_pad("<h3>$species</h3>".
    "<table><tr>\n  <td class=\"relative\">".$image_html."<a target=\"_blank\" href=\"index.php?filename=".$results['File_Name']."\"><img title=\"Open in new tab\" class=\"copyimage\" width=25 src=\"images/copy.png\"></a><i>$sciname</i>\n  <a href=\"$url\" target=\"_blank\"><img style=\"width: unset !important; display: inline; height: 1em; cursor: pointer;\" title=\"$url_title\" src=\"images/info.png\" width=\"20\"></a>\n  <a href=\"https://wikipedia.org/wiki/$sciname\" target=\"_blank\"><img style=\"width: unset !important; display: inline; height: 1em; cursor: pointer;\" title=\"Wikipedia\" src=\"images/wiki.png\" width=\"20\"></a><img style=\"width: unset !important; display: inline; height: 1em; cursor:pointer\" title=\"View species stats\" onclick=\"generateMiniGraph(this, '$comnamegraph')\" width=\"20\" src=\"images/chart.svg\"><br>\n  Occurrences: $count<br>\n  Max Confidence: $maxconf<br>\n  Best Recording: $date $time<br><br>\n  <div class='custom-audio-player' data-audio-src=\"$filename\" data-image-src=\"$filename.png\"></div>\n  </tr>\n    </table>\n  <p>Loading Images from ".ucfirst($image_provider_name)."</p>", '6096');
  echo "<script>document.getElementsByTagName(\"h3\")[0].scrollIntoView();</script>";
  
  ob_flush();
  flush();

  if ($image_provider_name === 'flickr' && ! empty($config["FLICKR_API_KEY"])) {
    $flickrjson = json_decode(file_get_contents("https://www.flickr.com/services/rest/?method=flickr.photos.search&api_key=".$config["FLICKR_API_KEY"]."&text=\"".str_replace(' ', '%20', $engname)."\"&license=2%2C3%2C4%2C5%2C6%2C9&sort=relevance&per_page=15&format=json&nojsoncallback=1"), true)["photos"]["photo"];

    foreach ($flickrjson as $val) {

      $iter++;
      $modaltext = "https://flickr.com/photos/".$val["owner"]."/".$val["id"];
      $authorlink = "https://flickr.com/people/".$val["owner"];
      $imageurl = 'https://farm' .$val["farm"]. '.static.flickr.com/' .$val["server"]. '/' .$val["id"]. '_'  .$val["secret"].  '.jpg';
      echo "<span style='cursor:pointer;' onclick='setModalText(".$iter.",\"".$val["title"]."\",\"".$modaltext."\", \"".$authorlink."\")'><img style='vertical-align:top' src=\"$imageurl\"></span>"; 
    }
  } elseif ($image_provider_name === 'wikipedia') {
    $wiki = new Wikipedia();
    $cache = $wiki->get_image($sciname);
    if (!empty($cache['image_url'])) {
      echo "<span><img style='vertical-align:top' src=\"".$cache['image_url']."\"></span>";
    }
  }
}
}
?>
<?php if(isset($_GET['species'])){?>
<br><br>
<div class="brbanner">Best Recordings for Other Species:</div><br>
<?php } else {?>
<hr><br>
<?php } ?>
  <form action="views.php" method="GET">
    <input type="hidden" name="sort" value="<?php if(isset($_GET['sort'])){echo $_GET['sort'];}?>">
    <input type="hidden" name="view" value="Species Stats">
    <table>
<?php
$excludelines = [];
while($results=$result->fetchArray(SQLITE3_ASSOC))
{
$comname = preg_replace('/ /', '_', $results['Com_Name']);
$comname = preg_replace('/\'/', '', $comname);
$filename = "/By_Date/".$results['Date']."/".$comname."/".$results['File_Name'];

array_push($excludelines, $results['Date']."/".$comname."/".$results['File_Name']);
array_push($excludelines, $results['Date']."/".$comname."/".$results['File_Name'].".png");
?>
      <tr>
      <td class="relative"><a target="_blank" href="index.php?filename=<?php echo $results['File_Name']; ?>"><img title="Open in new tab" class="copyimage" width=25 src="images/copy.png"></a>
        <button type="submit" name="species" value="<?php echo $results['Com_Name'];?>"><?php echo $results['Com_Name'];?></button><br><b>Occurrences:</b> <?php echo $results['COUNT(*)'];?><br>
      <b>Max Confidence:</b> <?php echo $percent = round((float)round($results['MAX(Confidence)'],2) * 100 ) . '%';?><br>
      <b>Best Recording:</b> <?php echo $results['Date']." ".$results['Time'];?><br>
      <div class='custom-audio-player' data-audio-src="<?php echo $filename;?>" data-image-src="<?php echo $filename.".png";?>"></div>
      </td></tr>
<?php
}

$file = file_get_contents($home."/BirdNET-Pi/scripts/disk_check_exclude.txt");
file_put_contents($home."/BirdNET-Pi/scripts/disk_check_exclude.txt", "##start"."\n".implode("\n",$excludelines)."\n".substr($file, strpos($file, "##end")));
?>
    </table>
  </form>
</div>
</div>
<?php
if (get_included_files()[0] === __FILE__) {
  echo '</body></html>';
}
