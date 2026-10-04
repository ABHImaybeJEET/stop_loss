# Live ingestion latency report

Generated 2026-10-04 05:38 UTC by `make latency` (`stop-loss-vectors latency`) on Windows AMD64.

- Records measured: **96** over 129 s (scratch namespace `live-latency`, emptied first; no dedupe).
- Embedder: OnnxEmbeddings (BAAI/bge-base-en-v1.5); micro-batch size 1; sources probed one at a time so no probe traffic overlaps a measured write.
- Over budget: p95 process+embed+index 1,015 ms ≥ 1,000 ms. Local share (embed) p95 158 ms; Pinecone write round trip p95 937 ms.
- Queryable = time from the upsert acknowledgement until a `content_hash`-filtered query returns the record (polled every 250 ms). 0 record(s) were not observed within the timeout and are excluded from that row (not imputed).
- `fetch` is per poll (all items of one poll share it); embed/upsert are per micro-batch, which is the latency each item in it experiences.
- Network floor: a bare Pinecone `describe_index_stats` round trip from this machine took p50 243 ms / min 240 ms (n=10). Every upsert pays at least this, so the index leg is bounded by the distance to the index region.

## All sources

| stage | n | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|---:|
| fetch (per poll) | 96 | 1,816 | 2,835 | 2,835 |
| embed (micro-batch) | 96 | 93 | 158 | 195 |
| upsert (micro-batch) | 96 | 368 | 937 | 1,813 |
| process = embed + upsert | 96 | 482 | 1,015 | 1,966 |
| upsert ack → queryable | 96 | 724 | 2,251 | 3,332 |
| end-to-end (fetch → queryable) | 96 | 3,391 | 5,735 | 7,126 |

## gdacs

| stage | n | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|---:|
| fetch (per poll) | 24 | 1,816 | 1,816 | 1,816 |
| embed (micro-batch) | 24 | 112 | 154 | 195 |
| upsert (micro-batch) | 24 | 365 | 396 | 408 |
| process = embed + upsert | 24 | 478 | 560 | 561 |
| upsert ack → queryable | 24 | 723 | 783 | 1,202 |
| end-to-end (fetch → queryable) | 24 | 2,996 | 3,100 | 3,579 |

## news

| stage | n | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|---:|
| fetch (per poll) | 24 | 2,765 | 2,765 | 2,765 |
| embed (micro-batch) | 24 | 63 | 114 | 126 |
| upsert (micro-batch) | 24 | 368 | 550 | 558 |
| process = embed + upsert | 24 | 450 | 608 | 644 |
| upsert ack → queryable | 24 | 245 | 816 | 830 |
| end-to-end (fetch → queryable) | 24 | 3,473 | 4,108 | 4,133 |

## usgs

| stage | n | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|---:|
| fetch (per poll) | 24 | 844 | 844 | 844 |
| embed (micro-batch) | 24 | 91 | 180 | 191 |
| upsert (micro-batch) | 24 | 365 | 396 | 509 |
| process = embed + upsert | 24 | 471 | 564 | 637 |
| upsert ack → queryable | 24 | 237 | 800 | 907 |
| end-to-end (fetch → queryable) | 24 | 1,578 | 2,215 | 2,256 |

## weather

| stage | n | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|---:|
| fetch (per poll) | 24 | 2,835 | 2,835 | 2,835 |
| embed (micro-batch) | 24 | 80 | 153 | 158 |
| upsert (micro-batch) | 24 | 682 | 1,789 | 1,813 |
| process = embed + upsert | 24 | 756 | 1,903 | 1,966 |
| upsert ack → queryable | 24 | 1,042 | 2,601 | 3,332 |
| end-to-end (fetch → queryable) | 24 | 4,748 | 6,835 | 7,126 |
