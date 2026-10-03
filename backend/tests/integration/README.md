# Integration Tests

This directory houses end-to-end and multi-component integration tests:
- Live/mocked database persistence cycles (`SQLiteRecordRepository`).
- End-to-end ingestion pipeline execution with real or recorded HTTP fixtures.
- Multi-agent workflow integration tests with LangGraph.
- FastAPI endpoint testing via `httpx.AsyncClient`.
