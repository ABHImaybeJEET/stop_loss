# StopLoss Intelligence: Data Contracts

This document formalizes the canonical data models, contracts, and schema invariants across the StopLoss Intelligence platform.

## 1. Domain Enums

### `DataType`
Categorizes every ingested intelligence observation:
- `weather`: Meteorological data, forecasts, hurricane tracks, wind/wave telemetry.
- `news`: Geopolitical events, financial news, regulatory announcements, operational notices.
- `market_price`: Financial instrument pricing, equity quotes, futures, options implied volatility.
- `macro`: Macroeconomic benchmarks, interest rates, inflation figures, inventory levels.

### `RunStatus`
Tracks the lifecycle of ingestion executions:
- `running`: Ingestion cycle is actively fetching or persisting data.
- `success`: Ingestion cycle finished with zero unhandled errors.
- `partial_success`: Some records succeeded but non-fatal errors or partial drops occurred.
- `failed`: Provider crashed or failed critically without completing ingestion.

### `ProviderErrorType`
Standardized categorization of external data provider failures:
- `timeout`: External API or network socket timed out.
- `rate_limit`: Provider rate limit or throttle ceiling hit (HTTP 429).
- `authentication`: API key, OAuth token, or signature rejection (HTTP 401/403).
- `invalid_response`: Non-JSON response, corrupt payload, or schema mismatch.
- `unavailable`: External provider endpoint down or unreachable (HTTP 502/503/504).
- `unknown`: Unclassified or internal exception.

---

## 2. Normalized Record (`NormalizedRecord`)

All external data sources are normalized into `NormalizedRecord` prior to persistence.

| Field | Type | Required | Description |
|---|---|---|---|
| `record_id` | `str` | Yes | Unique identifier (e.g. UUIDv4 or deterministic hash). |
| `data_type` | `DataType` | Yes | Domain data type (`weather`, `news`, `market_price`, `macro`). |
| `provider` | `str` | Yes | Source identifier (e.g. `open_meteo`, `gdelt`, `yahoo_finance`, `fred`). |
| `observed_at` | `datetime` | Yes | Timezone-aware UTC timestamp of actual physical/market event. |
| `fetched_at` | `datetime` | Yes | Timezone-aware UTC timestamp when StopLoss ingested the record. |
| `entity` | `str \| None` | No | Associated company, facility, or organization (e.g. "ExxonMobil"). |
| `ticker` | `str \| None` | No | Asset symbol or ticker (e.g. `XOM`, `XLE`, `NG=F`). |
| `location` | `str \| None` | No | Geographic coordinates or named place (e.g. "Corpus Christi, Texas"). |
| `indicator` | `str \| None` | No | Specific metric or series name (e.g. `wind_speed_10m`, `headline`). |
| `numeric_value` | `float \| None` | Conditional | Floating-point value of metric. At least one of numeric or text is required. |
| `text_value` | `str \| None` | Conditional | Textual body or title. At least one of numeric or text is required. |
| `unit` | `str \| None` | No | Measurement unit (e.g. `USD`, `knots`, `mb`, `percent`). |
| `source_url` | `str \| None` | No | Source URL for verification, attribution, and agent audit trails. |
| `raw_payload` | `dict[str, Any]` | No | Raw unmodified payload for provenance (defaults to `{}`). |
| `metadata` | `dict[str, Any]` | No | Extensible metadata bag (defaults to `{}`). |
| `is_demo` | `bool` | No | Flag indicating synthetic/historical demo data (defaults to `False`). |

### Model Invariants:
1. Both `observed_at` and `fetched_at` **must be timezone-aware**; naive datetimes are rejected with `ValidationError`.
2. At least one of `numeric_value` or `text_value` **must be non-None**.
3. All default dictionary fields (`raw_payload`, `metadata`) are created via `default_factory=dict` to prevent mutable default bugs.

---

## 3. Ingestion Run (`IngestionRun`)

Maintains an immutable execution audit log for every provider invocation.

| Field | Type | Default | Description |
|---|---|---|---|
| `run_id` | `str` | Required | Unique run identifier. |
| `provider` | `str` | Required | Target provider identifier. |
| `started_at` | `datetime` | Required | Timezone-aware timestamp when run started. |
| `finished_at` | `datetime \| None` | `None` | Timezone-aware timestamp when run ended. |
| `status` | `RunStatus` | `RunStatus.RUNNING` | Current status of the run. |
| `records_fetched` | `int` | `0` | Count of records fetched. |
| `records_inserted` | `int` | `0` | Count of new records inserted into database. |
| `records_updated` | `int` | `0` | Count of existing records updated. |
| `records_skipped` | `int` | `0` | Count of duplicate/filtered records. |
| `error_type` | `ProviderErrorType \| None` | `None` | Categorized error if run failed. |
| `error_message` | `str \| None` | `None` | Detailed error message or traceback. |

---

## 4. Provider Contract (`DataProvider`)

All data source adapters implement:
- `name: str` (property): Canonical identifier.
- `data_type: DataType` (property): Emitted data type.
- `fetch(**kwargs: Any) -> Any`: Calls external API and returns raw payload.
- `normalize(raw_data: Any) -> list[NormalizedRecord]`: Pure function transforming raw payload to `NormalizedRecord` models.

---

## 5. Storage Contract (`RecordRepository`)

Abstract interface decoupling storage technology from domain logic:
- `initialize() -> None`
- `upsert_record(record: NormalizedRecord) -> None`
- `bulk_upsert_records(records: Sequence[NormalizedRecord]) -> int`
- `get_record_by_id(record_id: str) -> NormalizedRecord | None`
- `get_records_by_type(data_type: DataType, limit: int = 100) -> list[NormalizedRecord]`
- `get_records_by_provider(provider: str, limit: int = 100) -> list[NormalizedRecord]`
- `get_records_by_entity_or_ticker(query: str, limit: int = 100) -> list[NormalizedRecord]`
- `get_records_by_time_range(start: datetime, end: datetime, limit: int = 100) -> list[NormalizedRecord]`
- `search_records(query: str, limit: int = 100) -> list[NormalizedRecord]`
- `save_ingestion_run(run: IngestionRun) -> None`
- `list_recent_ingestion_runs(limit: int = 20) -> list[IngestionRun]`
