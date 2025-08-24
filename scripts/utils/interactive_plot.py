"""Interactive daily heatmap for BirdNET-Pi (no search/filter UI)."""
from __future__ import annotations

import json
import os
from typing import Iterable, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.helpers import get_settings

conf = get_settings()
color_scheme = conf.get("COLOR_SCHEME", "light")

# --- Theme --------------------------------------------------------------------
if color_scheme == "dark":
    PLOT_BGCOLOR = "#F0F0F0"
    PAPER_BGCOLOR = "#AAAAAA"
    CUSTOM_COLOR_SCALE = [
        [0.0, PLOT_BGCOLOR],
        [0.2, "#BDBDBD"],
        [0.4, "#969696"],
        [0.6, "#737373"],
        [0.8, "#525252"],
        [1.0, "#252525"],
    ]
else:
    PLOT_BGCOLOR = "#FFFFFF"
    PAPER_BGCOLOR = "#7BC58A"
    CUSTOM_COLOR_SCALE = [
        [0.0, PLOT_BGCOLOR],
        [0.2, "#A3D8A1"],
        [0.4, "#70BD70"],
        [0.6, "#46A846"],
        [0.8, "#2E7D2E"],
        [1.0, "#004D00"],
    ]

ALL_HOURS: List[int] = list(range(24))


# --- Utils --------------------------------------------------------------------
def load_fonts() -> str:
    lang = conf.get("DATABASE_LANG")
    if lang in ["ja", "zh"]:
        return "Noto Sans JP"
    if lang == "th":
        return "Noto Sans Thai"
    return "Roboto Flex"


def normalize_logarithmic(arr: np.ndarray) -> np.ndarray:
    """
    Log-normalize to 0..1 with a gentle floor to keep low non-zero values visible.
    """
    arr = arr.astype(float)
    if arr.size == 0:
        return arr
    min_val = 0.5
    arr = np.clip(arr, min_val, None)
    amax = float(np.max(arr))
    if amax <= min_val:
        return arr - min_val
    return np.log(arr / min_val) / np.log(amax / min_val)


def determine_text_color(z: np.ndarray, threshold: float = 0.8) -> np.ndarray:
    """
    Light text on dark cells, dark text on light cells; background color on zeros.
    """
    return np.where(
        z == 0,
        PLOT_BGCOLOR,
        np.where(z > threshold, PLOT_BGCOLOR, "#1A1A1A"),
    )


def _labels_hide_zeros(values: np.ndarray) -> np.ndarray:
    """
    Convert numbers to strings but blank out zeros -> much fewer annotations.
    """
    s = values.astype(int).astype(str)
    s = np.where(values == 0, "", s)
    return s


def add_annotations(
    text_array: np.ndarray,
    text_colors: np.ndarray,
    col: int,
    species_list: Iterable[str],
    all_hours: Iterable[int],
    annotations: list,
    font_family: str,
) -> None:
    """
    Collect annotations for the heatmap (cell-wise text with per-cell color).
    """
    species_list = list(species_list)
    all_hours = list(all_hours)

    if col in [1, 2]:
        # Single-cell wide columns
        for i, species in enumerate(species_list):
            t = text_array[i, 0]
            if not t:
                continue
            annotations.append(
                dict(
                    x=0,
                    y=species,
                    text=t,
                    showarrow=False,
                    font=dict(family=font_family, color=text_colors[i, 0], size=10),
                    xref=f"x{col}",
                    yref=f"y{col}",
                    xanchor="center",
                    yanchor="middle",
                )
            )
    elif col == 3:
        # Hourly grid
        for i, species in enumerate(species_list):
            for j, hr in enumerate(all_hours):
                t = text_array[i, j]
                if not t:
                    continue
                annotations.append(
                    dict(
                        x=hr,
                        y=species,
                        text=t,
                        showarrow=False,
                        font=dict(family=font_family, color=text_colors[i, j], size=10),
                        xref="x3",
                        yref="y3",
                        xanchor="center",
                        yanchor="middle",
                    )
                )


