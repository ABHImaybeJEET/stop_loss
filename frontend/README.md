# StopLoss Intelligence Terminal Frontend (Checkpoint 5)

## Overview & Responsibility
The `frontend` directory will house the Next.js interactive financial intelligence terminal.
In accordance with **Checkpoint 0 (Project Foundation)**, code generation for the Next.js application is deferred to Checkpoint 5.

## Intended Dashboard Capabilities
- **Multi-Panel Terminal Layout**: Bloomberg/Refinitiv-inspired financial dashboard with dark mode and high-density data visualizations.
- **Geographic Threat Map**: Real-time NOAA/Open-Meteo hurricane tracking overlaid on Gulf of Mexico offshore rigs, pipelines, and coastal refineries.
- **Live News & Sentiment Ticker**: Streaming sentiment feeds with highlighted disruption indicators.
- **Macro & Market Correlation View**: Interactive charting correlating commodity spikes with equity sector drawdowns.
- **Portfolio Risk & Hedging Studio**:
  - Position entry and stress test simulator.
  - Value at Risk (VaR) distribution curves.
  - Actionable hedging recommendations with one-click audit trails and source evidence citations.
- **AI Agent Collaboration Inspector**: Visual trace showing how the multi-agent graph deliberated and arrived at hedging strategies.

## Technology Stack (Checkpoint 5)
- Next.js (App Router)
- React 19 / TypeScript
- TailwindCSS / Lucide Icons
- TradingView / Lightweight Charts / Recharts
- Mapbox GL / Deck.gl for weather and asset overlays
