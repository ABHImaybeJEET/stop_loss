# Test Fixtures

This directory contains static test payloads and replay fixtures:
- `weather_gulf_hurricane.json`: Sample Open-Meteo response simulating severe tropical storm conditions in the Gulf.
- `news_gdelt_sample.json`: Sample GDELT article feed covering refinery shut-ins and oil platform evacuations.
- `market_yfinance_sample.json`: Historical price data for energy equities (XLE, XOM, CVX) and natural gas futures (NG=F).
- `macro_fred_sample.json`: Benchmark macro series observations (DCOILWTICO, CPI, FEDFUNDS).
# Scaffold fixtures

`stub_sources.json` records the empty responses of all six scaffold connectors.
`normalized_news.json` and `vector_responses.json` are explicitly synthetic test
contracts, not live market data or recordings from a provider. Real connector
implementations must add sanitized recorded responses here when introduced.
