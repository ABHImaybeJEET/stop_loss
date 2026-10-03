import os
import yfinance as yf
import pandas as pd

# Directory to save macro data
DATA_DIR = "macro_historical_data"

MACRO_TICKERS = {
    # Commodities
    'Brent Crude': 'BZ=F',
    'WTI Crude': 'CL=F',
    'Natural Gas': 'NG=F',
    'Heating Oil': 'HO=F',
    'RBOB Gasoline': 'RB=F',
    'Gold': 'GC=F',
    'Silver': 'SI=F',
    'Copper': 'HG=F',
    'Platinum': 'PL=F',
    'Palladium': 'PA=F',
    'Wheat': 'ZW=F',
    'Sugar': 'SB=F',
    'Cotton': 'CT=F',
    'Corn': 'ZC=F',
    'Soybeans': 'ZS=F',

    # Indices
    'Nifty 50': '^NSEI',
    'Nifty Bank': '^NSEBANK',
    'BSE Sensex': '^BSESN',
    'S&P 500': '^GSPC',
    'Nasdaq 100': '^NDX',
    'Dow Jones': '^DJI',
    'Hang Seng': '^HSI',
    'Shanghai Composite': '000001.SS',

    # Volatility
    'India VIX': '^INDIAVIX',
    'US VIX': '^VIX',
    'Nasdaq VIX': '^VXN',
    'Oil VIX': '^OVX',
    'Gold VIX': '^GVZ',

    # Currencies
    'USD_INR': 'INR=X',
    'US Dollar Index': 'DX-Y.NYB',
    'EUR_INR': 'EURINR=X',
    'GBP_INR': 'GBPINR=X',
    'USD_CNY': 'CNY=X',

    # Bonds & Yields
    'US 10-Yr Yield': '^TNX',
    'US 5-Yr Yield': '^FVX',
    'US 30-Yr Yield': '^TYX',
    'US 13-Week Bill': '^IRX'
}

def download_macro_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    tickers_list = list(MACRO_TICKERS.values())
    print(f"Downloading data for {len(tickers_list)} macro indicators...")

    # Download in bulk
    data = yf.download(tickers_list, period="max", interval="1d", group_by="ticker", threads=True, progress=False)

    for name, ticker in MACRO_TICKERS.items():
        try:
            # If downloading multiple tickers, pandas returns a MultiIndex column dataframe
            if len(tickers_list) == 1:
                df = data
            else:
                df = data[ticker]

            df = df.dropna(how='all')
            if not df.empty:
                # Save using the ticker symbol, replacing invalid characters if any (like ^ or =)
                safe_ticker = ticker.replace('^', '').replace('=', '_')
                file_path = os.path.join(DATA_DIR, f"{safe_ticker}.csv")
                df.to_csv(file_path)
                print(f"Saved {name} ({ticker}) to {file_path}")
            else:
                print(f"No data found for {name} ({ticker})")
        except Exception as e:
            print(f"Error saving {name} ({ticker}): {e}")

if __name__ == "__main__":
    download_macro_data()
