import os
import pandas as pd
import json
from pathlib import Path

RAW_DIR = Path(".")
PROCESSED_DIR = Path("data/processed")

def process_ohlcv(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(input_dir): return
    files = [f for f in os.listdir(input_dir) if f.endswith('.csv')]
    for file in files:
        file_path = os.path.join(input_dir, file)
        try:
            df = pd.read_csv(file_path)
            if 'Date' not in df.columns: 
                continue
            
            # Ensure Date is timezone-aware UTC
            df['Date'] = pd.to_datetime(df['Date'], utc=True)
            
            # Drop rows where all prices are NaN
            price_cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Adj Close'] if c in df.columns]
            df = df.dropna(subset=price_cols, how='all')
            
            # Forward fill remaining NaNs in price columns
            if not df.empty:
                df[price_cols] = df[price_cols].ffill()
            
            df.to_csv(os.path.join(output_dir, file), index=False)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

def process_news():
    os.makedirs(PROCESSED_DIR / "news", exist_ok=True)
    
    # Process old news
    old_news_path = "india-news-headlines.csv"
    if os.path.exists(old_news_path):
        print("Processing old news...")
        df_iter = pd.read_csv(old_news_path, chunksize=100000)
        first = True
        for chunk in df_iter:
            chunk = chunk.dropna(subset=['headline_text'])
            chunk['publish_date'] = pd.to_datetime(chunk['publish_date'].astype(str), format='%Y%m%d', errors='coerce', utc=True)
            chunk = chunk.dropna(subset=['publish_date'])
            # Basic text clean
            chunk['headline_text'] = chunk['headline_text'].str.replace(r'<[^<>]*>', '', regex=True).str.strip()
            
            chunk.to_csv(PROCESSED_DIR / "news" / "india_news_cleaned.csv", mode='a' if not first else 'w', header=first, index=False)
            first = False
            
    # Process new news
    new_news_path = "clean_stock_news_2016 to 2026.csv"
    if os.path.exists(new_news_path):
        print("Processing new news...")
        df = pd.read_csv(new_news_path)
        df = df.dropna(subset=['title'])
        df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
        df = df.dropna(subset=['date'])
        df['title'] = df['title'].str.replace(r'<[^<>]*>', '', regex=True).str.strip()
        df.to_csv(PROCESSED_DIR / "news" / "stock_news_2016_2026_cleaned.csv", index=False)

def process_metadata():
    if not os.path.exists("company_metadata.json"): return
    print("Processing company metadata...")
    with open("company_metadata.json", "r") as f:
        data = json.load(f)
        
    cleaned = {k: v for k, v in data.items() if "error" not in v}
    
    with open(PROCESSED_DIR / "company_metadata_cleaned.json", "w") as f:
        json.dump(cleaned, f, indent=4)

def process_calamities():
    out_dir = PROCESSED_DIR / "calamities"
    os.makedirs(out_dir, exist_ok=True)
    
    eq_path = "calamity_historical_data/usgs_earthquakes_mag6plus.csv"
    if os.path.exists(eq_path):
        print("Processing earthquakes...")
        df = pd.read_csv(eq_path)
        df['time'] = pd.to_datetime(df['time'], format='mixed', utc=True)
        keep = ['time', 'latitude', 'longitude', 'depth', 'mag', 'place']
        df = df[[c for c in keep if c in df.columns]]
        df = df.dropna(subset=['time', 'mag'])
        df.to_csv(out_dir / "earthquakes_cleaned.csv", index=False)
        
    cyc_path = "calamity_historical_data/noaa_cyclones_since_2000.csv"
    if os.path.exists(cyc_path):
        print("Processing cyclones...")
        df = pd.read_csv(cyc_path, low_memory=False)
        df['ISO_TIME'] = pd.to_datetime(df['ISO_TIME'], errors='coerce', utc=True)
        df = df.dropna(subset=['ISO_TIME'])
        
        keep = ['SID', 'SEASON', 'NUMBER', 'BASIN', 'NAME', 'ISO_TIME', 'NATURE', 'LAT', 'LON', 'WMO_WIND', 'WMO_PRES']
        df = df[[c for c in keep if c in df.columns]]
        df.to_csv(out_dir / "cyclones_cleaned.csv", index=False)

def main():
    print("Starting data preprocessing...")
    print("Processing NSE market data...")
    process_ohlcv("nse_historical_data", PROCESSED_DIR / "nse_historical")
    print("Processing Macro data...")
    process_ohlcv("macro_historical_data", PROCESSED_DIR / "macro_historical")
    process_news()
    process_metadata()
    process_calamities()
    print("Preprocessing completed! All files are in data/processed/")

if __name__ == "__main__":
    main()
