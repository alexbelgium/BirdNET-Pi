"""
Generates an interactive Plotly heatmap for BirdNET detections and writes a self-contained HTML snippet.
- Three panels: Max confidence, total count, hourly counts.
- Search + sort in the browser; clicking a species navigates to a detail page.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.helpers import get_settings

ALL_HOURS = list(range(24))


def _load_fonts_family() -> str:
    conf = get_settings()
    lang = (conf.get('DATABASE_LANG') or '').lower()
    if lang in ('ja', 'zh'):
        return 'Noto Sans JP'
    if lang == 'th':
        return 'Noto Sans Thai'
    return 'Roboto Flex'  # default


def _theme():
    """Return colors based on configured color scheme."""
    conf = get_settings()
    color_scheme = conf.get('COLOR_SCHEME', 'light').lower()
    if color_scheme == 'dark':
        plot_bg = '#1e1e1e'
        paper_bg = '#1a1a1a'
        color_scale = [
            [0.0, '#0f0f0f'],
            [0.2, '#303030'],
            [0.4, '#505050'],
            [0.6, '#707070'],
            [0.8, '#9a9a9a'],
            [1.0, '#d0d0d0'],
        ]
        text_base = '#eaeaea'
    else:
        plot_bg = '#ffffff'
        paper_bg = '#f5fbf6'
        color_scale = [
            [0.0, '#ffffff'],
            [0.2, '#cfead2'],
            [0.4, '#9fd4a9'],
            [0.6, '#6ac07f'],
            [0.8, '#3ea75a'],
            [1.0, '#1d6f34'],
        ]
        text_base = '#111111'
    return plot_bg, paper_bg, color_scale, text_base


def _normalize_log(arr: np.ndarray, min_val: float = 0.5) -> np.ndarray:
    """
    Logarithmic normalization to 0..1.
    Values below min_val are clamped to min_val.
    If max <= min_val, return zeros.
    """
    arr = np.array(arr, dtype=float)
    arr = np.clip(arr, min_val, None)
    amax = float(np.max(arr)) if arr.size else min_val
    if amax <= min_val:
        return np.zeros_like(arr, dtype=float)
    return np.log(arr / min_val) / np.log(amax / min_val)


def _text_contrast(z_norm: np.ndarray, threshold: float = 0.6, light='#ffffff', dark='#1a1a1a') -> np.ndarray:
    """
    Choose light text on high-intensity cells and dark text on low-intensity cells.
    For zeros (masked cells), return transparent to hide labels.
    """
    z_norm = np.array(z_norm, dtype=float)
    out = np.where(z_norm == 0, 'rgba(0,0,0,0)', np.where(z_norm >= threshold, light, dark))
    return out


def _add_annotations(annotations, text_array, text_colors, species_list, x_vals, xref):
    """
    Collect annotations for a column. x_vals is either ['Confidence'], ['Count'], or 0..23
    xref is 'x1', 'x2', or 'x3' for subplots.
    """
    if len(x_vals) == 1:
        x = x_vals[0]
        for i, sp in enumerate(species_list):
            t = text_array[i, 0]
            c = text_colors[i, 0]
            if t and c != 'rgba(0,0,0,0)':
                annotations.append(dict(
                    x=x, y=sp, text=t, showarrow=False,
                    font=dict(size=10, color=c),
                    xref=xref, yref='y1', xanchor='center', yanchor='middle'
                ))
    else:
        for i, sp in enumerate(species_list):
            for j, x in enumerate(x_vals):
                t = text_array[i, j]
                c = text_colors[i, j]
                if t and c != 'rgba(0,0,0,0)':
                    annotations.append(dict(
                        x=x, y=sp, text=t, showarrow=False,
                        font=dict(size=10, color=c),
                        xref=xref, yref='y1', xanchor='center', yanchor='middle'
                    ))


def create_plotly_heatmap(
    df_birds: pd.DataFrame,
    now: datetime | None = None,
    tz: str = 'Europe/Brussels',
    output_dir: str = os.path.expanduser('~/BirdSongs/Extracted/Charts'),
    output_name: str = 'interactive_daily_plot.html'
) -> str:
    """
    Build the HTML for the interactive heatmap and write it to output_dir/output_name.
    Returns the absolute path to the written file.
    """

    # ----- Time & fonts/theme -------------------------------------------------
    if now is None:
        now = datetime.now(ZoneInfo(tz))
    font_family = _load_fonts_family()
    plot_bg, paper_bg, colorscale, text_base = _theme()

    # ----- Time column parsing ------------------------------------------------
    if not pd.api.types.is_datetime64_any_dtype(df_birds['Time']):
        # Try several common patterns; coerce invalid rows to NaT and drop them
        parsed = pd.to_datetime(df_birds['Time'], errors='coerce', utc=False)
        if parsed.isna().all():
            parsed = pd.to_datetime(df_birds['Time'], errors='coerce', unit='s', utc=False)
        if parsed.isna().all():
            parsed = pd.to_datetime(df_birds['Time'], errors='coerce', unit='ms', utc=False)
        if parsed.isna().all():
            parsed = pd.to_datetime(df_birds['Time'], errors='coerce', unit='ns', utc=False)
        df_birds['Time'] = parsed
    df_birds = df_birds.dropna(subset=['Time']).copy()
    df_birds['Hour'] = df_birds['Time'].dt.tz_localize(ZoneInfo(tz), nonexistent='shift_forward', ambiguous='NaT').dt.hour \
        if df_birds['Time'].dt.tz is None else df_birds['Time'].dt.tz_convert(ZoneInfo(tz)).dt.hour

    # ----- Aggregations -------------------------------------------------------
    plot_df = (
        df_birds
        .groupby(['Hour', 'Com_Name'])
        .agg(Count=('Com_Name', 'count'), Conf=('Confidence', 'max'))
        .reset_index()
        .fillna({'Count': 0, 'Conf': 0})
    )
    summary = (
        plot_df
        .groupby('Com_Name')
        .agg(Count=('Count', 'sum'), Conf=('Conf', 'max'))
        .reset_index()
    )
    summary = summary[summary['Count'] > 0].sort_values(['Count', 'Conf'], ascending=[False, False])
    species_list = summary['Com_Name'].tolist()

    if not species_list:
        # Nothing to plot—write a tiny placeholder
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, output_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write("<p>No detections for today.</p>")
        return out_path

    # ----- Panels data --------------------------------------------------------
    # Left: max confidence per species
    z_conf = _normalize_log(summary['Conf'].to_numpy().reshape(-1, 1)) * 100.0
    txt_conf = (summary['Conf'] * 100).round().astype(int).astype(str).to_numpy().reshape(-1, 1) + ' %'
    # Middle: total counts per species
    z_cnt = _normalize_log(summary['Count'].to_numpy().reshape(-1, 1))
    txt_cnt = summary['Count'].astype(str).to_numpy().reshape(-1, 1)
    # Right: hourly grid
    hourly_counts = (
        plot_df.pivot_table(index='Com_Name', columns='Hour', values='Count', aggfunc='sum')
        .reindex(species_list).fillna(0).reindex(columns=ALL_HOURS, fill_value=0)
    )
    hourly_conf = (
        plot_df.pivot_table(index='Com_Name', columns='Hour', values='Conf', aggfunc='max')
        .reindex(species_list).fillna(0).reindex(columns=ALL_HOURS, fill_value=0)
    )
    z_hourly = _normalize_log(hourly_counts.to_numpy())
    txt_hourly = hourly_counts.astype(int).astype(str).to_numpy()

    # Text colors for contrast
    tcolor_conf = _text_contrast(z_conf / 100.0)
    tcolor_cnt = _text_contrast(z_cnt, threshold=0.5)
    tcolor_hourly = _text_contrast(z_hourly, threshold=0.5)

    # Customdata (JS sorting/filtering depends on these)
    # For panel 1 & 2: a single dict per species with BOTH metrics
    per_species_custom = np.array([
        [{'confidence': float(c) * 100.0, 'count': int(n)}]
        for c, n in zip(summary['Conf'].to_numpy(), summary['Count'].to_numpy())
    ], dtype=object)

    # For panel 3: per cell (count, confidence%)
    per_cell_custom = np.dstack((hourly_counts.to_numpy(), (hourly_conf.to_numpy() * 100.0).astype(int)))

    # ----- Figure -------------------------------------------------------------
    fig = make_subplots(
        rows=1, cols=3, shared_yaxes=True,
        column_widths=[0.12, 0.12, 0.76], horizontal_spacing=0.006
    )

    fig.add_trace(go.Heatmap(
        z=z_conf, x=['Confidence'], y=species_list,
        customdata=per_species_custom,
        colorscale=colorscale, showscale=False,
        hovertemplate='Species: %{y}<br>Max Confidence: %{customdata[0].confidence:.0f}%<extra></extra>',
        xgap=1, ygap=1, zmin=0, zmax=100
    ), row=1, col=1)

    fig.add_trace(go.Heatmap(
        z=z_cnt, x=['Count'], y=species_list,
        customdata=per_species_custom,  # same object; includes both metrics
        colorscale=colorscale, showscale=False,
        hovertemplate='Species: %{y}<br>Total Count: %{customdata[0].count}<extra></extra>',
        xgap=1, ygap=1, zmin=0, zmax=1
    ), row=1, col=2)

    fig.add_trace(go.Heatmap(
        z=z_hourly, x=ALL_HOURS, y=species_list,
        customdata=per_cell_custom,
        colorscale=colorscale, showscale=False,
        text=txt_hourly,
        hovertemplate='Species: %{y}<br>Hour: %{x}:00<br>Detections: %{customdata[0]}<br>Max Conf: %{customdata[1]}%<extra></extra>',
        xgap=1, ygap=1, zmin=0, zmax=1
    ), row=1, col=3)

    # Annotations to control per-cell label colors
    annotations = []
    _add_annotations(annotations, txt_conf, tcolor_conf, species_list, ['Confidence'], 'x1')
    _add_annotations(annotations, txt_cnt,  tcolor_cnt,  species_list, ['Count'],      'x2')
    _add_annotations(annotations, txt_hourly, tcolor_hourly, species_list, ALL_HOURS, 'x3')

    main_title = f"Hourly Overview — Updated {now.strftime('%Y-%m-%d %H:%M:%S')}"
    subtitle = f"({summary['Com_Name'].nunique()} species; {int(summary['Count'].sum())} detections)"

    fig.update_layout(
        title=dict(
            text=f"<b>{main_title}</b><br><span style='font-size:12px;'>{subtitle}</span>",
            x=0.5, y=0.98, xanchor='center', yanchor='top'
        ),
        autosize=True,
        height=max(600, len(species_list) * 25 + 120),
        margin=dict(l=20, r=20, t=90, b=80),
        plot_bgcolor=paper_bg,
        paper_bgcolor=paper_bg,
        font=dict(family=_load_fonts_family(), size=12, color=text_base),
        clickmode='event+select',
        dragmode=False,
        annotations=annotations,
        yaxis=dict(
            autorange='reversed',
            tickfont=dict(size=10),
            categoryorder='array',
            categoryarray=species_list,
            fixedrange=True
        ),
        xaxis1=dict(title='Max Confidence', showticklabels=False, fixedrange=True),
        xaxis2=dict(title='Total Count', showticklabels=False, fixedrange=True),
        xaxis3=dict(
            title='Hour', tickmode='linear', dtick=1, fixedrange=True
        ),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)

    # ----- HTML (self-contained snippet) -------------------------------------
    annotations_json = json.dumps(annotations, ensure_ascii=False)

    # Load fonts (small, cached CDN). Safe to omit if you host locally.
    fonts_html = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;600&family=Noto+Sans+Thai:wght@400;600&family=Roboto+Flex:opsz,wght@8..144,400;8..144,600&display=swap" rel="stylesheet">
    """.strip()

    # Give container a stable ID so JS can find it reliably
    graph_html = fig.to_html(
        include_plotlyjs='cdn',
        full_html=False,
        default_height='80%',
        default_width='100%',
        config=dict(
            scrollZoom=False,
            doubleClick=False,
            displaylogo=False,
            displayModeBar=False,
            modeBarButtonsToRemove=[
                'zoom2d','pan2d','select2d','lasso2d','zoomIn2d','zoomOut2d','resetScale2d'
            ]
        ),
        div_id='birds-heatmap'
    )

    html_str = f"""
{fonts_html}
<style>
  /* Hide modebar defensively */
  .modebar, .modebar-container, .plotly .modebar {{"display":"none"}} 
</style>

<div id="birds-heatmap-container" style="position:relative; max-width: 1100px; width: 98%; margin: 0 auto;">
  <div style="position:absolute; bottom:10px; left:10px; z-index:10;">
    <input type="text" id="birdSearch" placeholder="Search..." 
           style="padding:5px; font-size:12px; background-color:rgba(255,255,255,0.6); color:#444; border:1px solid #ccc;
                  border-radius:3px; width:160px;" />
    <button id="filterButton" style="padding:5px; font-size:12px; background-color:rgba(255,255,255,0.6);
                  color:#444; border:1px solid #ccc; border-radius:3px;">OK</button>
    <select id="sortOptions" style="padding:5px; font-size:12px; background-color:rgba(255,255,255,0.6);
                  color:#444; border:1px solid #ccc; border-radius:3px;">
      <option value="count" selected>Total Count</option>
      <option value="confidence">Max Confidence</option>
      <option value="species">Species Name</option>
    </select>
  </div>
  {graph_html}
</div>

<script>
  const allAnnotations = {annotations_json};
  const plot = document.getElementById('birds-heatmap');
  // Deep copy of original data (structuredClone for modern browsers; fallback JSON)
  let originalData = plot && plot.data ? JSON.parse(JSON.stringify(plot.data)) : [];

  function applyFilter() {{
    if (!plot || !originalData.length) return;

    const searchTerm = (document.getElementById('birdSearch').value || '').toLowerCase();
    const sortBy = document.getElementById('sortOptions').value;

    const speciesList = originalData[0].y.slice(); // copy
    let indices = [];

    speciesList.forEach((sp, i) => {{
      if (sp.toLowerCase().includes(searchTerm)) indices.push(i);
    }});

    // Sort indices by selected metric
    if (sortBy === 'confidence') {{
      indices.sort((a,b) => (originalData[0].customdata[b][0].confidence || 0)
                          -  (originalData[0].customdata[a][0].confidence || 0));
    }} else if (sortBy === 'species') {{
      indices.sort((a,b) => speciesList[a].localeCompare(speciesList[b]));
    }} else {{ // count
      indices.sort((a,b) => (originalData[0].customdata[b][0].count || 0)
                          -  (originalData[0].customdata[a][0].count || 0));
    }}

    // Rebuild traces with filtered/sorted species
    const newData = originalData.map((trace) => {{
      const t = JSON.parse(JSON.stringify(trace));
      if (t.type === 'heatmap') {{
        t.y = indices.map(i => speciesList[i]);
        t.z = indices.map(i => trace.z[i]);
        if (trace.customdata) t.customdata = indices.map(i => trace.customdata[i]);
        if (trace.text)       t.text       = indices.map(i => trace.text[i]);
      }}
      return t;
    }});

    // Filter annotations to visible species (keep all x)
    const visibleSet = new Set(newData[0].y.map(s => s.toLowerCase()));
    const filteredAnnotations = allAnnotations.filter(a => visibleSet.has(String(a.y).toLowerCase()));

    // Apply new data and keep categories in the new order
    const newLayout = Object.assign({{}}, plot.layout, {{
      annotations: filteredAnnotations,
      yaxis: Object.assign({{}}, plot.layout.yaxis || {{}}, {{
        categoryorder: 'array',
        categoryarray: newData[0].y
      }})
    }});

    Plotly.react(plot, newData, newLayout);
  }}

  document.getElementById('filterButton').addEventListener('click', applyFilter);
  document.getElementById('birdSearch').addEventListener('keyup', (e) => {{ if (e.key === 'Enter') applyFilter(); }});
  document.getElementById('sortOptions').addEventListener('change', applyFilter);

  // Click to navigate
  plot.on('plotly_click', function(data) {{
    if (data.points && data.points[0] && data.points[0].y) {{
      const species = encodeURIComponent(String(data.points[0].y));
      const url = '/views.php?view=Recordings&species=' + species;
      window.location.href = url;
    }}
  }});
</script>
    """

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, output_name)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_str)
    return out_path
