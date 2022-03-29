# DAILY WEATHER REPORT


## WORKFLOW

1. Get Madeira - df_madeira - via API call
2. Get Açores - df_azores - via API call 
3. Get Continente - df_continente - via API call 

Sort by date 
1. df_madeira
2. df_azores
3. df_continente

Select by yesterday’s date 
1. df_madeira
2. df_azores
3. df_continente

Create Top 4 dataframes
1. df_madeira
    1. df_madeira_temp_max
    2. df_madeira_temp_min
    3. df_madeira_wind_max
    4. df_madeira_rain_accu
2. df_azores
    1. df_azores_temp_max
    2. df_azores_temp_min
    3. df_azores_wind_max
    4. df_azores_rain_accu
3. df_continente
    1. df_continente_temp_max
    2. df_continente_temp_min
    3. df_continente_wind_max
    4. df_continente_rain_accu

Load Image Templates 
1. Madeira
2. Açores
3. Continente

Loop to create Image 
1. Madeira
2. Açores
3. Continente

Save Images
1. Madeira
2. Açores
3. Continente


# ALPHA VERSION 


![daily](https://user-images.githubusercontent.com/34355337/160450254-64c90def-abbc-46ac-bc8d-8b4a07e3a02e.png)


# INSTALL
- Fork repo
- Create repo on your machine
- Create a virtual environment on your machine 
- run ```pip install -r requirements.txt --no-index --find-links file:///tmp/packages```
