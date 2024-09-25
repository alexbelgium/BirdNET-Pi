#===============================================================================
#=== daily_plot.py (adjusted version @jmtmp) ==========================================
#===============================================================================
#=== 2024-04-19: new version
#=== 2024-04-28: new custom formatting for millions (my_int_fmt function)
#===             new formatting of total occurence in semi-monthly plot
#=== 2024-09-01: updated suptitle and xlabels formatting
#=== 2024-09-05: Daemon implementing
#===============================================================================

import argparse
import sqlite3
import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.font_manager as font_manager
from matplotlib import rcParams
from matplotlib.colors import LogNorm
from matplotlib.colors import TwoSlopeNorm
from matplotlib.ticker import FormatStrFormatter
from datetime import datetime
from time import sleep
from utils.helpers import DB_PATH, get_settings



def load_fonts():
    # Add every font at the specified location
    font_dir = [os.path.expanduser('~/BirdNET-Pi/homepage/static')]
    for font in font_manager.findSystemFonts(font_dir, fontext='ttf'):
        font_manager.fontManager.addfont(font)
    # Set font family globally
    lang = get_settings()['DATABASE_LANG']
    if lang in ['ja', 'zh']:
        rcParams['font.family'] = 'Noto Sans JP'
    elif lang == 'th':
        rcParams['font.family'] = 'Noto Sans Thai'
    else:
        rcParams['font.family'] = 'Roboto Flex'

 
def my_int_fmt(numberstr, converthundreds=False):
    ret_str = numberstr
    if isinstance(numberstr, str):                          #parameter is string
        if numberstr.isnumeric():                          #parameter is integer
            number = int(numberstr)
            if (number >= 9500000):                                    #millions
                ret_str = str(round(number/1000000)) + 'M'
            elif (number >= 950):                                     #thousands
                ret_str = str(round(number/1000)) + 'k'
            elif converthundreds and (number>=100):                    #hundreds
                ret_str = '.' + str(round(number/100)) + 'k'               
    return ret_str

def clr_plot_facecolor():
    # Update colors according to color scheme
    if get_settings()['COLOR_SCHEME'] == "dark":
        return 'darkgrey'
    else:
        return 'none' 
        
def clr_current_ticklabel():
    # Update colors according to color scheme
    if get_settings()['COLOR_SCHEME'] == "dark":
        return 'white'
    else:
        return 'red'          
  
def my_heatmap(axis, crosstable, clrmap, clrnorm, annotfmt='', annotsize='medium'):
    #annotsize: float or {'xx-small', 'x-small', 'small', 'medium', 'large', 'x-large', 'xx-large'}
    hm_axes = sns.heatmap(crosstable, cmap=clrmap, norm=clrnorm, cbar=False, linewidths=0.5, linecolor="Silver", ax=axis, annot=(annotfmt != ''), fmt=annotfmt, annot_kws={"fontsize": annotsize})
    #set border
    for _, spine in hm_axes.spines.items(): spine.set_visible(True)
    return hm_axes

def get_daily_plot_data(conn, now):
    sql_fields = "COUNT(DISTINCT Com_Name) as Species, COUNT(Com_Name) as Detections, COUNT(DISTINCT Date) as Days"
    db_entire = pd.read_sql_query("SELECT " + sql_fields + " FROM detections", conn)
    db_today  = pd.read_sql_query("SELECT " + sql_fields + " FROM detections WHERE Date = DATE('now')", conn)
    # prepare suptitle  
    avg_daily_detections = round(int(db_entire.Detections[0])/int(db_entire.Days[0]))
    plot_suptitle  = "Hourly overview updated at " + now.strftime("%Y-%m-%d %H:%M:%S") + "\n"
    plot_suptitle += "(" + str(db_today.Species[0]) + " species today, " + str(db_entire.Species[0]) + " in total;  "
    plot_suptitle += str(db_today.Detections[0]) + " detections today, " + str(avg_daily_detections) + " on average)" 
    # prepare dataset
    sql = "SELECT Date, abs(strftime('%H',Time)) as Hour, Com_Name as Bird, count(Com_Name) as Count, Max(Confidence) as Conf \
           FROM detections WHERE Date = DATE('now', 'localtime') GROUP BY Hour, Bird"
    plot_dataframe = pd.read_sql_query(sql, conn)   
    return  plot_suptitle, plot_dataframe
    
