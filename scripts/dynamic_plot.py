import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import os
from utils.helpers import get_settings  # Import to access COLOR_SCHEME

# Define custom colorscales for light and dark modes
COLOR_SCALES = {
    "light": [
        [0.0, '#E0F2E9'], [0.2, '#A3D8A1'], [0.4, '#70BD70'],
        [0.6, '#46A846'], [0.8, '#2E7D2E'], [1.0, '#004D00']
    ],
    "dark": [
        [0.0, '#F0F0F0'], [0.2, '#BDBDBD'], [0.4, '#969696'],
        [0.6, '#737373'], [0.8, '#525252'], [1.0, '#252525']
    ]
}
ALL_HOURS = list(range(24))


def normalize_logarithmic(arr):
    """Applies a logarithmic normalization to the array, mapping values between 0.5 and max(arr) to a normalized scale between 0 and 1."""
    arr = arr.astype(float)
    min_val = 0.5
    arr = np.clip(arr, min_val, None)
    return np.log(arr / min_val) / np.log(np.max(arr) / min_val) if np.max(arr) > min_val else arr - min_val


def determine_text_color(z, threshold=0.5):
    """Determines text color (black or white) based on normalized value of z."""
    return np.where(z > threshold, 'white', 'black')


def add_annotations(fig, text_array, text_colors, col, row, species_list, all_hours, annotations):
    """Collects annotations for the heatmap without adding them individually, appending them to the provided annotations list."""
    if col in [1, 2]:  # Single-column heatmaps
        for i, species in enumerate(species_list):
            current_text, current_color = text_array[i, 0], text_colors[i, 0]
            if current_text:
                annotations.append(dict(
                    x=0, y=species, text=current_text, showarrow=False,
                    font=dict(color=current_color, size=10),
                    xref=f'x{col}', yref=f'y{col}', xanchor='center', yanchor='middle'
                ))
    elif col == 3:  # Multi-column heatmap
        for i, species in enumerate(species_list):
            for j, hour in enumerate(all_hours):
                current_text, current_color = text_array[i, j], text_colors[i, j]
                if current_text:
                    annotations.append(dict(
                        x=hour, y=species, text=current_text, showarrow=False,
                        font=dict(color=current_color, size=10),
                        xref='x3', yref='y3', xanchor='center', yanchor='middle'
                    ))


