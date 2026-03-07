# -*- coding: utf-8 -*-
# Original Code: Jorge Gomes 
# Optimization: João Pina 

# ------------------------------
#       DESCRIPTION
# ------------------------------

# This app scrapes information from IPMA and generates an image and its corresponding alt text
# The image is to be shared automatically on social media

# ------------------------------
#       IMPORT LIBRARIES
# ------------------------------

import requests
import pandas as pd
import regex as re
import json
import time
from datetime import datetime, timedelta
from PIL import Image, ImageFont, ImageDraw 
import logging
from string import Template

# Configure logger
logger = logging.getLogger(__name__)

# ---------------------------------------
#    GET DATA AND GENERATE DATAFRAMES
# ----------------------------------------

# Define URL 

#url = 'https://www.ipma.pt/pt/otempo/obs.superficie/table-top-stations-all.jsp'
URL_BOT_FOGOS = 'https://bot.fogos.pt/ipma.php'
URL_IPMA_API = 'https://api.ipma.pt/open-data/observation/meteorology/stations/observations.json'

# Headers to reduce Cloudflare bot blocking
HEADERS = {
    "User-Agent": "VostPTExtremosMeteo/1.0 (DailyWeatherReport; +https://github.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def _is_valid(value):
    """Exclude -99.0 (IPMA's invalid/missing indicator)."""
    return value is not None and value != -99.0


def fetch_from_ipma_api(yesterday_date):
    """
    Fetch from official IPMA API (no Cloudflare) and aggregate hourly → daily.
    Returns json_data in same format as bot.fogos.pt: {date: {stationId: {temp_max, ...}}}
    """
    logger.info(f"Fetching from IPMA API (fallback): {URL_IPMA_API}")
    r = requests.get(URL_IPMA_API, headers=HEADERS, timeout=60)
    r.raise_for_status()
    hourly = r.json()

    # Aggregate by date (YYYY-MM-DD) and station
    # IPMA: temperatura, humidade, intensidadeVentoKM, precAcumulada
    daily_by_date_station = {}  # {(date, stationId): {temps, hums, winds, precs}}

    for dt_str, stations in hourly.items():
        if not isinstance(stations, dict):
            continue
        date_part = dt_str[:10]  # "2026-02-14T01:00" -> "2026-02-14"
        for station_id, obs in stations.items():
            if obs is None:
                continue
            key = (date_part, str(station_id))
            if key not in daily_by_date_station:
                daily_by_date_station[key] = {
                    "temps": [], "hums": [], "winds": [], "precs": []
                }
            t = obs.get("temperatura")
            h = obs.get("humidade")
            w = obs.get("intensidadeVentoKM")
            p = obs.get("precAcumulada")
            if _is_valid(t):
                daily_by_date_station[key]["temps"].append(t)
            if _is_valid(h):
                daily_by_date_station[key]["hums"].append(h)
            if _is_valid(w):
                daily_by_date_station[key]["winds"].append(w)
            if p is not None and p >= 0:  # prec can be 0
                daily_by_date_station[key]["precs"].append(p)

    # Build output in bot.fogos.pt format: {date: {stationId: {temp_max, temp_min, ...}}}
    json_data = {}
    for (date_part, station_id), agg in daily_by_date_station.items():
        if not agg["temps"]:  # need at least temp data
            continue
        row = {
            "temp_max": max(agg["temps"]),
            "temp_min": min(agg["temps"]),
            "vento_int_max_inst": max(agg["winds"]) if agg["winds"] else -99.0,
            "prec_quant": max(agg["precs"]) if agg["precs"] else 0.0,
            "hum_max": max(agg["hums"]) if agg["hums"] else -99.0,
            "hum_min": min(agg["hums"]) if agg["hums"] else -99.0,
        }
        if date_part not in json_data:
            json_data[date_part] = {}
        json_data[date_part][station_id] = row

    logger.info(f"IPMA API: aggregated {len(json_data)} dates, {sum(len(v) for v in json_data.values())} station-days")
    return json_data


def fetch_observations_data(yesterday_date):
    """
    Fetch IPMA observations. Uses official IPMA API first (works from GitHub Actions);
    falls back to bot.fogos.pt only if IPMA API fails (e.g. local network issues).
    Returns json_data dict in format {date: {stationId: {...}}}.
    """
    # Use IPMA API first - no Cloudflare, works from GitHub Actions and locally
    try:
        data = fetch_from_ipma_api(yesterday_date)
        if data and yesterday_date in data:
            logger.info("Using IPMA API data")
            return data
        logger.warning("IPMA API returned no data for yesterday, trying bot.fogos.pt")
    except Exception as e:
        logger.warning(f"IPMA API failed: {e}. Trying bot.fogos.pt fallback.")

    # Fallback to bot.fogos.pt (may be rate-limited from GitHub Actions)
    try:
        logger.info(f"Fetching from {URL_BOT_FOGOS}")
        page = requests.get(URL_BOT_FOGOS, headers=HEADERS, timeout=30)
        if page.status_code == 429:
            raise RuntimeError("Rate limited (429)")
        if "Access denied" in page.text and "Cloudflare" in page.text:
            raise RuntimeError("Cloudflare blocked")
        page.raise_for_status()
        search = re.search(r'var observations = (.*?);', page.text, re.DOTALL)
        if search:
            data = json.loads(search.group(1))
            logger.info("Using bot.fogos.pt data")
            return data
    except Exception as e:
        logger.error(f"bot.fogos.pt also failed: {e}")
        raise RuntimeError(
            "Could not fetch weather data. Both IPMA API and bot.fogos.pt failed."
        ) from e

    raise RuntimeError("Could not fetch weather data from any source.")


# Check yesterday's date early (needed for IPMA fallback)
yesterday = datetime.now() - timedelta(1)
yesterday_date = datetime.strftime(yesterday, '%Y-%m-%d')

# Fetch data (bot.fogos.pt or IPMA API fallback)
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


# Define function to fetch stationId's name 
def getStationNameById(id):
    headers = {
        "User-Agent": "VostPTExtremosMeteo/1.0",
    }
    
    try:
        # Try the v2 endpoint first
        url_bar = f"https://api.fogos.pt/v2/weather/stations?id={id}"
        logger.info(f"Trying v2 endpoint: {url_bar}")
        response_id = requests.get(url_bar, headers=headers, timeout=30)
        logger.info(f"V2 response status: {response_id.status_code}")
        
        # If v2 fails, try v1 endpoint as fallback
        if response_id.status_code != 200:
            url_bar = f"https://api.fogos.pt/v1/weather/stations?id={id}"
            logger.info(f"Trying v1 endpoint: {url_bar}")
            response_id = requests.get(url_bar, headers=headers, timeout=30)
            logger.info(f"V1 response status: {response_id.status_code}")
        
        response_id.raise_for_status()
        
        # Debug the response
        logger.debug(f"Response content: {response_id.text}")
        
        # Check if response is empty
        if not response_id.text:
            logger.error(f"Empty response received for station ID {id}")
            return None
        
        # Add more detailed error logging
        try:
            json_id = response_id.json()
            if not json_id:
                logger.error(f"Empty JSON received for station ID {id}")
                return None
            
            # Log the structure of the response
            logger.debug(f"JSON structure: {json_id.keys() if isinstance(json_id, dict) else 'not a dict'}")
            
            df_id = pd.json_normalize(json_id)
            return df_id
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for station ID {id}: {e}")
            logger.error(f"Response content was: {response_id.text[:200]}...")  # Log first 200 chars
            return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for station ID {id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error for station ID {id}: {e}")
        return None

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

# Max Temperature Colors

four_temp_max_mad.loc[:,'colors'] = pd.Series(colors_temp_max).values
four_temp_max_az.loc[:,'colors'] = pd.Series(colors_temp_max).values
four_temp_max_pt.loc[:,'colors'] = pd.Series(colors_temp_max).values

# Min Temperature Colors

four_temp_min_mad.loc[:,'colors'] = pd.Series(colors_temp_min).values
four_temp_min_az.loc[:,'colors'] = pd.Series(colors_temp_min).values
four_temp_min_pt.loc[:,'colors'] = pd.Series(colors_temp_min).values


# Max Rainfall 

four_rain_accu_mad.loc[:,'colors'] = pd.Series(colors_rain_max).values
four_rain_accu_az.loc[:,'colors'] = pd.Series(colors_rain_max).values
four_rain_accu_pt.loc[:,'colors'] = pd.Series(colors_rain_max).values


# Max Wind Gust 

four_wind_max_mad.loc[:,'colors'] = pd.Series(colors_wind_max).values
four_wind_max_az.loc[:,'colors'] = pd.Series(colors_wind_max).values
four_wind_max_pt.loc[:,'colors'] = pd.Series(colors_wind_max).values

# Mazimum Humidity

four_hum_max_mad.loc[:,'colors'] = pd.Series(colors_hum_max).values
four_hum_max_az.loc[:,'colors'] = pd.Series(colors_hum_max).values
four_hum_max_pt.loc[:,'colors'] = pd.Series(colors_hum_max).values

# Min Humidity
four_hum_min_mad.loc[:,'colors'] = pd.Series(colors_hum_min).values
four_hum_min_az.loc[:,'colors'] = pd.Series(colors_hum_min).values
four_hum_min_pt.loc[:,'colors'] = pd.Series(colors_hum_min).values


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
#     ALT TEXT
# ------------------------------

alt_text = Template(" ".join([
    "Temperatura máxima: $max_temp_station_0 ($max_temp_0); $max_temp_station_1 ($max_temp_1); $max_temp_station_2 ($max_temp_2); $max_temp_station_3 ($max_temp_3).",
    "Temperatura mínima: $min_temp_station_0 ($min_temp_0); $min_temp_station_1 ($min_temp_1); $min_temp_station_2 ($min_temp_2); $min_temp_station_3 ($min_temp_3).",
    "Chuva acumulada: $rainfall_station_0 ($rainfall_0); $rainfall_station_1 ($rainfall_1); $rainfall_station_2 ($rainfall_2); $rainfall_station_3 ($rainfall_3).",
    "Rajada máxima: $wind_station_0 ($wind_0); $wind_station_1 ($wind_1); $wind_station_2 ($wind_2); $wind_station_3 ($wind_3).",
    "Humidade máxima: $max_humidity_station_0 ($max_humidity_0); $max_humidity_station_1 ($max_humidity_1); $max_humidity_station_2 ($max_humidity_2); $max_humidity_station_3 ($max_humidity_3).",
    "Humidade mínima: $min_humidity_station_0 ($min_humidity_0); $min_humidity_station_1 ($min_humidity_1); $min_humidity_station_2 ($min_humidity_2); $min_humidity_station_3 ($min_humidity_3).",
    "Maior amplitude térmica: $amplitude_station ($amplitude, variando entre $min_amplitude e $max_amplitude)."
]))

alt_text_pt_data: dict[str, str] = {}
alt_text_az_data: dict[str, str] = {}
alt_text_mad_data: dict[str, str] = {}

# ------------------------------
#     PORTUGAL CONTINENTAL
# ------------------------------


# Create Loop For Max Temperature
for x in range(4):
    name = getStationNameById(four_temp_max_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp_value = four_temp_max_pt.iloc[x].temp_max
    station_temp = str(station_temp_value)
    color = four_temp_max_pt.iloc[x].colors
    image_editable_pt.text((max_temp_station_name_x,max_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((max_temp_value_x, max_temp_start_coords), station_temp, color, font=subtitle_font)

    alt_text_pt_data[f"max_temp_station_{x}"] = station_name_final
    alt_text_pt_data[f"max_temp_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_temp_start_coords += 30

# Create Loop For Min Temperature
for x in range(4):
    name = getStationNameById(four_temp_min_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp_value = four_temp_min_pt.iloc[x].temp_min
    station_temp = str(station_temp_value)
    color = four_temp_min_pt.iloc[x].colors
    image_editable_pt.text((min_temp_station_name_x,min_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((min_temp_value_x, min_temp_start_coords), station_temp, color, font=subtitle_font)

    alt_text_pt_data[f"min_temp_station_{x}"] = station_name_final
    alt_text_pt_data[f"min_temp_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    min_temp_start_coords += 30

# Create Loop For Max Rainfall
for x in range(4):
    name = getStationNameById(four_rain_accu_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp_value = four_rain_accu_pt.iloc[x].prec_quant
    station_temp = str(station_temp_value)
    color = four_rain_accu_pt.iloc[x].colors
    image_editable_pt.text((max_rain_station_name_x,max_rain_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((max_rain_value_x, max_rain_start_coords), station_temp, color, font=subtitle_font)

    alt_text_pt_data[f"rainfall_station_{x}"] = station_name_final
    alt_text_pt_data[f"rainfall_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_rain_start_coords += 30

# Create Loop For Max Wind Gust
for x in range(4):
    name = getStationNameById(four_wind_max_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp_value = four_wind_max_pt.iloc[x].vento_int_max_inst
    station_temp = str(station_temp_value)
    color = four_wind_max_pt.iloc[x].colors
    image_editable_pt.text((max_wind_station_name_x,max_wind_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((max_wind_value_x, max_wind_start_coords), station_temp, color, font=subtitle_font)

    alt_text_pt_data[f"wind_station_{x}"] = station_name_final
    alt_text_pt_data[f"wind_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_wind_start_coords += 30

# Create Loop for Max Humidity
for x in range(4):
    name = getStationNameById(four_hum_max_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp_value = four_hum_max_pt.iloc[x].hum_max
    station_temp = str(station_temp_value)
    color = four_hum_max_pt.iloc[x].colors
    image_editable_pt.text((max_hum_station_name_x,max_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((max_hum_value_x, max_hum_start_coords), station_temp, color, font=subtitle_font)

    alt_text_pt_data[f"max_humidity_station_{x}"] = station_name_final
    alt_text_pt_data[f"max_humidity_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_hum_start_coords += 30

# Create Loop for Min Humidity
for x in range(4):
    name = getStationNameById(four_hum_min_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp_value = four_hum_min_pt.iloc[x].hum_min
    station_temp = str(station_temp_value)
    color = four_hum_min_pt.iloc[x].colors
    image_editable_pt.text((min_hum_station_name_x,min_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_pt.text((min_hum_value_x, min_hum_start_coords), station_temp, color, font=subtitle_font)

    alt_text_pt_data[f"min_humidity_station_{x}"] = station_name_final
    alt_text_pt_data[f"min_humidity_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    min_hum_start_coords += 30

# Create Loop for Amplitude
for x in range(1):
    name = getStationNameById(df_amplitude_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp_max_value = df_amplitude_pt.iloc[x].temp_max
    station_temp_min_value = df_amplitude_pt.iloc[x].temp_min
    station_temp_amplitude_value = round(df_amplitude_pt.iloc[x].amplitude, 2)
    station_temp_max = str(station_temp_max_value)
    station_temp_min = str(station_temp_min_value)
    station_temp_amplitude = str(station_temp_amplitude_value)
    image_editable_pt.text((842,525), station_name,(0,0,0), font=location_font)
    image_editable_pt.text((920,570), station_temp_max,(154,7,7), font=subtitle_font)
    image_editable_pt.text((683,570), station_temp_min,(93,173,236), font=subtitle_font)
    image_editable_pt.text((755,600), station_temp_amplitude,(250,186,61), font=amplitude_font)

    alt_text_pt_data["amplitude_station"] = station_name
    alt_text_pt_data["amplitude"] = f"{station_temp_amplitude_value:g}".replace(".", ",")
    alt_text_pt_data["min_amplitude"] = f"{station_temp_min_value:g}".replace(".", ",")
    alt_text_pt_data["max_amplitude"] = f"{station_temp_max_value:g}".replace(".", ",")


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
for x in range(4):
    name = getStationNameById(four_temp_max_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp_value = four_temp_max_az.iloc[x].temp_max
    station_temp = str(station_temp_value)
    color = four_temp_max_az.iloc[x].colors
    image_editable_az.text((max_temp_station_name_x,max_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((max_temp_value_x, max_temp_start_coords), station_temp, color, font=subtitle_font)

    alt_text_az_data[f"max_temp_station_{x}"] = station_name_final
    alt_text_az_data[f"max_temp_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_temp_start_coords += 30

# Create Loop For Min Temperature
for x in range(4):
    name = getStationNameById(four_temp_min_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp_value = four_temp_min_az.iloc[x].temp_min
    station_temp = str(station_temp_value)
    color = four_temp_min_az.iloc[x].colors
    image_editable_az.text((min_temp_station_name_x,min_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((min_temp_value_x, min_temp_start_coords), station_temp, color, font=subtitle_font)

    alt_text_az_data[f"min_temp_station_{x}"] = station_name_final
    alt_text_az_data[f"min_temp_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    min_temp_start_coords += 30

# Create Loop For Max Rainfall
for x in range(4):
    name = getStationNameById(four_rain_accu_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp_value = four_rain_accu_az.iloc[x].prec_quant
    station_temp = str(station_temp_value)
    color = four_rain_accu_az.iloc[x].colors
    image_editable_az.text((max_rain_station_name_x,max_rain_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((max_rain_value_x, max_rain_start_coords), station_temp, color, font=subtitle_font)

    alt_text_az_data[f"rainfall_station_{x}"] = station_name_final
    alt_text_az_data[f"rainfall_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_rain_start_coords += 30

# Create Loop For Max Wind Gust
for x in range(4):
    name = getStationNameById(four_wind_max_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp_value = four_wind_max_az.iloc[x].vento_int_max_inst
    station_temp = str(station_temp_value)
    color = four_wind_max_az.iloc[x].colors
    image_editable_az.text((max_wind_station_name_x,max_wind_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((max_wind_value_x, max_wind_start_coords), station_temp, color, font=subtitle_font)

    alt_text_az_data[f"wind_station_{x}"] = station_name_final
    alt_text_az_data[f"wind_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_wind_start_coords += 30

# Create Loop for Max Humidity
for x in range(4):
    name = getStationNameById(four_hum_max_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp_value = four_hum_max_az.iloc[x].hum_max
    station_temp = str(station_temp_value)
    color = four_hum_max_az.iloc[x].colors
    image_editable_az.text((max_hum_station_name_x,max_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((max_hum_value_x, max_hum_start_coords), station_temp, color, font=subtitle_font)

    alt_text_az_data[f"max_humidity_station_{x}"] = station_name_final
    alt_text_az_data[f"max_humidity_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_hum_start_coords += 30

# Create Loop for Min Humidity
for x in range(4):
    name = getStationNameById(four_hum_min_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp_value = four_hum_min_az.iloc[x].hum_min
    station_temp = str(station_temp_value)
    color = four_hum_min_az.iloc[x].colors
    image_editable_az.text((min_hum_station_name_x,min_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_az.text((min_hum_value_x, min_hum_start_coords), station_temp, color, font=subtitle_font)

    alt_text_az_data[f"min_humidity_station_{x}"] = station_name_final
    alt_text_az_data[f"min_humidity_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    min_hum_start_coords += 30

# Create Loop for Amplitude
for x in range(1):
    name = getStationNameById(df_amplitude_az.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp_max_value = df_amplitude_az.iloc[x].temp_max
    station_temp_min_value = df_amplitude_az.iloc[x].temp_min
    station_temp_amplitude_value = round(df_amplitude_az.iloc[x].amplitude, 2)
    station_temp_max = str(station_temp_max_value)
    station_temp_min = str(station_temp_min_value)
    station_temp_amplitude = str(station_temp_amplitude_value)
    image_editable_az.text((842,525), station_name,(0,0,0), font=location_font)
    image_editable_az.text((920,570), station_temp_max,(154,7,7), font=subtitle_font)
    image_editable_az.text((683,570), station_temp_min,(93,173,236), font=subtitle_font)
    image_editable_az.text((755,600), station_temp_amplitude,(250,186,61), font=amplitude_font)

    alt_text_az_data["amplitude_station"] = station_name
    alt_text_az_data["amplitude"] = f"{station_temp_amplitude_value:g}".replace(".", ",")
    alt_text_az_data["min_amplitude"] = f"{station_temp_min_value:g}".replace(".", ",")
    alt_text_az_data["max_amplitude"] = f"{station_temp_max_value:g}".replace(".", ",")

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
for x in range(4):
    name = getStationNameById(four_temp_max_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp_value = four_temp_max_mad.iloc[x].temp_max
    station_temp = str(station_temp_value)
    color = four_temp_max_mad.iloc[x].colors
    image_editable_mad.text((max_temp_station_name_x,max_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((max_temp_value_x, max_temp_start_coords), station_temp, color, font=subtitle_font)

    alt_text_mad_data[f"max_temp_station_{x}"] = station_name_final
    alt_text_mad_data[f"max_temp_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_temp_start_coords += 30

# Create Loop For Min Temperature
for x in range(4):
    name = getStationNameById(four_temp_min_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp_value = four_temp_min_mad.iloc[x].temp_min
    station_temp = str(station_temp_value)
    color = four_temp_min_mad.iloc[x].colors
    image_editable_mad.text((min_temp_station_name_x,min_temp_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((min_temp_value_x, min_temp_start_coords), station_temp, color, font=subtitle_font)

    alt_text_mad_data[f"min_temp_station_{x}"] = station_name_final
    alt_text_mad_data[f"min_temp_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    min_temp_start_coords += 30

# Create Loop For Max Rainfall
for x in range(4):
    name = getStationNameById(four_rain_accu_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp_value = four_rain_accu_mad.iloc[x].prec_quant
    station_temp = str(station_temp_value)
    color = four_rain_accu_mad.iloc[x].colors
    image_editable_mad.text((max_rain_station_name_x,max_rain_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((max_rain_value_x, max_rain_start_coords), station_temp, color, font=subtitle_font)

    alt_text_mad_data[f"rainfall_station_{x}"] = station_name_final
    alt_text_mad_data[f"rainfall_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_rain_start_coords += 30

# Create Loop For Max Wind Gust
for x in range(4):
    name = getStationNameById(four_wind_max_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp_value = four_wind_max_mad.iloc[x].vento_int_max_inst
    station_temp = str(station_temp_value)
    color = four_wind_max_mad.iloc[x].colors
    image_editable_mad.text((max_wind_station_name_x,max_wind_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((max_wind_value_x, max_wind_start_coords), station_temp, color, font=subtitle_font)

    alt_text_mad_data[f"wind_station_{x}"] = station_name_final
    alt_text_mad_data[f"wind_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_wind_start_coords += 30

# Create Loop for Max Humidity
for x in range(4):
    name = getStationNameById(four_hum_max_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp_value = four_hum_max_mad.iloc[x].hum_max
    station_temp = str(station_temp_value)
    color = four_hum_max_mad.iloc[x].colors
    image_editable_mad.text((max_hum_station_name_x,max_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((max_hum_value_x, max_hum_start_coords), station_temp, color, font=subtitle_font)

    alt_text_mad_data[f"max_humidity_station_{x}"] = station_name_final
    alt_text_mad_data[f"max_humidity_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    max_hum_start_coords += 30

# Create Loop for Min Humidity
for x in range(4):
    name = getStationNameById(four_hum_min_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp_value = four_hum_min_mad.iloc[x].hum_min
    station_temp = str(station_temp_value)
    color = four_hum_min_mad.iloc[x].colors
    image_editable_mad.text((min_hum_station_name_x,min_hum_start_coords), station_name_final, color, font=subtitle_font)
    image_editable_mad.text((min_hum_value_x, min_hum_start_coords), station_temp, color, font=subtitle_font)

    alt_text_mad_data[f"min_humidity_station_{x}"] = station_name_final
    alt_text_mad_data[f"min_humidity_{x}"] = f"{station_temp_value:g}".replace(".", ",")

    # Increase y coordinates by 30px
    min_hum_start_coords += 30

# Create Loop for Amplitude
for x in range(1):
    name = getStationNameById(df_amplitude_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp_max_value = df_amplitude_mad.iloc[x].temp_max
    station_temp_min_value = df_amplitude_mad.iloc[x].temp_min
    station_temp_amplitude_value = round(df_amplitude_mad.iloc[x].amplitude, 2)
    station_temp_max = str(station_temp_max_value)
    station_temp_min = str(station_temp_min_value)
    station_temp_amplitude = str(station_temp_amplitude_value)
    image_editable_mad.text((842,525), station_name,(0,0,0), font=location_font)
    image_editable_mad.text((920,570), station_temp_max,(154,7,7), font=subtitle_font)
    image_editable_mad.text((683,570), station_temp_min,(93,173,236), font=subtitle_font)
    image_editable_mad.text((755,600), station_temp_amplitude,(250,186,61), font=amplitude_font)

    alt_text_mad_data["amplitude_station"] = station_name
    alt_text_mad_data["amplitude"] = f"{station_temp_amplitude_value:g}".replace(".", ",")
    alt_text_mad_data["min_amplitude"] = f"{station_temp_min_value:g}".replace(".", ",")
    alt_text_mad_data["max_amplitude"] = f"{station_temp_max_value:g}".replace(".", ",")

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

# Save Alt Texts
with open("daily_meteo_report_pt.txt", mode="w", encoding="utf-8") as f:
    f.write(alt_text.substitute(alt_text_pt_data))

with open("daily_meteo_report_az.txt", mode="w", encoding="utf-8") as f:
    f.write(alt_text.substitute(alt_text_az_data))

with open("daily_meteo_report_mad.txt", mode="w", encoding="utf-8") as f:
    f.write(alt_text.substitute(alt_text_mad_data))

#---------------------------------
#         THE END
#---------------------------------


# Made with 🤍 by Jorge Gomes & João Pina  MARCH 2022