def create_daily_plot(chart_name, chart_suptitle, df_birds, now):  
    #=== Set up all needed dataframes ==========================================
    # Order birds according to occurrence and confidence
    df_birds_summary = df_birds.groupby('Bird').agg({'Count': 'sum', 'Conf': 'max'})
    df_birds_ordered = df_birds_summary.sort_values(by=['Count','Conf'], ascending=[False, False])
    df_birds['Bird'] = pd.Categorical(df_birds['Bird'], ordered=True, categories=df_birds_ordered.index)
    # Count birds and recordings; empty dataset raises an exception      
    no_of_rows = df_birds_summary.shape[0]
    total_recordings = df_birds['Count'].sum()     
    if no_of_rows == 0: exit(0)  
    # Prepare crosstables
    df_confidences = pd.crosstab(index=df_birds['Bird'], columns=df_birds['Date'], values=df_birds['Conf'],  aggfunc='max')
    df_detections  = pd.crosstab(index=df_birds['Bird'], columns=df_birds['Date'], values=df_birds['Count'], aggfunc='sum')
    df_perioddata  = pd.crosstab(index=df_birds['Bird'], columns=df_birds['Hour'], values=df_birds['Count'], aggfunc='sum')
    # Prepare frametable matrix for hourly occurrence (24 columns)
    df_empty_matrix = pd.DataFrame(data=0, index=df_perioddata.index, columns=pd.Series(data=range(0, 24)))
    # Agregate prepared matrix with data (fill empty periods by zeros)
    df_perioddata = (df_empty_matrix + df_perioddata).fillna(0)  
    #=== Set up plot and all subplots ========================================== 
    set_toplabels = False                                                       # Not yet done: when true size of table has to be changed
    # Color palletes
    cmap_confi = 'Greys'  # Changed from PiYG to Greys
    cmap_count = 'Greys'  # Changed from Blues to Greys
    norm_confi = TwoSlopeNorm(vmin=0.25, vmax=1.25, vcenter=0.75)               # Fake min and max due to nice colors
    norm_count = LogNorm(vmin=1, vmax=total_recordings)                         # Color mapping/normalization must be reinitialised
    # Plot dimensions (in inches at default 100dpi or as percentage)
    row_height = 0.28                                                           # 28dots
    fig_height = row_height * (no_of_rows + 4)                                  # 4 rows for suptitle, xticklabels and xlabel
    row_space = row_height / fig_height                                         # row heigh as a plot percentage    
    # Plot setup
    f, axs = plt.subplots(1, 4, figsize=(10, fig_height), width_ratios=[5, 2, 2, 18], facecolor=clr_plot_facecolor())
    plt.subplots_adjust(left=0.02, right=0.98, top=(1 - 2*row_space), bottom=(0 + 2*row_space), wspace=0, hspace=0)
    plt.suptitle(chart_suptitle, y=0.99)
    # Bird name column (labels goes from confidence columns)
    axs[0].clear()  # Make sure the axis is clear to avoid overlapping text
    axs[0].set_xlim(0, 1)
    axs[0].set_ylim(0, len(df_confidences.index))