def create_plotly_heatmap(df_birds, now):
    """Creates a Plotly heatmap with annotations based on bird detection data."""
    # Titles and Subtitle
    main_title = f"Hourly Overview Updated at {now.strftime('%Y-%m-%d %H:%M:%S')}"
    subtitle = f"({df_birds['Com_Name'].nunique()} species today; {len(df_birds)} detections today)"
    
    # Ensure 'Time' is datetime
    if not pd.api.types.is_datetime64_any_dtype(df_birds['Time']):
        df_birds['Time'] = pd.to_datetime(df_birds['Time'], unit='ns')

    df_birds['Hour'] = df_birds['Time'].dt.hour
    
    # Group data and fill missing values
    plot_dataframe = df_birds.groupby(['Hour', 'Com_Name']).agg(
        Count=('Com_Name', 'count'),
        Conf=('Confidence', 'max')
    ).reset_index().fillna({'Conf': 0, 'Count': 0})

    # Fetch color scheme setting and choose corresponding colorscale and text color
    conf = get_settings()
    color_scheme = conf.get('COLOR_SCHEME', 'light')
    color_scale = COLOR_SCALES.get(color_scheme, COLOR_SCALES["light"])

    # Summarize data for heatmap axes
    df_birds_summary = plot_dataframe.groupby('Com_Name').agg(
        Count=('Count', 'sum'),
        Conf=('Conf', 'max')
    ).reset_index()
    df_birds_summary = df_birds_summary[df_birds_summary['Count'] > 0]
    df_birds_summary.sort_values(by=['Count', 'Conf'], ascending=[False, False], inplace=True)
    species_list = df_birds_summary['Com_Name'].tolist()

    # Normalize values and prepare text annotations
    z_confidence = normalize_logarithmic(df_birds_summary['Conf'].values.reshape(-1, 1) * 100)
    text_confidence = np.char.add(np.round(df_birds_summary['Conf'].values).astype(int).astype(str), ' %')

    z_detections = normalize_logarithmic(df_birds_summary['Count'].values.reshape(-1, 1))
    text_detections = df_birds_summary['Count'].astype(str).values  # Use actual counts for annotations
    text_color_detections = determine_text_color(z_detections, threshold=0.5, color_scheme=color_scheme)

    df_hourly = plot_dataframe.pivot_table(index='Com_Name', columns='Hour', values='Count', aggfunc='sum').fillna(0)
    df_hourly = df_hourly.reindex(species_list).fillna(0).reindex(columns=ALL_HOURS, fill_value=0)
    z_hourly = normalize_logarithmic(df_hourly.values)
    text_hourly = df_hourly.astype(int).astype(str).values  # Use actual counts for hourly annotations
    text_color_hourly = determine_text_color(z_hourly, threshold=0.5, color_scheme=color_scheme)

    # Create subplots
    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, column_widths=[0.1, 0.1, 0.7], horizontal_spacing=0.02)

    # Heatmap Traces
    fig.add_trace(go.Heatmap(
        z=z_confidence, customdata=df_birds_summary['Conf'].values, x=['Confidence'], y=species_list,
        colorscale=color_scale, showscale=False, hovertemplate='Species: %{y}<br>Max Confidence: %{customdata:.0f}%<extra></extra>',
        xgap=1, ygap=1, zmin=0, zmax=1
    ), row=1, col=1)

    fig.add_trace(go.Heatmap(
        z=z_detections, customdata=df_birds_summary['Count'].values, x=['Count'], y=species_list,
        colorscale=color_scale, showscale=False, hovertemplate='Species: %{y}<br>Total Counts: %{customdata}<extra></extra>',
        xgap=1, ygap=1, zmin=0, zmax=1
    ), row=1, col=2)

    fig.add_trace(go.Heatmap(
        z=z_hourly, customdata=df_hourly.values, x=ALL_HOURS, y=species_list,
        colorscale=color_scale, showscale=False, hovertemplate='Species: %{y}<br>Hour: %{x}<br>Detections: %{customdata}<extra></extra>',
        xgap=1, ygap=1, zmin=0, zmax=1
    ), row=1, col=3)

    # Annotations
    annotations = []
    add_annotations(fig, text_confidence.reshape(-1, 1), determine_text_color(z_confidence, threshold=0.5, color_scheme=color_scheme), col=1, row=1, species_list=species_list, all_hours=ALL_HOURS, annotations=annotations)
    add_annotations(fig, text_detections.reshape(-1, 1), text_color_detections, col=2, row=1, species_list=species_list, all_hours=ALL_HOURS, annotations=annotations)
    add_annotations(fig, text_hourly, text_color_hourly, col=3, row=1, species_list=species_list, all_hours=ALL_HOURS, annotations=annotations)
    fig.update_layout(annotations=annotations)

    # Layout configuration
    fig.update_layout(
        title=dict(text=f"<b>{main_title}</b><br><span style='font-size:14px;'>{subtitle}</span>", x=0.5, y=0.97, xanchor='center', yanchor='top', font=dict(size=24)),
        autosize=True, height=max(600, len(species_list) * 25 + 100),
        yaxis=dict(autorange='reversed', tickfont=dict(size=10), showticklabels=True, ticklabelstandoff=15, fixedrange=True),
        xaxis1=dict(title='Max confidence', showticklabels=False, title_font=dict(size=10), fixedrange=True),
        xaxis2=dict(title='Total counts', showticklabels=False, title_font=dict(size=10), fixedrange=True),
        xaxis3=dict(title='Hour', tickfont=dict(size=10), tickmode='linear', dtick=1, fixedrange=True),
        margin=dict(l=20, r=20, t=80, b=80), clickmode='event+select',
        plot_bgcolor='#CCCCCC', paper_bgcolor='#7F7F7F', font=dict(size=10), dragmode=False
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)

    # Export the figure as an HTML string
    html_str = (
        f"<div class='chart-container' style='width: 80%; margin: 0 auto;'>"
        + fig.to_html(
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
                    'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'resetScale2d'
                ]
            )
        )
        + "</div>"
    )
    
    # Add CSS and JavaScript
    html_str = (
        "<style>.modebar-container { display: none !important; }</style>"
        + html_str +
        "<script>"
        "var plot = document.getElementsByClassName('plotly-graph-div')[0];"
        "plot.on('plotly_click', function(data){"
        "    var species = data.points[0].y.replace(/ /g, '+');"
        "    var url = '/views.php?view=Recordings&species=' + species;"
        "    window.location.href = url;"
        "});"
        "function makeYAxisLabelsClickable() {"
        "    document.querySelectorAll('.yaxislayer-above .ytick text').forEach(function(label) {"
        "        label.style.cursor = 'pointer';"
        "        label.addEventListener('click', function() {"
        "            var species = label.textContent.replace(/ /g, '+');"
        "            var url = '/views.php?view=Recordings&species=' + species;"
        "            window.location.href = url;"
        "        });"
        "    });"
        "}"
        "makeYAxisLabelsClickable();"
        "plot.on('plotly_afterplot', makeYAxisLabelsClickable);"
        "</script>"
    )

    # Save the HTML file
    output_dir = os.path.expanduser('~/BirdSongs/Extracted/Charts/')
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, 'interactive_daily_plot.html'), 'w') as f:
        f.write(html_str)

    # Clear figure to reset layout and prevent issues in future runs
    fig.clear()
