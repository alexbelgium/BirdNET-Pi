#===============================================================================
#=== daily_plot.py (adjusted version @jmtmp) ==========================================
#===============================================================================
#=== 2024-04-19: new version
#=== 2024-04-28: new custom formatting for millions (my_int_fmt function)
#===             new formatting of total occurence in semi-monthly plot
#=== 2024-09-01: updated suptitle and xlabels formatting
#=== 2024-09-05: Daemon implementing
#=== 2024-09-26: transparent first column
#=== 2024-10-02: code refactor
#===============================================================================

import argparse
import sqlite3
import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.font_manager as font_manager
from matplotlib import rcParams
from matplotlib.colors import LogNorm, TwoSlopeNorm
from matplotlib.ticker import FormatStrFormatter
from datetime import datetime
from time import sleep
from functools import lru_cache
from utils.helpers import DB_PATH, FONT_DIR, get_settings, get_font
from utils.interactive_plot import create_plotly_heatmap

# Cache the settings to avoid redundant calls
@lru_cache(maxsize=None)
def get_settings_cached():
    return get_settings()

def load_fonts():
    # Add every font at the specified location
    font_dir = [FONT_DIR]
    for font in font_manager.findSystemFonts(font_dir, fontext='ttf'):
        font_manager.fontManager.addfont(font)
    # Set font family globally
    rcParams['font.family'] = get_font()['font.family']

def my_int_fmt(number, converthundreds=False):
    try:
        number = float(number)
    except (ValueError, TypeError):
        return str(number)
    if number >= 9_500_000:
        return f"{round(number / 1_000_000)}M"
    elif number >= 950:
        return f"{round(number / 1_000)}k"
    elif converthundreds and number >= 100:
        return f".{round(number / 100)}k"
    else:
        return str(int(number))

def clr_plot_facecolor():
    # Update colors according to color scheme
    if get_settings_cached()['COLOR_SCHEME'] == "dark":
        return 'darkgrey'
    else:
        return '#77C487'

def clr_current_ticklabel():
    # Update colors according to color scheme
    if get_settings_cached()['COLOR_SCHEME'] == "dark":
        return 'white'
    else:
        return 'red'

def my_heatmap(axis, crosstable, clrmap, clrnorm, annotfmt='', annotsize='medium'):
    # annotsize: float or {'xx-small', 'x-small', 'small', 'medium', 'large', 'x-large', 'xx-large'}
    hm_axes = sns.heatmap(crosstable, cmap=clrmap, norm=clrnorm, cbar=False, linewidths=0.5, linecolor="Silver", ax=axis,
                          annot=(annotfmt != ''), fmt=annotfmt, annot_kws={"fontsize": annotsize})
    # Set border
    for _, spine in hm_axes.spines.items():
        spine.set_visible(True)
    return hm_axes

def get_daily_plot_data(conn, now):
    sql_fields = "Time, Confidence, COUNT(DISTINCT Com_Name) as Species, COUNT(Com_Name) as Detections, COUNT(DISTINCT Date) as Days"
    db_entire = pd.read_sql_query(f"SELECT {sql_fields} FROM detections", conn)
    db_today = pd.read_sql_query(f"SELECT {sql_fields} FROM detections WHERE Date = DATE('now')", conn)
    # Prepare suptitle
    days_count = int(db_entire.Days[0]) if db_entire.Days[0] else 1  # Avoid division by zero
    avg_daily_detections = round(int(db_entire.Detections[0]) / days_count)
    plot_suptitle = f"Hourly overview updated at {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
    plot_suptitle += f"({db_today.Species[0]} species today, {db_entire.Species[0]} in total;  "
    plot_suptitle += f"{db_today.Detections[0]} detections today, {avg_daily_detections} on average)"
    # Prepare dataset
    sql = """
        SELECT Time, Confidence, Date, CAST(strftime('%H', Time) AS INTEGER) AS Hour, Com_Name,
               COUNT(Com_Name) AS Count, MAX(Confidence) AS Conf
        FROM detections
        WHERE Date = DATE('now', 'localtime')
        GROUP BY Hour, Com_Name
    """
    plot_dataframe = pd.read_sql_query(sql, conn)
    return plot_suptitle, plot_dataframe

