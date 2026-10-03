import os
import json
import time
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

NSE_DATA_DIR = "nse_historical_data"
OUTPUT_FILE = "company_metadata.json"

def fetch_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        # Extract only the relevant fields to keep the JSON manageable
        metadata = {
            "ticker": ticker,
            "shortName": info.get("shortName", ""),
            "longName": info.get("longName", ""),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "marketCap": info.get("marketCap", 0),
            "longBusinessSummary": info.get("longBusinessSummary", ""),
            "city": info.get("city", ""),
            "country": info.get("country", ""),
            "fullTimeEmployees": info.get("fullTimeEmployees", 0),
            "beta": info.get("beta", None),
            "trailingPE": info.get("trailingPE", None),
            "dividendYield": info.get("dividendYield", None)
        }
        return metadata
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}

def download_fundamentals():
    if not os.path.exists(NSE_DATA_DIR):
        print(f"Error: {NSE_DATA_DIR} directory not found.")
        return

    # Get list of all tickers we downloaded
    tickers = []
    for f in os.listdir(NSE_DATA_DIR):
        if f.endswith(".csv"):
            tickers.append(f.replace(".csv", ""))

    print(f"Found {len(tickers)} tickers. Fetching fundamentals...")

    # Load existing metadata to resume if it crashed previously
    metadata_dict = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r') as f:
                metadata_dict = json.load(f)
                print(f"Loaded {len(metadata_dict)} existing entries from {OUTPUT_FILE}.")
        except:
            pass

    # Filter out already fetched tickers (unless they had an error)
    tickers_to_fetch = [t for t in tickers if t not in metadata_dict or "error" in metadata_dict[t]]
    print(f"Tickers remaining to fetch: {len(tickers_to_fetch)}")

    # We use a lower number of workers to avoid aggressive rate limiting
    MAX_WORKERS = 5
    count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(fetch_info, t): t for t in tickers_to_fetch}
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                data = future.result()
                metadata_dict[ticker] = data
                count += 1
                
                # Save progress periodically
                if count % 20 == 0:
                    with open(OUTPUT_FILE, 'w') as f:
                        json.dump(metadata_dict, f, indent=4)
                    print(f"Progress: Fetched {count}/{len(tickers_to_fetch)}...")
                    
            except Exception as e:
                print(f"Unhandled exception for {ticker}: {e}")

    # Final save
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(metadata_dict, f, indent=4)
    print("Finished downloading fundamentals!")

if __name__ == "__main__":
    download_fundamentals()
