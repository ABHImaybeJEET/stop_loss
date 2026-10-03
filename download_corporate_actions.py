import os
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

NSE_DATA_DIR = "nse_historical_data"
ACTIONS_DIR = "corporate_actions_data"

def fetch_actions(ticker):
    try:
        stock = yf.Ticker(ticker)
        actions = stock.actions
        if not actions.empty:
            file_path = os.path.join(ACTIONS_DIR, f"{ticker}.csv")
            actions.to_csv(file_path)
            return True, ticker
        return False, ticker
    except Exception as e:
        return False, f"{ticker} (Error: {e})"

def download_corporate_actions():
    if not os.path.exists(NSE_DATA_DIR):
        print(f"Error: {NSE_DATA_DIR} directory not found.")
        return

    if not os.path.exists(ACTIONS_DIR):
        os.makedirs(ACTIONS_DIR)

    # Get list of all tickers we downloaded OHLCV data for
    tickers = []
    for f in os.listdir(NSE_DATA_DIR):
        if f.endswith(".csv"):
            tickers.append(f.replace(".csv", ""))

    # Check which ones are already downloaded to allow resuming
    existing_actions = [f.replace(".csv", "") for f in os.listdir(ACTIONS_DIR)]
    tickers_to_fetch = [t for t in tickers if t not in existing_actions]

    print(f"Total tickers: {len(tickers)}")
    print(f"Tickers to fetch actions for: {len(tickers_to_fetch)}")

    MAX_WORKERS = 5
    count = 0
    found_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(fetch_actions, t): t for t in tickers_to_fetch}
        
        for future in as_completed(future_to_ticker):
            success, result_ticker = future.result()
            count += 1
            
            if success:
                found_count += 1
                
            if count % 50 == 0:
                print(f"Progress: Processed {count}/{len(tickers_to_fetch)}. Found actions for {found_count} tickers.")

    print(f"Finished! Found corporate actions for {found_count} additional tickers.")

if __name__ == "__main__":
    download_corporate_actions()
