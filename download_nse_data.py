import os
import requests
import pandas as pd
import yfinance as yf
from io import StringIO
import time
from datetime import datetime

# URL for NSE equity list
NSE_EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

# Directory to save the data
DATA_DIR = "nse_historical_data"

def get_nse_tickers():
    print("Fetching list of currently traded NSE stocks...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(NSE_EQUITY_URL, headers=headers, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        
        # The 'SYMBOL' column contains the ticker symbol
        # We append '.NS' for yfinance
        tickers = df['SYMBOL'].astype(str) + ".NS"
        return tickers.tolist()
    except Exception as e:
        print(f"Error fetching NSE ticker list: {e}")
        return []

def download_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    tickers = get_nse_tickers()
    if not tickers:
        print("No tickers found. Exiting.")
        return

    print(f"Found {len(tickers)} tickers. Starting download...")
    
    # We will process in batches to avoid overwhelming memory/API
    # but yf.download is efficient with multiple tickers. 
    # To handle failures gracefully and store separately, we will download chunk by chunk.
    
    batch_size = 50
    total_tickers = len(tickers)
    
    # For testing/demonstration, we might just want to download the first few batches 
    # or let it run fully. It will take some time.
    
    for i in range(0, total_tickers, batch_size):
        batch = tickers[i:i+batch_size]
        print(f"Downloading batch {i//batch_size + 1}/{(total_tickers + batch_size - 1)//batch_size} ({i} to {min(i+batch_size, total_tickers)})...")
        
        try:
            # group_by="ticker" will give us a MultiIndex dataframe
            data = yf.download(batch, period="max", interval="1d", group_by="ticker", threads=True, progress=False)
            
            # Save each ticker's data
            for ticker in batch:
                try:
                    # If batch has only 1 ticker, the structure is different
                    if len(batch) == 1:
                        df = data
                    else:
                        df = data[ticker]
                        
                    # Drop NaN rows (e.g. if a stock started trading recently, older dates will be NaN)
                    df = df.dropna(how='all')
                    
                    if not df.empty:
                        # Save to CSV (can use Parquet for better performance in prod)
                        file_path = os.path.join(DATA_DIR, f"{ticker}.csv")
                        df.to_csv(file_path)
                except Exception as e:
                    print(f"  -> Could not process {ticker} from batch: {e}")
                    
        except Exception as e:
            print(f"Error downloading batch: {e}")
            
        # Small sleep to respect rate limits
        time.sleep(1)

    print("Download complete.")

if __name__ == "__main__":
    download_data()