def get_data(now=None):
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    if now is None:
        now = datetime.now()
    df = pd.read_sql_query(f"SELECT * from detections WHERE Date = DATE('{now.strftime('%Y-%m-%d')}')",
                           conn)

    # Convert Date and Time Fields to Panda's format
    df['Date'] = pd.to_datetime(df['Date'])
    df['Time'] = pd.to_datetime(df['Time'], unit='ns')

    # Add round hours to dataframe
    df['Hour of Day'] = [r.hour for r in df.Time]

    return df, now

def get_yearly_plot_data(conn, now):
    sql_fields = "COUNT(DISTINCT Com_Name) as Species, COUNT(Com_Name) as Detections, COUNT(DISTINCT Date) as Days"
    db_entire = pd.read_sql_query(f"SELECT {sql_fields} FROM detections", conn)
    db_ytd = pd.read_sql_query(f"SELECT {sql_fields} FROM detections WHERE Date >= DATE('now','start of year')", conn)
    # Prepare suptitle
    plot_suptitle = (f"Semi-monthly overview updated at {now.strftime('%Y-%m-%d %H:%M:%S')}   "
                     f"({db_ytd.Species[0]} species this year, {db_entire.Species[0]} in total)")
    # Prepare dataset
    sql = """
        SELECT 2 * (CAST(strftime('%m', Date) AS INTEGER) - 1) +
               CASE WHEN CAST(strftime('%d', Date) AS INTEGER) < 16 THEN 0 ELSE 1 END AS Period,
               strftime('%Y', Date) AS Year, Com_Name,
               COUNT(Com_Name) AS Count, MAX(Confidence) AS Conf
        FROM detections
        WHERE Date >= DATE('now','start of year')
        GROUP BY Period, Com_Name
    """
    plot_dataframe = pd.read_sql_query(sql, conn)
    return plot_suptitle, plot_dataframe