#    axs[0].axis('off')
    axs[0].set(xlabel=None, ylabel=None) 
    axs[0].set_xlabel('updated at\n'+now.strftime("%Y-%m-%d %H:%M:%S"), labelpad=7, loc='left')
    # Confidence column
    hm_confi = my_heatmap(axs[1], df_confidences, cmap_confi, norm_confi, annotfmt=".0%")
    hm_confi.tick_params(bottom=True, left=False, labelbottom=True, labeltop=set_toplabels, labelleft=True, labelrotation=0)
    hm_confi.set(xlabel=None, ylabel=None, xticklabels=['max\nconfidence'])  
    # Occurrence column
    hm_count = my_heatmap(axs[2], df_detections, cmap_count, norm_count, annotfmt="g")
    hm_count.tick_params(bottom=True, left=False, labelbottom=True, labeltop=set_toplabels, labelleft=False)
    hm_count.set(xlabel=None, ylabel=None, xticklabels=['total\ndetections'])
    # Occurrence heatmap
    hm_data = my_heatmap(axs[3], df_perioddata, cmap_count, norm_count, annotfmt="g", annotsize=9)
    hm_data.tick_params(bottom=True, top=set_toplabels, left=False, labelbottom=True, labeltop=set_toplabels, labelleft=False, labelrotation=0)
    hm_data.set(xlabel=None, ylabel=None)
    hm_data.set_xlabel('hourly detections', labelpad=1)
    hm_data.xaxis.set_major_formatter(FormatStrFormatter('%d'))
    # Apply custom annotation format
    for t in hm_data.texts:
        if len(t.get_text())>3: t.set_text(my_int_fmt(t.get_text()))
    # Set tick label for current hour
    for label in hm_data.get_xticklabels():
        if int(label.get_text()) == now.hour: label.set_color(clr_current_ticklabel())
    #=== Save combined plot ====================================================
    plt.savefig(os.path.expanduser('~/BirdSongs/Extracted/Charts/' + chart_name + '.png'))
    plt.show()
    plt.close()


def get_yearly_plot_data(conn, now):
    sql_fields = "COUNT(DISTINCT Com_Name) as Species, COUNT(Com_Name) as Detections, COUNT(DISTINCT Date) as Days"
    db_entire = pd.read_sql_query("SELECT " + sql_fields + " FROM detections", conn)
    db_ytd    = pd.read_sql_query("SELECT " + sql_fields + " FROM detections WHERE Date >= date('now','start of year')", conn)
    # prepare suptitle  
    plot_suptitle  = "Semi-monthly overview updated at " + now.strftime("%Y-%m-%d %H:%M:%S") + "   (" 
    plot_suptitle += str(db_ytd.Species[0]) + " species this year, " + str(db_entire.Species[0]) + " in total)"
    # prepare dataset   
    sql = "SELECT 2*(strftime('%m',Date)-1) + iif( abs(strftime('%d',Date))<16, 0, 1) as Period,             \
           strftime('%Y', Date) as Year, Com_Name as Bird, count(Com_Name) as Count, Max(Confidence) as Conf \
           FROM detections WHERE Date >= date('now','start of year') GROUP BY Period, Bird"    
    plot_dataframe = pd.read_sql_query(sql, conn)   
    return  plot_suptitle, plot_dataframe


