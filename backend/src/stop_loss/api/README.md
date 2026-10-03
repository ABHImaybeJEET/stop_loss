# FastAPI Backend Service (Checkpoint 5)

## Purpose & Scope
This module provides the asynchronous REST and WebSocket API serving the StopLoss Intelligence Terminal:
- **Streaming Intelligence Feeds**: Server-Sent Events (SSE) or WebSockets for live news, weather telemetry, and price ticks.
- **Agent Execution Endpoints**: Triggers multi-agent analysis runs and streams token outputs / reasoning steps to the frontend.
- **Portfolio & Risk Endpoints**: Ingests user portfolio positions and delivers VaR, scenario stress test results, and suggested hedges.
- **Audit & Provenance Endpoints**: Returns raw evidence traces, citations, and data lineage for every recommendation.
