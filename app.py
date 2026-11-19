# -*- coding: utf-8 -*-
# Original Code: Jorge Gomes 
# Optimization: João Pina 
#               Micael Carvalho

# ------------------------------
#       DESCRIPTION
# ------------------------------

# This app scrapes information from IPMA and generates an image
# The image is to be shared automatically on social media 

# ------------------------------
#       IMPORT LIBRARIES
# ------------------------------

import requests
import pandas as pd
import regex as re
import json
import time
import sys
import logging

from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageFont, ImageDraw 

# Configure logger
logger = logging.getLogger(__name__)

# ---------------------------------------
#    GET DATA AND GENERATE DATAFRAMES
# ----------------------------------------

# Define URL 

URL_IPMA_DAILY = 'https://www.ipma.pt/pt/otempo/obs.superficie/table-top-stations-all.jsp'
URL_BOT_FOGOS = 'https://bot.fogos.pt/ipma.php'

# Headers to reduce Cloudflare bot blocking
HEADERS = {
    "User-Agent": "VostPTExtremosMeteo/1.0 (DailyWeatherReport; +https://github.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_daily_observations(url):
    """
    Fetch IPMA's official daily station summaries embedded in the page as
    `var observations = {...};`. Returns {date: {stationId: {temp_max, ...}}}.
    """
    logger.info(f"Fetching from {url}")
    page = requests.get(url, headers=HEADERS, timeout=60)
    if page.status_code == 429:
        raise RuntimeError("Rate limited (429)")
    if "Access denied" in page.text and "Cloudflare" in page.text:
        raise RuntimeError("Cloudflare blocked")
    page.raise_for_status()
    search = re.search(r'var observations = (.*?);', page.text, re.DOTALL)
    if not search:
        raise RuntimeError("Observations not found in page")
    return json.loads(search.group(1))


def fetch_observations_data(yesterday_date):
    """
    Fetch IPMA daily observations. Uses the IPMA page directly first and
    bot.fogos.pt (a proxy of the same page) as fallback.

    The hourly api.ipma.pt endpoint is deliberately not used: it only covers
    the last 24 hours, so yesterday's extremes computed from it miss the
    early-morning hours and gusts/precipitation totals are wrong.
    """
    for url in (URL_IPMA_DAILY, URL_BOT_FOGOS):
        try:
            data = fetch_daily_observations(url)
        except Exception as e:
            logger.warning(f"{url} failed: {e}")
            continue
        if yesterday_date in data:
            logger.info(f"Using data from {url}")
            return data
        logger.warning(f"{url} has no data for {yesterday_date} yet")

    raise RuntimeError(f"Could not fetch daily weather data for {yesterday_date} from any source.")


# Check yesterday's date early (needed for IPMA fallback)
yesterday = datetime.now() - timedelta(1)
yesterday_date = datetime.strftime(yesterday, '%Y-%m-%d')

locks_dir = Path("locks")
locks_dir.mkdir(exist_ok=True)

# Delete old lock files
for old_lock in locks_dir.glob("generated_*.lock"):
    if yesterday_date not in old_lock.name:
        old_lock.unlink()

# Today's lock file
lock_file = locks_dir / f"generated_{yesterday_date}.lock"

# Skip if already generated
if lock_file.exists():
    print(f"Report for {yesterday_date} already generated. Skipping.")
    sys.exit(0)

# Fetch data (IPMA page or bot.fogos.pt fallback)
json_data = fetch_observations_data(yesterday_date)

print(f"Fetched data for {len(json_data)} dates")

# Create Dataframe from json data

ipma_data = pd.concat({k: pd.DataFrame(v).T for k, v in json_data.items()}, axis=0).reset_index()

ipma_data.to_csv("check.csv")

#print (ipma_data.info())
# Rename resulting level_x columns

ipma_data = ipma_data.rename(columns={'level_0': 'date','level_1':'stationId'})

#print (ipma_data.info())

# Sort dataframe by date 

ipma_data = ipma_data.sort_values(by=['date'])

report_date = str(yesterday_date)

print(report_date)

# Create new datafraeme with only yesterday's results

ipma_data_yesterday = ipma_data[ipma_data['date'] == yesterday_date].copy()

#print (ipma_data_yesterday.info())


# Fetch all stations once (one request per station was slow and timeouts
# silently dropped stations from the report)
URL_STATIONS = "https://api.fogos.pt/v2/weather/stations"


def fetch_stations():
    for attempt in range(1, 4):
        try:
            response = requests.get(URL_STATIONS, headers=HEADERS, timeout=60)
            response.raise_for_status()
            # Newer stations carry the IPMA id in `stationId` (`id` is the DB id)
            return {
                str(st.get("stationId", st.get("id"))): st
                for st in response.json()
            }
        except Exception as e:
            logger.warning(f"Stations request failed (attempt {attempt}/3): {e}")
            time.sleep(10 * attempt)
    raise RuntimeError(f"Could not fetch stations from {URL_STATIONS}")


stations = fetch_stations()
logger.info(f"Loaded {len(stations)} stations")


# Define function to fetch stationId's name
def getStationNameById(id):
    station = stations.get(str(id))
    if station is None:
        logger.error(f"Station ID {id} not found in {URL_STATIONS}")
        return None
    return pd.json_normalize(station)

# Create empty list for territory
territory = []

# Get max records on dataframe
max_records = len(ipma_data_yesterday)

# Add logging for dataframe info
logger.info(f"Processing {max_records} records from {yesterday_date}")
logger.info(f"Sample station IDs: {ipma_data_yesterday['stationId'].head().tolist()}")

# Get territory for each station on the Dataframe 
for x in range(max_records):
    info = getStationNameById(ipma_data_yesterday.iloc[x].stationId)
    if info is None:
        logger.warning(f"Could not get info for station {ipma_data_yesterday.iloc[x].stationId}, skipping...")
        territory.append("Unknown")  # Add placeholder instead of skipping
    else:
        region = info.place.values[0]
        territory.append(region)

# Create new column called "territory" using the list generated above 
ipma_data_yesterday['territory'] = territory

# Filter out unknown territories before creating specific dataframes
ipma_data_yesterday = ipma_data_yesterday[ipma_data_yesterday.territory != "Unknown"]

# Create dataframe for Madeira's values from yesterday 
df_madeira_yesterday = ipma_data_yesterday[ipma_data_yesterday.territory == "Madeira"]

# Create dataframe for Azores's values from yesterday 
df_azores_yesterday = ipma_data_yesterday[ipma_data_yesterday.territory == "Açores"]

# Create dataframe for Portugal's values from yesterday 
df_portugal_yesterday = ipma_data_yesterday[ipma_data_yesterday.territory == "Portugal"]


# -----------------------------------
#       DEFINE MAX TEMP, 
# MIN TEMP, MAX GUST, AND RAIN ACCU
#       FOR ALL TERRITORIES
# -----------------------------------

# Max Temperatures 
# Create Dataframe based on yesterday's data, sorting maximum temperature and extracting top 4 values

four_temp_max_mad = df_madeira_yesterday.sort_values(by=['temp_max'],ascending=False).head(4)
four_temp_max_az = df_azores_yesterday.sort_values(by=['temp_max'],ascending=False).head(4)
four_temp_max_pt = df_portugal_yesterday.sort_values(by=['temp_max'],ascending=False).head(4)

# Min Temperatures
# Create Dataframes based on yesterday's data, sorting by minimum temperature

four_temp_min_mad  = df_madeira_yesterday.sort_values(by=['temp_min'],ascending=True)
four_temp_min_az = df_azores_yesterday.sort_values(by=['temp_min'],ascending=True)
four_temp_min_pt = df_portugal_yesterday.sort_values(by=['temp_min'],ascending=True)
# Drop all -99.0 values, since those are IPMA's way of saying station is fucked up or not working or somehting
# (Yes!Really!)
# and keep top four results
four_temp_min_mad = four_temp_min_mad[four_temp_min_mad.temp_min != -99.0].head(4)
four_temp_min_az = four_temp_min_az[four_temp_min_az.temp_min != -99.0].head(4)
four_temp_min_pt = four_temp_min_pt[four_temp_min_pt.temp_min != -99.0].head(4)

# Max Wind Gust 
# Create Dataframes based on yesterday's data, sorting by maximum wind gust
four_wind_max_mad = df_madeira_yesterday.sort_values(by=['vento_int_max_inst'],ascending=False).head(4)
four_wind_max_az = df_azores_yesterday.sort_values(by=['vento_int_max_inst'],ascending=False).head(4)
four_wind_max_pt = df_portugal_yesterday.sort_values(by=['vento_int_max_inst'],ascending=False).head(4)

# Max rain accumulated
# Create Dataframes based on yesterday's data, sorting by maximum accumulated rain
four_rain_accu_mad = df_madeira_yesterday.sort_values(by=['prec_quant'],ascending=False).head(4)
four_rain_accu_az = df_azores_yesterday.sort_values(by=['prec_quant'],ascending=False).head(4)
four_rain_accu_pt = df_portugal_yesterday.sort_values(by=['prec_quant'],ascending=False).head(4)

# Humidity Min 
four_hum_min_mad  = df_madeira_yesterday.sort_values(by=['hum_min'],ascending=True)
four_hum_min_az = df_azores_yesterday.sort_values(by=['hum_min'],ascending=True)
four_hum_min_pt = df_portugal_yesterday.sort_values(by=['hum_min'],ascending=True)

four_hum_min_mad = four_hum_min_mad[four_hum_min_mad.hum_min != -99.0].head(4)
four_hum_min_az = four_hum_min_az[four_hum_min_az.hum_min != -99.0].head(4)
four_hum_min_pt = four_hum_min_pt[four_hum_min_pt.hum_min != -99.0].head(4)

# Humidity Max
four_hum_max_mad  = df_madeira_yesterday.sort_values(by=['hum_max'],ascending=False)
four_hum_max_az = df_azores_yesterday.sort_values(by=['hum_max'],ascending=False)
four_hum_max_pt = df_portugal_yesterday.sort_values(by=['hum_max'],ascending=False)

four_hum_max_mad = four_hum_max_mad[four_hum_max_mad.hum_max != -99.0].head(4)
four_hum_max_az = four_hum_max_az[four_hum_max_az.hum_max != -99.0].head(4)
four_hum_max_pt = four_hum_max_pt[four_hum_max_pt.hum_max != -99.0].head(4)


# ----------------------------------
#       THERMAL AMPLITUDES
# -----------------------------------

# Create a copy of the dataframes
df_amplitude_pt = df_portugal_yesterday
df_amplitude_az = df_azores_yesterday
df_amplitude_mad = df_madeira_yesterday

# Drop -99 values from all dataframes
df_amplitude_pt=df_amplitude_pt[df_amplitude_pt.temp_min != -99.0]
df_amplitude_pt=df_amplitude_pt[df_amplitude_pt.temp_max != -99.0]
df_amplitude_az=df_amplitude_az[df_amplitude_az.temp_min != -99.0]
df_amplitude_az=df_amplitude_az[df_amplitude_az.temp_max != -99.0]
df_amplitude_mad=df_amplitude_mad[df_amplitude_mad.temp_min != -99.0]
df_amplitude_mad=df_amplitude_mad[df_amplitude_mad.temp_max != -99.0]


# Create Amplitude Column for each dataframe
df_amplitude_pt['amplitude']=df_amplitude_pt.temp_max - df_amplitude_pt.temp_min
df_amplitude_az['amplitude']=df_amplitude_az.temp_max - df_amplitude_az.temp_min
df_amplitude_mad['amplitude']=df_amplitude_mad.temp_max - df_amplitude_mad.temp_min

# Sort Dataframe by amplitude and filter forthe the top record
df_amplitude_pt = df_amplitude_pt.sort_values(by=['amplitude'],ascending=False).head(1)
df_amplitude_az = df_amplitude_az.sort_values(by=['amplitude'],ascending=False).head(1)
df_amplitude_mad = df_amplitude_mad.sort_values(by=['amplitude'],ascending=False).head(1)


# ----------------------------------
#       ADDING COLORS TO DATAFRAMES
# -----------------------------------

# Create Colors Lists 

colors_temp_max = [(154,7,7),(144,37,37),(134,67,67),(124,97,97)]
colors_temp_min = [(89,165,222),(89,165,222),(107,176,226),(141,195,233)]
colors_hum_max = [(89,165,222),(89,165,222),(107,176,226),(141,195,233)]
colors_hum_min = [(154,7,7),(234,9,9),(240,157,57),(239,129,129)]
colors_wind_max = [(89,133,187),(122,160,210),(147,179,224),(189,208,234)]
colors_rain_max = [(112,121,164),(138,147,189),(163,175,213),(185,194,226)]

# Attach colors, tolerating regions/metrics with fewer than the expected
# number of valid stations (e.g. after IPMA's -99.0 invalid readings are
# filtered out), so a sparse day degrades gracefully instead of crashing.
def add_colors(df, colors):
    if len(df) < len(colors):
        logger.warning(
            "Only %d station(s) available where %d were expected; rendering available data.",
            len(df), len(colors),
        )
    df.loc[:,'colors'] = pd.Series(colors[:len(df)]).values
    return df


# Max Temperature Colors

four_temp_max_mad = add_colors(four_temp_max_mad, colors_temp_max)
four_temp_max_az = add_colors(four_temp_max_az, colors_temp_max)
four_temp_max_pt = add_colors(four_temp_max_pt, colors_temp_max)

# Min Temperature Colors

four_temp_min_mad = add_colors(four_temp_min_mad, colors_temp_min)
four_temp_min_az = add_colors(four_temp_min_az, colors_temp_min)
four_temp_min_pt = add_colors(four_temp_min_pt, colors_temp_min)


# Max Rainfall 

four_rain_accu_mad = add_colors(four_rain_accu_mad, colors_rain_max)
four_rain_accu_az = add_colors(four_rain_accu_az, colors_rain_max)
four_rain_accu_pt = add_colors(four_rain_accu_pt, colors_rain_max)


# Max Wind Gust 

four_wind_max_mad = add_colors(four_wind_max_mad, colors_wind_max)
four_wind_max_az = add_colors(four_wind_max_az, colors_wind_max)
four_wind_max_pt = add_colors(four_wind_max_pt, colors_wind_max)

# Mazimum Humidity

four_hum_max_mad = add_colors(four_hum_max_mad, colors_hum_max)
four_hum_max_az = add_colors(four_hum_max_az, colors_hum_max)
four_hum_max_pt = add_colors(four_hum_max_pt, colors_hum_max)

# Min Humidity
four_hum_min_mad = add_colors(four_hum_min_mad, colors_hum_min)
four_hum_min_az = add_colors(four_hum_min_az, colors_hum_min)
four_hum_min_pt = add_colors(four_hum_min_pt, colors_hum_min)


# ------------------------------
#       IMAGE MANIPULATION 
# ------------------------------


# Load Base Images
template_pt = Image.open("resumo_meteo_template_pt.png")
template_az = Image.open("resumo_meteo_template_az.png")
template_mad = Image.open("resumo_meteo_template_mad.png")

# Define Font and Size
# Font file needs to be in the same folder
title_font = ImageFont.truetype('Lato-Bold.ttf', 24)
subtitle_font = ImageFont.truetype('Lato-Bold.ttf', 22)
date_font = ImageFont.truetype('Lato-Bold.ttf', 24)
amplitude_font =ImageFont.truetype('Lato-Bold.ttf',72)
location_font =ImageFont.truetype('Lato-Bold.ttf',14)

# Create copies of the images that can be edited
image_editable_pt = ImageDraw.Draw(template_pt)
image_editable_az = ImageDraw.Draw(template_az)
image_editable_mad = ImageDraw.Draw(template_mad)


# Create vars for coordinates

# Right Column 

max_temp_start_coords = 190 # This value increments by 30px every loop iteration
max_temp_station_name_x = 115  # Where Station Name Appears 
max_temp_value_x = 460  # Where Value Appears 

min_temp_start_coords = 370 # This value increments by 30px every loop iteration
min_temp_station_name_x = 115  # Where Station Name Appears 
min_temp_value_x = 460  # Where Value Appears 

max_rain_start_coords = 540 # This value increments by 30px every loop iteration
max_rain_station_name_x = 115  # Where Station Name Appears 
max_rain_value_x = 460  # Where Value Appears 

max_wind_start_coords = 720 # This value increments by 30px every loop iteration
max_wind_station_name_x = 115  # Where Station Name Appears 
max_wind_value_x = 460  # Where Value Appears 


# Left Column 

max_hum_start_coords = 190 # This value increments by 30px every loop iteration
max_hum_station_name_x = 650  # WHere Station Name Appears 
max_hum_value_x = 950  # Where Value Appears 
max_hum_unit_x = 970    # Where Unit Appears 

min_hum_start_coords = 370 # This value increments by 30px every loop iteration
min_hum_station_name_x = 650  # WHere Station Name Appears 
min_hum_value_x = 950  # Where Value Appears 
min_hum_unit_x = 970    # Where Unit Appears 




# ------------------------------
#     PORTUGAL CONTINENTAL
# ------------------------------


# Create Loop For Max Temperature 
for x in range(len(four_temp_max_pt)):
    name = getStationNameById(four_temp_max_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_temp_max_pt.iloc[x].temp_max)
    color = four_temp_max_pt.iloc[x].colors
    image_editable_pt.text((max_temp_station_name_x,max_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((max_temp_value_x, max_temp_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_temp_start_coords += 30
 
 # Create Loop For Min Temperature 
for x in range(len(four_temp_min_pt)):
    name = getStationNameById(four_temp_min_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_temp_min_pt.iloc[x].temp_min)
    color = four_temp_min_pt.iloc[x].colors
    image_editable_pt.text((min_temp_station_name_x,min_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((min_temp_value_x, min_temp_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    min_temp_start_coords += 30  

# Create Loop For Max Rainfall 
for x in range(len(four_rain_accu_pt)):
    name = getStationNameById(four_rain_accu_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_rain_accu_pt.iloc[x].prec_quant)
    color = four_rain_accu_pt.iloc[x].colors
    image_editable_pt.text((max_rain_station_name_x,max_rain_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((max_rain_value_x, max_rain_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_rain_start_coords += 30

# Create Loop For Max Wind Gust
for x in range(len(four_wind_max_pt)):
    name = getStationNameById(four_wind_max_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_wind_max_pt.iloc[x].vento_int_max_inst)
    color = four_wind_max_pt.iloc[x].colors
    image_editable_pt.text((max_wind_station_name_x,max_wind_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((max_wind_value_x, max_wind_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_wind_start_coords += 30

# Create Loop for Max Humidity 
for x in range(len(four_hum_max_pt)):
    name = getStationNameById(four_hum_max_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_hum_max_pt.iloc[x].hum_max)
    color = four_hum_max_pt.iloc[x].colors
    image_editable_pt.text((max_hum_station_name_x,max_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((max_hum_value_x, max_hum_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_hum_start_coords += 30

# Create Loop for Min Humidity 
for x in range(len(four_hum_min_pt)):
    name = getStationNameById(four_hum_min_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_hum_min_pt.iloc[x].hum_min)
    color = four_hum_min_pt.iloc[x].colors
    image_editable_pt.text((min_hum_station_name_x,min_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((min_hum_value_x, min_hum_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    min_hum_start_coords += 30

# Create Loop for Ampitude
for x in range(len(df_amplitude_pt)):
    name = getStationNameById(df_amplitude_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp_max = str(df_amplitude_pt.iloc[x].temp_max)
    station_temp_min = str(df_amplitude_pt.iloc[x].temp_min)
    station_temp_amplitude = str(round(df_amplitude_pt.iloc[x].amplitude,2))
    image_editable_pt.text((842,525), station_name,(0,0,0), font=location_font)
    image_editable_pt.text((920,570), station_temp_max,(154,7,7), font=subtitle_font)
    image_editable_pt.text((683,570), station_temp_min,(93,173,236), font=subtitle_font)
    image_editable_pt.text((755,600), station_temp_amplitude,(250,186,61), font=amplitude_font)


# ------------------------------
#           AÇORES
# ------------------------------

# Reset Coordinates

# Right Column 

max_temp_start_coords = 190 # This value increments by 30px every loop iteration
max_temp_station_name_x = 115  # Where Station Name Appears 
max_temp_value_x = 460  # Where Value Appears 

min_temp_start_coords = 370 # This value increments by 30px every loop iteration
min_temp_station_name_x = 115  # Where Station Name Appears 
min_temp_value_x = 460  # Where Value Appears 

max_rain_start_coords = 540 # This value increments by 30px every loop iteration
max_rain_station_name_x = 115  # Where Station Name Appears 
max_rain_value_x = 460  # Where Value Appears 

max_wind_start_coords = 720 # This value increments by 30px every loop iteration
max_wind_station_name_x = 115  # Where Station Name Appears 
max_wind_value_x = 460  # Where Value Appears 


# Left Column 

max_hum_start_coords = 190 # This value increments by 30px every loop iteration
max_hum_station_name_x = 650  # WHere Station Name Appears 
max_hum_value_x = 950  # Where Value Appears 
max_hum_unit_x = 970    # Where Unit Appears 

min_hum_start_coords = 370 # This value increments by 30px every loop iteration
min_hum_station_name_x = 650  # WHere Station Name Appears 
min_hum_value_x = 950  # Where Value Appears 
min_hum_unit_x = 970    # Where Unit Appears 

# Create Loop For Max Temperature 
for x in range(len(four_temp_max_az)):
    name = getStationNameById(four_temp_max_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_temp_max_az.iloc[x].temp_max)
    color = four_temp_max_az.iloc[x].colors
    image_editable_az.text((max_temp_station_name_x,max_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((max_temp_value_x, max_temp_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_temp_start_coords += 30
 
 # Create Loop For Min Temperature 
for x in range(len(four_temp_min_az)):
    name = getStationNameById(four_temp_min_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_temp_min_az.iloc[x].temp_min)
    color = four_temp_min_az.iloc[x].colors
    image_editable_az.text((min_temp_station_name_x,min_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((min_temp_value_x, min_temp_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    min_temp_start_coords += 30  

# Create Loop For Max Rainfall 
for x in range(len(four_rain_accu_az)):
    name = getStationNameById(four_rain_accu_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_rain_accu_az.iloc[x].prec_quant)
    color = four_rain_accu_az.iloc[x].colors
    image_editable_az.text((max_rain_station_name_x,max_rain_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((max_rain_value_x, max_rain_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_rain_start_coords += 30

# Create Loop For Max Wind Gust
for x in range(len(four_wind_max_az)):
    name = getStationNameById(four_wind_max_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_wind_max_az.iloc[x].vento_int_max_inst)
    color = four_wind_max_az.iloc[x].colors
    image_editable_az.text((max_wind_station_name_x,max_wind_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((max_wind_value_x, max_wind_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_wind_start_coords += 30

# Create Loop for Max Humidity 
for x in range(len(four_hum_max_az)):
    name = getStationNameById(four_hum_max_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_hum_max_az.iloc[x].hum_max)
    color = four_hum_max_az.iloc[x].colors
    image_editable_az.text((max_hum_station_name_x,max_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((max_hum_value_x, max_hum_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_hum_start_coords += 30

# Create Loop for Min Humidity 
for x in range(len(four_hum_min_az)):
    name = getStationNameById(four_hum_min_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_hum_min_az.iloc[x].hum_min)
    color = four_hum_min_az.iloc[x].colors
    image_editable_az.text((min_hum_station_name_x,min_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((min_hum_value_x, min_hum_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    min_hum_start_coords += 30

# Create Loop for Ampitude
for x in range(len(df_amplitude_az)):
    name = getStationNameById(df_amplitude_az.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp_max = str(df_amplitude_az.iloc[x].temp_max)
    station_temp_min = str(df_amplitude_az.iloc[x].temp_min)
    station_temp_amplitude = str(round(df_amplitude_az.iloc[x].amplitude,2))
    image_editable_az.text((842,525), station_name,(0,0,0), font=location_font)
    image_editable_az.text((920,570), station_temp_max,(154,7,7), font=subtitle_font)
    image_editable_az.text((683,570), station_temp_min,(93,173,236), font=subtitle_font)
    image_editable_az.text((755,600), station_temp_amplitude,(250,186,61), font=amplitude_font)



# ------------------------------
#           MADEIRA
# ------------------------------

# Reset Coordinates

# Right Column 

max_temp_start_coords = 190 # This value increments by 30px every loop iteration
max_temp_station_name_x = 115  # Where Station Name Appears 
max_temp_value_x = 460  # Where Value Appears 

min_temp_start_coords = 370 # This value increments by 30px every loop iteration
min_temp_station_name_x = 115  # Where Station Name Appears 
min_temp_value_x = 460  # Where Value Appears 

max_rain_start_coords = 540 # This value increments by 30px every loop iteration
max_rain_station_name_x = 115  # Where Station Name Appears 
max_rain_value_x = 460  # Where Value Appears 

max_wind_start_coords = 720 # This value increments by 30px every loop iteration
max_wind_station_name_x = 115  # Where Station Name Appears 
max_wind_value_x = 460  # Where Value Appears 


# Left Column 

max_hum_start_coords = 190 # This value increments by 30px every loop iteration
max_hum_station_name_x = 650  # WHere Station Name Appears 
max_hum_value_x = 950  # Where Value Appears 
max_hum_unit_x = 970    # Where Unit Appears 

min_hum_start_coords = 370 # This value increments by 30px every loop iteration
min_hum_station_name_x = 650  # WHere Station Name Appears 
min_hum_value_x = 950  # Where Value Appears 
min_hum_unit_x = 970    # Where Unit Appears 

# Create Loop For Max Temperature 
for x in range(len(four_temp_max_mad)):
    name = getStationNameById(four_temp_max_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_temp_max_mad.iloc[x].temp_max)
    color = four_temp_max_mad.iloc[x].colors
    image_editable_mad.text((max_temp_station_name_x,max_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((max_temp_value_x, max_temp_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_temp_start_coords += 30
 
 # Create Loop For Min Temperature 
for x in range(len(four_temp_min_mad)):
    name = getStationNameById(four_temp_min_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_temp_min_mad.iloc[x].temp_min)
    color = four_temp_min_mad.iloc[x].colors
    image_editable_mad.text((min_temp_station_name_x,min_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((min_temp_value_x, min_temp_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    min_temp_start_coords += 30  

# Create Loop For Max Rainfall 
for x in range(len(four_rain_accu_mad)):
    name = getStationNameById(four_rain_accu_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_rain_accu_mad.iloc[x].prec_quant)
    color = four_rain_accu_mad.iloc[x].colors
    image_editable_mad.text((max_rain_station_name_x,max_rain_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((max_rain_value_x, max_rain_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_rain_start_coords += 30

# Create Loop For Max Wind Gust
for x in range(len(four_wind_max_mad)):
    name = getStationNameById(four_wind_max_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_wind_max_mad.iloc[x].vento_int_max_inst)
    color = four_wind_max_mad.iloc[x].colors
    image_editable_mad.text((max_wind_station_name_x,max_wind_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((max_wind_value_x, max_wind_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_wind_start_coords += 30

# Create Loop for Max Humidity 
for x in range(len(four_hum_max_mad)):
    name = getStationNameById(four_hum_max_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_hum_max_mad.iloc[x].hum_max)
    color = four_hum_max_mad.iloc[x].colors
    image_editable_mad.text((max_hum_station_name_x,max_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((max_hum_value_x, max_hum_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    max_hum_start_coords += 30

# Create Loop for Min Humidity 
for x in range(len(four_hum_min_mad)):
    name = getStationNameById(four_hum_min_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_hum_min_mad.iloc[x].hum_min)
    color = four_hum_min_mad.iloc[x].colors
    image_editable_mad.text((min_hum_station_name_x,min_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((min_hum_value_x, min_hum_start_coords), station_temp, color, font=subtitle_font)
    

    # Increase y coordinates by 30px 
    min_hum_start_coords += 30

# Create Loop for Ampitude
for x in range(len(df_amplitude_mad)):
    name = getStationNameById(df_amplitude_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp_max = str(df_amplitude_mad.iloc[x].temp_max)
    station_temp_min = str(df_amplitude_mad.iloc[x].temp_min)
    station_temp_amplitude = str(round(df_amplitude_mad.iloc[x].amplitude,2))
    image_editable_mad.text((842,525), station_name,(0,0,0), font=location_font)
    image_editable_mad.text((920,570), station_temp_max,(154,7,7), font=subtitle_font)
    image_editable_mad.text((683,570), station_temp_min,(93,173,236), font=subtitle_font)
    image_editable_mad.text((755,600), station_temp_amplitude,(250,186,61), font=amplitude_font)

#---------------------------------
#      INSERT DATES
#---------------------------------

# Insert Report Dates
image_editable_pt.text((29,1020), report_date,(255,255,255), font=date_font)
image_editable_az.text((29,1020), report_date,(255,255,255), font=date_font)
image_editable_mad.text((29,1020), report_date,(255,255,255), font=date_font)

#---------------------------------
#         SAVE PICTURES
#---------------------------------
# Save Resulting Pictures
template_pt.save("daily_meteo_report_pt.png")
template_az.save("daily_meteo_report_az.png")
template_mad.save("daily_meteo_report_mad.png")

lock_file.write_text(f"Generated report for {yesterday_date}\n")
#---------------------------------
#         THE END
#---------------------------------


# Made with 🤍 by Jorge Gomes & João Pina  MARCH 2022