def create_plot(chart_name, chart_suptitle, df_birds, now, time_unit, period_col, xlabel, xtick_labels):
    # Common code for data preparation
    df_birds_summary = df_birds.groupby('Com_Name').agg({'Count': 'sum', 'Conf': 'max'})
    df_birds_ordered = df_birds_summary.sort_values(by=['Count', 'Conf'], ascending=[False, False])
    df_birds['Com_Name'] = pd.Categorical(df_birds['Com_Name'], ordered=True, categories=df_birds_ordered.index)
    no_of_rows = df_birds_summary.shape[0]
    total_recordings = df_birds['Count'].sum()
    if no_of_rows == 0:
        print("No data available for plotting.")
        return

    # Prepare crosstables
    df_confidences = pd.crosstab(index=df_birds['Com_Name'], columns=df_birds[time_unit], values=df_birds['Conf'], aggfunc='max')
    df_detections = pd.crosstab(index=df_birds['Com_Name'], columns=df_birds[time_unit], values=df_birds['Count'], aggfunc='sum')
    df_perioddata = pd.crosstab(index=df_birds['Com_Name'], columns=df_birds[period_col], values=df_birds['Count'], aggfunc='sum')

    # Prepare empty matrix for periods
    df_empty_matrix = pd.DataFrame(data=0, index=df_perioddata.index, columns=pd.Series(data=range(len(xtick_labels))))
    df_perioddata = (df_empty_matrix + df_perioddata).fillna(0)

    # Color palettes
    color_scheme = get_settings_cached()['COLOR_SCHEME']
    cmap_confi = 'PiYG' if color_scheme != "dark" else 'Greys'
    cmap_count = 'Blues' if color_scheme != "dark" else 'Greys'
    norm_confi = TwoSlopeNorm(vmin=0.25, vmax=1.25, vcenter=0.75)
    norm_count = LogNorm(vmin=1, vmax=total_recordings)

    # Plot dimensions
    row_height = 0.28
    fig_height = row_height * (no_of_rows + 4)
    row_space = row_height / fig_height

    # Plot setup
    f, axs = plt.subplots(1, 4, figsize=(10, fig_height), width_ratios=[5, 2, 2, 18], facecolor=clr_plot_facecolor())
    plt.subplots_adjust(left=0.02, right=0.98, top=(1 - 2 * row_space), bottom=(0 + 2 * row_space), wspace=0, hspace=0)
    plt.suptitle(chart_suptitle, y=0.99)

    # Bird name column
    axs[0].set_xlim(0, 1)
    axs[0].set_ylim(0, len(df_confidences.index))
    axs[0].axis('off')

    # Confidence column
    hm_confi = my_heatmap(axs[1], df_confidences, cmap_confi, norm_confi, annotfmt=".0%")
    hm_confi.tick_params(bottom=True, left=False, labelbottom=True, labeltop=False, labelleft=True, labelrotation=0)
    hm_confi.set(xlabel=None, ylabel=None, xticklabels=['max\nconfidence'])

    # Occurrence column
    hm_count = my_heatmap(axs[2], df_detections, cmap_count, norm_count, annotfmt="g")
    hm_count.tick_params(bottom=True, left=False, labelbottom=True, labeltop=False, labelleft=False)
    hm_count.set(xlabel=None, ylabel=None, xticklabels=['total\ndetections'])

    # Apply custom annotation format
    for t in hm_count.texts:
        if len(t.get_text()) > 3:
            t.set_text(my_int_fmt(t.get_text()))

    # Occurrence heatmap
    hm_data = my_heatmap(axs[3], df_perioddata, cmap_count, norm_count, annotfmt="g", annotsize=9)
    hm_data.tick_params(bottom=True, top=False, left=False, labelbottom=True, labeltop=False,
                        labelleft=False, labelrotation=0)
    hm_data.set(xlabel=None, ylabel=None)
    hm_data.set_xlabel(xlabel, labelpad=1)
    hm_data.xaxis.set_major_formatter(FormatStrFormatter('%d'))
    hm_data.set_xticklabels(xtick_labels)

    # Apply custom annotation format
    for t in hm_data.texts:
        if len(t.get_text()) > 2:
            t.set_text(my_int_fmt(t.get_text(), converthundreds=True))

    # Set tick label for current period
    for idx, label in enumerate(hm_data.get_xticklabels()):
        if period_col == 'Hour':
            if int(label.get_text()) == now.hour:
                label.set_color(clr_current_ticklabel())
        elif period_col == 'Period':
            # Map current period to index
            current_period = 2 * (now.month - 1) + (0 if now.day < 16 else 1)
            if idx == current_period:
                label.set_color(clr_current_ticklabel())

    # Save the plot
    plt.savefig(os.path.expanduser(f'~/BirdSongs/Extracted/Charts/{chart_name}.png'))
    plt.show()
    plt.close()

def main(daemon, sleep_m):
    load_fonts()
    while True:
        with sqlite3.connect(DB_PATH) as conn:
            now = datetime.now()

            # Generate daily plot data and static plot
            suptitle, dataframe = get_daily_plot_data(conn, now)
            create_plot(
                chart_name='Combo-' + now.strftime("%Y-%m-%d"),
                chart_suptitle=suptitle,
                df_birds=dataframe,
                now=now,
                time_unit='Date',
                period_col='Hour',
                xlabel='hourly detections',
                xtick_labels=list(range(24))
            )

            try:
                data, time = get_data(now)
                create_plotly_heatmap(data, time)
            except Exception as e:
                print(f"Failed to create interactive heatmap: {e}")

            # Generate yearly plot data and static plot
            suptitle, dataframe = get_yearly_plot_data(conn, now)
            month_labels = ['Jan', '', 'Feb', '', 'Mar', '', 'Apr', '', 'May', '', 'Jun', '', 'Jul', '',
                            'Aug', '', 'Sep', '', 'Oct', '', 'Nov', '', 'Dec', '']
            create_plot(
                chart_name='Combo2-' + now.strftime("%Y-%m-%d"),
                chart_suptitle=suptitle,
                df_birds=dataframe,
                now=now,
                time_unit='Year',
                period_col='Period',
                xlabel='semi-monthly detections',
                xtick_labels=month_labels
            )

        if daemon:
            sleep(60 * sleep_m)
        else:
            break

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', action='store_true')
    parser.add_argument('--sleep', default=2, type=int, help='Time between runs (minutes)')
    args = parser.parse_args()
    main(args.daemon, args.sleep)
