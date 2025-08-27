function renderDailyPlot(data) {
  const container = document.getElementById('daily-plot');
  if (!container) return;
  const table = document.createElement('table');
  table.id = 'daily-plot-table';

  const headers = ['Common Name', 'Max Confidence', 'Occurrences'];
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  headers.forEach((h, idx) => {
    const th = document.createElement('th');
    th.textContent = h;
    th.addEventListener('click', () => sortTable(idx));
    headerRow.appendChild(th);
  });
  for (let h = 0; h < 24; h++) {
    const th = document.createElement('th');
    th.textContent = h.toString().padStart(2, '0');
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  let max = 0;
  data.species.forEach(sp => {
    sp.hours.forEach(c => { if (c > max) max = c; });
  });

  data.species.forEach(sp => {
    const tr = document.createElement('tr');
    const tdName = document.createElement('td');
    tdName.textContent = sp.name;
    tr.appendChild(tdName);
    const tdConf = document.createElement('td');
    tdConf.textContent = Number(sp.max_confidence).toFixed(2);
    tr.appendChild(tdConf);
    const tdTotal = document.createElement('td');
    tdTotal.textContent = sp.total;
    tr.appendChild(tdTotal);
    sp.hours.forEach((count, hour) => {
      const td = document.createElement('td');
      if (count) {
        const alpha = max ? (count / max) : 0;
        td.style.backgroundColor = `rgba(76,175,80,${alpha})`;
        td.textContent = count;
      }
      td.title = `${sp.name} - ${count} detections - max conf ${sp.max_confidence.toFixed(2)}`;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.innerHTML = '';
  container.appendChild(table);
}

function sortTable(idx) {
  const table = document.getElementById('daily-plot-table');
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const asc = table.dataset.sortAsc === '1' ? false : true;
  rows.sort((a, b) => {
    let valA = a.cells[idx].textContent;
    let valB = b.cells[idx].textContent;
    if (idx > 0) {
      valA = parseFloat(valA) || 0;
      valB = parseFloat(valB) || 0;
    }
    return asc ? (valA > valB ? 1 : -1) : (valA < valB ? 1 : -1);
  });
  rows.forEach(r => tbody.appendChild(r));
  table.dataset.sortAsc = asc ? '1' : '0';
}

function loadDailyPlot(date) {
  const container = document.getElementById('daily-plot');
  if (!container) return;
  fetch(`scripts/daily_plot_data.php?date=${date}`)
    .then(resp => resp.json())
    .then(data => renderDailyPlot(data))
    .catch(() => { container.textContent = 'No data available'; });
}

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('daily-plot');
  if (!container) return;
  loadDailyPlot(container.dataset.date);
});
