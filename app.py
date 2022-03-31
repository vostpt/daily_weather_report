# -*- coding: utf-8 -*-
# Original Code: Jorge Gomes 
# Optimization: João Pina 

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
from datetime import datetime, timedelta
from PIL import Image, ImageFont, ImageDraw 


# ---------------------------------------
#    GET DATA AND GENERATE DATAFRAMES
# ----------------------------------------

# Define URL 

url = 'https://www.ipma.pt/pt/otempo/obs.superficie/table-top-stations-all.jsp'

# Get URL content 
page = requests.get(url)


# Based on this soluton 
# https://gist.github.com/falsovsky/aa5423db4c71ff3dbfeeff48b9102ed5 

# Use Regex to extract json

search = re.search('var observations = (.*?);',page.text,re.DOTALL);
json_data = json.loads(search.group(1))

# Create Dataframe from json data

ipma_data = pd.concat({k: pd.DataFrame(v).T for k, v in json_data.items()}, axis=0).reset_index()

# Rename resulting level_x columns

ipma_data = ipma_data.rename(columns={'level_0': 'date','level_1':'stationId'})

# Sort dataframe by date 

ipma_data = ipma_data.sort_values(by=['date'])

# Check yesterday's date and create string

yesterday = datetime.now() - timedelta(1)
yesterday_date = datetime.strftime(yesterday, '%Y-%m-%d')
report_date = str(yesterday_date)

# Create new datafraeme with only yesterday's results

ipma_data_yesterday = ipma_data[ipma_data['date'] == yesterday_date]


# Define function to fetch stationId's name 
def getStationNameById(id):
    url_bar = f"https://api.fogos.pt/v2/weather/stations" \
    f"?id={id}" 
    # Get response from URL 
    response_id = requests.get(url_bar)
    # Get the json content from the response
    json_id = response_id.json()
    # Create Datafframe from json file
    df_id = pd.json_normalize(json_id)
    return df_id


# Create empty list for territory
territory = []

# Get max records on dataframe
max_records = len(ipma_data_yesterday)

# Get territory for each station on the Dataframe 

for x in range(max_records):
  info = getStationNameById(ipma_data_yesterday.iloc[x].stationId)
  region = info.place.values[0]
  territory.append(region)

# Create new column called "territory" using the list generated above 

ipma_data_yesterday.loc[:,'territory'] = pd.Series(territory).values

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

colors_temp_max = [(143,32,23),(155,53,48),(179,103,101),(205,156,155)]
colors_temp_min = [(89,165,222),(89,165,222),(107,176,226),(141,195,233)]
colors_hum_max = [(89,165,222),(89,165,222),(107,176,226),(141,195,233)]
colors_hum_min = [(143,32,23),(155,53,48),(179,103,101),(205,156,155)]
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
#     PORTUGAL CONTINENTAL
# ------------------------------


# Create Loop For Max Temperature 
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(1):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(1):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(4):
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
for x in range(1):
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

#---------------------------------
#         THE END
#---------------------------------


# Made with 🤍 by Jorge Gomes & João Pina  MARCH 2022

