import os
import pandas as pd
import requests
from io import StringIO

DATA_DIR = "calamity_historical_data"

def download_earthquakes():
    print("Downloading historical Earthquake data (USGS) > Mag 6.0 since 2000...")
    # USGS API endpoint for earthquakes > Magnitude 6.0 since Jan 1, 2000
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&starttime=2000-01-01&minmagnitude=6.0"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        df = pd.read_csv(StringIO(response.text))
        
        # Sort by date
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values(by='time')
        
        file_path = os.path.join(DATA_DIR, "usgs_earthquakes_mag6plus.csv")
        df.to_csv(file_path, index=False)
        print(f"Successfully saved {len(df)} major earthquakes to {file_path}")
        
    except Exception as e:
        print(f"Error downloading earthquakes: {e}")

def download_cyclones():
    print("Downloading historical Cyclone/Hurricane data (NOAA IBTrACS)...")
    print("Note: This is a large dataset (~100MB+), filtering for year >= 2000...")
    # NOAA IBTrACS CSV endpoint
    url = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ALL.list.v04r01.csv"
    
    try:
        # We stream the download because it's large, and we read it in chunks to filter
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # The first row is the header, the second row is units, we skip the units row
        df_list = []
        chunk_iter = pd.read_csv(StringIO(response.text), chunksize=50000, low_memory=False, skiprows=[1])
        
        for chunk in chunk_iter:
            # Filter for Year >= 2000 (Season column)
            # Some rows might have invalid seasons, so we coerce to numeric
            chunk['SEASON'] = pd.to_numeric(chunk['SEASON'], errors='coerce')
            filtered_chunk = chunk[chunk['SEASON'] >= 2000]
            df_list.append(filtered_chunk)
            
        final_df = pd.concat(df_list, ignore_index=True)
        
        file_path = os.path.join(DATA_DIR, "noaa_cyclones_since_2000.csv")
        final_df.to_csv(file_path, index=False)
        
        # Unique storms
        unique_storms = final_df['SID'].nunique()
        print(f"Successfully saved {unique_storms} unique global cyclones to {file_path}")
        
    except Exception as e:
        print(f"Error downloading cyclones: {e}")

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    download_earthquakes()
    download_cyclones()
