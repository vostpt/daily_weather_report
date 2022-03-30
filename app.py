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
date_font = ImageFont.truetype('Lato-Bold.ttf', 72)

# Create copies of the images that can be edited
image_editable_pt = ImageDraw.Draw(template_pt)
image_editable_az = ImageDraw.Draw(template_az)
image_editable_mad = ImageDraw.Draw(template_mad)

# Create Units strings 
temp_unit = "º C"
rain_unit = " mm"
wind_unit = " km/h"

# Create vars for coordinates

max_temp_station_y = 40
max_temp_y = 373.7607
max_temp_unit_y = 416

min_temp_station_y = 40
min_temp_y = 385.9927
min_temp_unit_y = 416

max_wind_station_y = 600
max_wind_y = 950
max_wind_unit_y = 1000.0576

max_rain_station_y = 600
max_rain_y = 950
max_rain_unit_y = 1000.0576

# Create Colors Lists

colors_temp_max = []
colors_temp_min = []
colors_hum_max = []
colors_hum_min = []
colors_wind_max = []
colors_rain_accu =[(112,112,164),(138,147,189),(163,175,213),(185,194,226)


# ------------------------------
#     PORTUGAL CONTINENTAL
# ------------------------------

# Define starting Y Coordinates 
start_coord = 300

# Create Loop For Max Temperature 
for x in range(4):
    name = getStationNameById(four_temp_max_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_temp_max_pt.iloc[x].temp_max)
    image_editable_pt.text((max_temp_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_pt.text((max_temp_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_pt.text((max_temp_unit_y,start_coord), temp_unit, (0, 0, 0), font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24
   

# Define starting Y Coordinates 
start_coord = 560

# Create Loop For Min Temperature 
for x in range(4):
    name = getStationNameById(four_temp_min_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_temp_min_pt.iloc[x].temp_min)
    image_editable_pt.text((min_temp_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_pt.text((min_temp_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_pt.text((min_temp_unit_y,start_coord), temp_unit, (0, 0, 0), font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24

# Define starting Y Coordinates 
start_coord = 560

# Create Loop For Max Wind Gusts
for x in range(4):
    name = getStationNameById(four_wind_max_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_wind_max_pt.iloc[x].vento_int_max_inst)
    image_editable_pt.text((max_wind_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_pt.text((max_wind_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_pt.text((max_wind_unit_y,start_coord), wind_unit, (0,0,0),font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24

# Define starting Y Coordinates 
start_coord = 300

# Create Loop For Max Rain Accumulation
for x in range(4):
    name = getStationNameById(four_rain_accu_pt.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(CIM)", "").strip()
    station_temp = str(four_rain_accu_pt.iloc[x].prec_quant)
    image_editable_pt.text((max_rain_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_pt.text((max_rain_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_pt.text((max_rain_unit_y,start_coord), rain_unit, (0,0,0),font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24

# ------------------------------
#     AZORES
# ------------------------------

# Define starting Y Coordinates 
start_coord = 300

# Create Loop For Max Temperature 
for x in range(4):
    name = getStationNameById(four_temp_max_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_temp_max_az.iloc[x].temp_max)
    image_editable_az.text((max_temp_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_az.text((max_temp_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_az.text((max_temp_unit_y,start_coord), temp_unit, (0, 0, 0), font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24
   

# Define starting Y Coordinates 
start_coord = 560

# Create Loop For Min Temperature 
for x in range(4):
    name = getStationNameById(four_temp_min_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_temp_min_az.iloc[x].temp_min)
    image_editable_az.text((min_temp_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_az.text((min_temp_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_az.text((min_temp_unit_y,start_coord), temp_unit, (0, 0, 0), font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24

# Define starting Y Coordinates 
start_coord = 560

# Create Loop For Max Wind Gusts
for x in range(4):
    name = getStationNameById(four_wind_max_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_wind_max_az.iloc[x].vento_int_max_inst)
    image_editable_az.text((max_wind_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_az.text((max_wind_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_az.text((max_wind_unit_y,start_coord), wind_unit, (0,0,0),font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24

# Define starting Y Coordinates 
start_coord = 300

# Create Loop For Max Rain Accumulation
for x in range(4):
    name = getStationNameById(four_rain_accu_az.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("(DROTRH)", "").strip()
    station_temp = str(four_rain_accu_az.iloc[x].prec_quant)
    image_editable_az.text((max_rain_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_az.text((max_rain_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_az.text((max_rain_unit_y,start_coord), rain_unit, (0,0,0),font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24


#---------------------------------
#          MADEIRA
#---------------------------------

# Define starting Y Coordinates 
start_coord = 300

# Create Loop For Max Temperature 
for x in range(4):
    name = getStationNameById(four_temp_max_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_temp_max_mad.iloc[x].temp_max)
    image_editable_mad.text((max_temp_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_mad.text((max_temp_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_mad.text((max_temp_unit_y,start_coord), temp_unit, (0, 0, 0), font=subtitle_font)

    # Increase y coordinates by 24px 

    # Increase y coordinates by 24px 
    start_coord += 24
   

# Define starting Y Coordinates 
start_coord = 560

# Create Loop For Min Temperature 
for x in range(4):
    name = getStationNameById(four_temp_min_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_temp_min_mad.iloc[x].temp_min)
    image_editable_mad.text((min_temp_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_mad.text((min_temp_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_mad.text((min_temp_unit_y,start_coord), temp_unit, (0, 0, 0), font=subtitle_font)


    # Increase y coordinates by 24px 
    start_coord += 24

# Define starting Y Coordinates 
start_coord = 560

# Create Loop For Max Wind Gusts
for x in range(4):
    name = getStationNameById(four_wind_max_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_wind_max_mad.iloc[x].vento_int_max_inst)
    image_editable_mad.text((max_wind_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_mad.text((max_wind_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_mad.text((max_wind_unit_y,start_coord), wind_unit, (0,0,0),font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24

# Define starting Y Coordinates 
start_coord = 300

# Create Loop For Max Rain Accumulation
for x in range(4):
    name = getStationNameById(four_rain_accu_mad.iloc[x].stationId)
    station_name = name.location.values[0]
    # Strip station names 
    station_name_final = station_name.replace("Madeira,", "").strip()
    station_temp = str(four_rain_accu_mad.iloc[x].prec_quant)
    image_editable_mad.text((max_rain_station_y,start_coord), station_name_final, (0, 0, 0), font=subtitle_font)
    image_editable_mad.text((max_rain_y,start_coord), station_temp, (0, 0, 0), font=subtitle_font)
    image_editable_mad.text((max_rain_unit_y,start_coord), rain_unit, (0,0,0),font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24


#---------------------------------
#      INSERT DATE AND UNITS
#---------------------------------

image_editable_pt.text((348.8804,739.9473), report_date, (193, 193, 193), font=date_font)
image_editable_az.text((348.8804,739.9473), report_date, (193, 193, 193), font=date_font)
image_editable_mad.text((348.8804,739.9473), report_date, (193, 193, 193), font=date_font)


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



#............................................ PAGE BREAK ......................