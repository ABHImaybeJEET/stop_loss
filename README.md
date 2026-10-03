# Financial Intelligence Terminal: Stop Loss

This project is an AI-powered financial intelligence terminal that continuously ingests global news feeds, real-time weather, and historical market data to forecast equity and commodity impacts using an autonomous multi-agent portfolio management system.

## Overview
- **Data Ingestion Pipeline:** Connects to Financial APIs (yfinance, etc.) and Weather APIs, backed by a Vector Database.
- **Multi-Agent Engine:** Stateful agentic orchestration system for sentiment analysis, macro impact analytics, and quantitative risk modeling.
- **Interactive Terminal:** Dynamic dashboard to display multi-agent execution graphs, interactive charts, and risk exposure breakdowns.

## Data Sources
- **Equities:** NSE (National Stock Exchange of India) via yfinance.
- **Macro Proxies:** Indices (^NSEI, ^INDIAVIX, ^TNX), Commodities (CL=F, NG=F, GC=F), Currencies (INR=X).
