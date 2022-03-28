# -*- coding: utf-8 -*-
# author: Jorge Gomes for VOST Portugal

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


# Based on this soluton https://gist.github.com/falsovsky/aa5423db4c71ff3dbfeeff48b9102ed5 

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
four_wind_max = ipma_data_yesterday.sort_values(by=['vento_int_max_inst'],ascending=False).head(4)


# Max rain accumulated
four_rain_accu = ipma_data_yesterday.sort_values(by=['prec_quant'],ascending=False).head(4)

# ------------------------------
#     DAILY VARIABLES
# ------------------------------

# FIRST VALUE 
row = 0 
station_01 = four_temp_max.iloc[row].stationId
url_bar = f"https://api.fogos.pt/v2/weather/stations" \
f"?id={station_01}" 
# Get response from URL 
response_id = requests.get(url_bar)
# Get the json content from the response
json_id = response_id.json()
df_id = pd.json_normalize(json_id)


# ------------------------------
#      IMAGE MANIPULATION
# ------------------------------

def getStationNameById(id):
    url_bar = f"https://api.fogos.pt/v2/weather/stations" \
    f"?id={id}" 
    # Get response from URL 
    response_id = requests.get(url_bar)
    # Get the json content from the response
    json_id = response_id.json()
    df_id = pd.json_normalize(json_id)
    return df_id


# Load Base Image
template = Image.open("template.png")

# Define Title Font
title_font = ImageFont.truetype('Lato-Bold.ttf', 24)
subtitle_font = ImageFont.truetype('Lato-Bold.ttf', 22)

title_text_temp_max = "TEMPERATURA MÁXIMA"
image_editable = ImageDraw.Draw(template)

image_editable.text((10,150), title_text_temp_max, (0, 0, 0), font=title_font)

station_name_01 = str(df_id.location.values[0])
station_temp_01 = str(four_temp_max.iloc[row].temp_max)

image_editable.text((10,190), station_name_01, (0, 0, 0), font=subtitle_font)
image_editable.text((250,190), station_temp_01, (0, 0, 0), font=subtitle_font)

start_coord = 230
for x in range(3):
    name = getStationNameById(four_temp_max.iloc[x].stationId)
    station_name = name.location.values[0]
    station_temp = str(four_temp_max.iloc[x].temp_max)

    image_editable.text((10,start_coord), station_name, (0, 0, 0), font=subtitle_font)
    image_editable.text((150,start_coord), station_temp, (0, 0, 0), font=subtitle_font)

    start_coord += 40


template.save("daily.png")


# Made with 🤍 by Jorge 🔨 Gomes MARCH 2022