def create_yearly_plot(chart_name, chart_suptitle, df_birds, now):
    #=== Set up all needed dataframes ==========================================
    # Order birds according to occurrence and confidence
    df_birds_summary = df_birds.groupby('Bird').agg({'Count': 'sum', 'Conf': 'max'})
    df_birds_ordered = df_birds_summary.sort_values(by=['Count','Conf'], ascending=[False, False])
    df_birds['Bird'] = pd.Categorical(df_birds['Bird'], ordered=True, categories=df_birds_ordered.index)
    # Prepare crosstables
    df_confidences = pd.crosstab(index=df_birds['Bird'], columns=df_birds['Year'], values=df_birds['Conf'], aggfunc='max')
    df_detections  = pd.crosstab(index=df_birds['Bird'], columns=df_birds['Year'], values=df_birds['Count'], aggfunc='sum')
    df_perioddata  = pd.crosstab(index=df_birds['Bird'], columns=df_birds['Period'], values=df_birds['Count'], aggfunc='sum')
    # Prepare matrix for semi-monthly occurrence (24 columns)
    df_empty_matrix = pd.DataFrame(data=0, index=df_perioddata.index, columns=pd.Series(data=range(0, 24)))
    # Agregate prepared matrix with data (fill empty periods by zeros)
    df_perioddata = (df_empty_matrix + df_perioddata).fillna(0)  
    # Count birds and recordings; empty dataset raises an exception      
    no_of_rows = df_birds_summary.shape[0]
    total_recordings = df_birds['Count'].sum()     
    if no_of_rows == 0: exit(0)         
    #=== Set up plot and all subplots ==========================================
    set_toplabels = False                                                       # Neni hotovo: pokud True budu muset pridat radky
    # Color palletes
    cmap_confi = 'PiYG'
    cmap_count = 'Blues'
    norm_confi = TwoSlopeNorm(vmin=0.25, vmax=1.25, vcenter=0.75)               # Fake min and max due to the color
    norm_count = LogNorm(vmin=1, vmax=total_recordings)                         # Color mapping/normalization must be reinitialised
    # Plot dimensions (in inches at default 100dpi or as percentage)
    row_height = 0.28                                                           # 28dots
    fig_height = row_height * (no_of_rows + 4)                                  # 4 rows for suptitle, xticklabels and xlabel
    row_space  = row_height / fig_height                                        # row heigh as a plot percentage
    # Plot setup 
    f, axs = plt.subplots(1, 4, figsize=(10, fig_height), width_ratios=[5, 2, 2, 18], facecolor=clr_plot_facecolor())
    plt.subplots_adjust(left=0.02, right=0.98, top=(1 - 2*row_space), bottom=(0 + 2*row_space), wspace=0, hspace=0)
    plt.suptitle(chart_suptitle, y=(1 - row_space))
    # Bird name column (labels goes from confidence columns)
    hm_name = my_heatmap(axs[0], df_confidences, cmap_confi, norm_confi)
    hm_name.tick_params(bottom=False, left=False, labelbottom=False, labelleft=False) 
    hm_name.set(xlabel=None, ylabel=None)
    hm_name.set_xlabel('updated at\n'+now.strftime("%Y-%m-%d %H:%M:%S"), labelpad=7, loc='left')   
    # Confidence column
    hm_confi = my_heatmap(axs[1], df_confidences, cmap_confi, norm_confi, annotfmt=".0%")  
    hm_confi.tick_params(bottom=True, left=False, labelbottom=True, labeltop=set_toplabels, labelleft=True, labelrotation=0)     
    hm_confi.set(xlabel=None, ylabel=None, xticklabels=['max\nconfidence'])  
    # Occurrence column
    hm_count = my_heatmap(axs[2], df_detections, cmap_count, norm_count, annotfmt="g")
    hm_count.tick_params(bottom=True, left=False, labelbottom=True, labeltop=set_toplabels, labelleft=False)
    hm_count.set(xlabel=None, ylabel=None, xticklabels=['total\ndetections'])
    # Apply custom annotation format
    for t in hm_count.texts:
        if len(t.get_text())>3: t.set_text(my_int_fmt(t.get_text())) 
    # Occurrence heatmap
    hm_data = my_heatmap(axs[3], df_perioddata, cmap_count, norm_count, annotfmt="g", annotsize=9)
    hm_data.tick_params(bottom=True, top=set_toplabels, left=False, labelbottom=True, labeltop=set_toplabels, labelleft=False, labelrotation=0)    #labelsize=16
    hm_data.set(xlabel=None, ylabel=None)
    hm_data.set_xlabel('semi-monthly detections', labelpad=1)
    hm_data.set_xticklabels(['Jan','','Feb','','Mar','','Apr','','May','','Jun','','Jul','','Aug','','Sep','','Oct','','Nov','','Dec',''])
    # Apply custom annotation format
    for t in hm_data.texts:
        if len(t.get_text())>2: t.set_text(my_int_fmt(t.get_text(), converthundreds=True))
    # Set tick label for current period
    for label in hm_data.get_xticklabels():
        if label.get_text() == now.strftime('%b'): label.set_color(clr_current_ticklabel())
    #=== Set combined plot layout and titles and save ==========================
    plt.savefig(os.path.expanduser('~/BirdSongs/Extracted/Charts/' + chart_name + '.png'))
    plt.show()
    plt.close()     
                  
#=== MAIN ======================================================================

def main(daemon, sleep_m):
    load_fonts()
    while True:
        conn = sqlite3.connect(DB_PATH) 
        now = datetime.now() 
        suptitle, dataframe = get_daily_plot_data(conn, now)                   
        create_daily_plot('Combo-'+now.strftime("%Y-%m-%d"), suptitle, dataframe, now)  
        suptitle, dataframe = get_yearly_plot_data(conn, now)
        create_yearly_plot('Combo2-'+now.strftime("%Y-%m-%d"), suptitle, dataframe, now)                
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


