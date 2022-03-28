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


# ------------------------------
#            GET DATA
# ------------------------------

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

# Create new datafraeme with only yesterday's results

ipma_data_yesterday = ipma_data[ipma_data['date'] == yesterday_date]

# Max Temperatures 
# Create Dataframe based on yesterday's data, sorting maximum temperature and extracting top 4 values

four_temp_max  = ipma_data_yesterday.sort_values(by=['temp_max'],ascending=False).head(4)

# Min Temperatures
# Create Dataframe based on yesterday's data, sorting minimum temperature

four_temp_min_all  = ipma_data_yesterday.sort_values(by=['temp_min'],ascending=True)

# Drop all -99.0 values, since those are IPMA's way of saying station is fucked up. (Yes!Really!)
# and keep top four results
four_temp_min = four_temp_min_all[four_temp_min_all.temp_min != -99.0].head(4)

# Max Wind Gust 
# Create Dataframe based on yesterday's data, sorting maximum wind gust
four_wind_max = ipma_data_yesterday.sort_values(by=['vento_int_max_inst'],ascending=False).head(4)


# Max rain accumulated
# Create Dataframe based on yesterday's data, sorting maximum accumulated rain
four_rain_accu = ipma_data_yesterday.sort_values(by=['prec_quant'],ascending=False).head(4)


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

# ------------------------------
#       IMAGE MANIPULATION 
# ------------------------------
# Load Base Image
template = Image.open("resumo_meteo_template.png")

# Define Font and Size
# Font file needs to be in the same folder
title_font = ImageFont.truetype('Lato-Bold.ttf', 24)
subtitle_font = ImageFont.truetype('Lato-Bold.ttf', 22)

# Create a copy of the image that can be edited
image_editable = ImageDraw.Draw(template)


# Define starting Y Coordinates 
start_coord = 300

# Create Loop For Max Temperature 
for x in range(4):
    name = getStationNameById(four_temp_max.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp = str(four_temp_max.iloc[x].temp_max)
    image_editable.text((40,start_coord), station_name, (0, 0, 0), font=subtitle_font)
    image_editable.text((450,start_coord), station_temp, (0, 0, 0), font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24
   

# Define starting Y Coordinates 
start_coord = 560

# Create Loop For Min Temperature 
for x in range(4):
    name = getStationNameById(four_temp_min.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp = str(four_temp_min.iloc[x].temp_min)
    image_editable.text((40,start_coord), station_name, (0, 0, 0), font=subtitle_font)
    image_editable.text((450,start_coord), station_temp, (0, 0, 0), font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24

# Define starting Y Coordinates 
start_coord = 560

# Create Loop For Max Wind Gusts
for x in range(4):
    name = getStationNameById(four_wind_max.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp = str(four_wind_max.iloc[x].vento_int_max_inst)
    image_editable.text((600,start_coord), station_name, (0, 0, 0), font=subtitle_font)
    image_editable.text((950,start_coord), station_temp, (0, 0, 0), font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24

# Define starting Y Coordinates 
start_coord = 300

# Create Loop For Max Rain Accumulation
for x in range(4):
    name = getStationNameById(four_rain_accu.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp = str(four_wind_max.iloc[x].prec_quant)
    image_editable.text((600,start_coord), station_name, (0, 0, 0), font=subtitle_font)
    image_editable.text((950,start_coord), station_temp, (0, 0, 0), font=subtitle_font)

    # Increase y coordinates by 24px 
    start_coord += 24

# Save Resulting Picture 
template.save("daily_meteo_report.png")


# Made with 🤍 by Jorge Gomes & João Pina  MARCH 2022