# --- Main ---------------------------------------------------------------------
def create_plotly_heatmap(df_birds: pd.DataFrame, now) -> None:
    """
    Build HTML file: interactive_daily_plot.html
    - No search/filter UI
    - Click a cell to jump to Recordings for that species
    """
    font_family = load_fonts()

    # Early exit for empty input
    if df_birds.empty:
        html = (
            "<div style='padding:1rem;font-family:sans-serif'>"
            "<h3>No detections for this period</h3>"
            "<p>The dataset is empty; nothing to plot.</p>"
            "</div>"
        )
        _write_html(html)
        return

    main_title = f"Hourly Overview — updated {now.strftime('%Y-%m-%d %H:%M:%S')}"
    subtitle = f"({df_birds['Com_Name'].nunique()} species; {len(df_birds)} detections)"

    # Ensure datetime
    if not pd.api.types.is_datetime64_any_dtype(df_birds["Time"]):
        # If upstream supplies ns, this will still work; otherwise it auto-detects.
        df_birds["Time"] = pd.to_datetime(df_birds["Time"], errors="coerce")
    df_birds["Hour"] = df_birds["Time"].dt.hour

    # Aggregate
    plot_dataframe = (
        df_birds.groupby(["Hour", "Com_Name"], as_index=False)
        .agg(Count=("Com_Name", "count"), Conf=("Confidence", "max"))
        .fillna({"Conf": 0, "Count": 0})
    )

    df_birds_summary = (
        plot_dataframe.groupby("Com_Name", as_index=False)
        .agg(Count=("Count", "sum"), Conf=("Conf", "max"))
        .query("Count > 0")
        .sort_values(["Count", "Conf"], ascending=[False, False], kind="mergesort")
    )
    species_list: List[str] = df_birds_summary["Com_Name"].tolist()

    # Left columns: confidence (0..100), count (int)
    z_confidence = normalize_logarithmic(
        df_birds_summary["Conf"].values.reshape(-1, 1)
    ) * 100.0
    text_confidence = (
        (df_birds_summary["Conf"].values * 100).round().astype(int).astype(str)
    ).reshape(-1, 1)

    z_detections = normalize_logarithmic(
        df_birds_summary["Count"].values.reshape(-1, 1)
    )
    text_detections = _labels_hide_zeros(
        df_birds_summary["Count"].values.reshape(-1, 1)
    )
    text_color_detections = determine_text_color(z_detections, threshold=0.5)

    # Hourly pivot
    df_hourly_counts = (
        plot_dataframe.pivot_table(
            index="Com_Name", columns="Hour", values="Count", aggfunc="sum"
        )
        .fillna(0)
        .reindex(species_list)
        .reindex(columns=ALL_HOURS, fill_value=0)
    )
    df_hourly_conf = (
        plot_dataframe.pivot_table(
            index="Com_Name", columns="Hour", values="Conf", aggfunc="max"
        )
        .fillna(0)
        .reindex(species_list)
        .reindex(columns=ALL_HOURS, fill_value=0)
    )

    z_hourly = normalize_logarithmic(df_hourly_counts.values)
    text_hourly = _labels_hide_zeros(df_hourly_counts.values)
    text_color_hourly = determine_text_color(z_hourly, threshold=0.5)

    # Customdata for rich hover: per-cell count + per-cell max confidence
    custom_data_hourly = np.dstack(
        (df_hourly_counts.values, (df_hourly_conf.values * 100).astype(int))
    )

    # Build figure
    fig = make_subplots(
        rows=1,
        cols=3,
        shared_yaxes=True,
        column_widths=[0.12, 0.12, 0.76],
        horizontal_spacing=0.003,
    )

    custom_data_confidence = np.array(
        [{"confidence": float(c) * 100.0} for c in df_birds_summary["Conf"].values]
    ).reshape(-1, 1)
    custom_data_count = np.array(
        [{"count": int(n)} for n in df_birds_summary["Count"].values]
    ).reshape(-1, 1)

    fig.add_trace(
        go.Heatmap(
            z=z_confidence,
            customdata=custom_data_confidence,
            x=["Confidence"],
            y=species_list,
            colorscale= CUSTOM_COLOR_SCALE,
            showscale=False,
            hovertemplate=(
                "Species: %{y}<br>"
                "Max Confidence: %{customdata.confidence:.0f}%<extra></extra>"
            ),
            xgap=1,
            ygap=1,
            zmin=0,
            zmax=100,
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Heatmap(
            z=z_detections,
            customdata=custom_data_count,
            x=["Count"],
            y=species_list,
            colorscale=CUSTOM_COLOR_SCALE,
            showscale=False,
            hovertemplate=(
                "Species: %{y}<br>"
                "Total Counts: %{customdata.count}<extra></extra>"
            ),
            xgap=1,
            ygap=1,
            zmin=0,
            zmax=1,
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Heatmap(
            z=z_hourly,
            customdata=custom_data_hourly,
            x=ALL_HOURS,
            y=species_list,
            colorscale=CUSTOM_COLOR_SCALE,
            showscale=False,
            text=text_hourly,
            hovertemplate=(
                "Species: %{y}<br>"
                "Hour: %{x}<br>"
                "Detections: %{customdata[0]}<br>"
                "Max Confidence: %{customdata[1]}%<extra></extra>"
            ),
            xgap=1,
            ygap=1,
            zmin=0,
            zmax=1,
        ),
        row=1,
        col=3,
    )

    # Annotations (use sparingly by hiding zeros)
    annotations: list = []
    add_annotations(
        text_confidence,
        determine_text_color(z_confidence, threshold=0.5),
        col=1,
        species_list=species_list,
        all_hours=ALL_HOURS,
        annotations=annotations,
        font_family=font_family,
    )
    add_annotations(
        text_detections,
        text_color_detections,
        col=2,
        species_list=species_list,
        all_hours=ALL_HOURS,
        annotations=annotations,
        font_family=font_family,
    )
    add_annotations(
        text_hourly,
        text_color_hourly,
        col=3,
        species_list=species_list,
        all_hours=ALL_HOURS,
        annotations=annotations,
        font_family=font_family,
    )
    fig.update_layout(annotations=annotations)

    # Layout polish
    fig.update_layout(
        title=dict(
            text=f"<b>{main_title}</b><br><span style='font-size:12px'>{subtitle}</span>",
            x=0.5,
            y=0.97,
            xanchor="center",
            yanchor="top",
            font=dict(family=font_family, size=20),
        ),
        autosize=True,
        height=max(600, len(species_list) * 24 + 120),
        margin=dict(l=12, r=12, t=80, b=80),
        plot_bgcolor=PAPER_BGCOLOR,
        paper_bgcolor=PAPER_BGCOLOR,
        clickmode="event+select",
        dragmode=False,
        font=dict(family=font_family, size=10, color="#000000"),
        # lock species order as computed above
        yaxis=dict(
            autorange="reversed",
            categoryorder="array",
            categoryarray=species_list,
            tickfont=dict(family=font_family, size=10),
            showticklabels=True,
            ticklabelstandoff=12,
            fixedrange=True,
            automargin=True,
        ),
        xaxis1=dict(
            title="Max Confidence",
            showticklabels=False,
            title_font=dict(family=font_family, size=10),
            fixedrange=True,
        ),
        xaxis2=dict(
            title="Total Counts",
            showticklabels=False,
            title_font=dict(family=font_family, size=10),
            fixedrange=True,
        ),
        xaxis3=dict(
            title="Hour",
            tickfont=dict(family=font_family, size=10),
            tickmode="linear",
            dtick=1,
            fixedrange=True,
        ),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)

    # Single HTML build (no search/filter UI)
    div_id = "daily-heatmap"
    html_str = f"""
    <div class="chart-container" style="position:relative;max-width:1200px;width:98%;margin:0 auto;">
        {fig.to_html(
            include_plotlyjs="cdn",
            full_html=False,
            default_height="80%",
            default_width="100%",
            div_id=div_id,
            config=dict(
                scrollZoom=False,
                doubleClick=False,
                displaylogo=False,
                displayModeBar=False,
                modeBarButtonsToRemove=[
                    "zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","resetScale2d"
                ],
            ),
        )}
    </div>
    <script>
    (function() {{
        var plot = document.getElementById("{div_id}");
        if (!plot) return;

        // Keep plot responsive
        window.addEventListener("resize", function() {{
            if (window.Plotly && plot) {{
                Plotly.Plots.resize(plot);
            }}
        }});

        // Click -> navigate to species recordings
        plot.on("plotly_click", function(data) {{
            try {{
                if (data && data.points && data.points[0] && data.points[0].y) {{
                    var species = String(data.points[0].y || "").replace(/\\s+/g, "+");
                    var url = "/views.php?view=Recordings&species=" + species;
                    window.location.href = url;
                }}
            }} catch(e) {{}}
        }});
    }})();
    </script>
    """

    _write_html(html_str)


# --- I/O ----------------------------------------------------------------------
def _write_html(html_str: str) -> None:
    output_dir = os.path.expanduser("~/BirdSongs/Extracted/Charts/")
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "interactive_daily_plot.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_str)
