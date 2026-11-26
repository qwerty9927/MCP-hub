# ADR 0006: SEARCH_TOOLS Ranks Tools by Vector Similarity in pgvector

## Status
Accepted.

## Date
2026-11-16

## Context
`SEARCH_TOOLS` ranked Tools with a hand-written keyword scorer. Each call loaded up to 1000 of the account's Tools into memory and scored them in Python by shared words and substrings. It found only Tools whose name, description or parameters used the query's words: "open a ticket" never found `create_issue`. Agents phrase queries in their own words, so word overlap is a weak signal.

## Decision
1. **Every Tool has an embedding.** `discovered_tools.embedding` is a `vector(384)` (pgvector) of the Tool's name, Server name, description and parameter names and descriptions (`tool_embedding_text`).
2. **Embeddings come from a local model.** fastembed runs `BAAI/bge-small-en-v1.5` (ONNX) in the hub process, in a worker thread. It is configured by `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` and `EMBEDDING_CACHE_DIR`. The model is loaded and checked at startup; the Docker image ships it pre-downloaded.
3. **Ranking is vector only.** Each query is embedded and the database returns the caller's `top_k` nearest Tools by cosine distance (HNSW index `vector_cosine_ops`), filtered in the same query to the owner, enabled Servers, and AVAILABLE Tools. The keyword scorer is removed. Each result carries its `similarity`. The query runs with `SET LOCAL hnsw.iterative_scan = strict_order` (pgvector ≥ 0.8): the index applies filters after collecting `hnsw.ef_search` (40) candidates across all accounts, so without iterative scans a caller whose Tools are not among them would get fewer than `top_k`, or none.
4. **Search never blocks discovery.** Tools are embedded when their Server is discovered; if embedding fails they are stored without one and are not searchable until a backfill embeds them. The backfill, `EmbeddingBackfillService` in `app/background_service/embedding_backfill.py`, runs at startup and every 10 minutes (job `backfill-tool-embeddings`), alongside the session sweeper (ADR-0005).

## Why
- **pgvector over an in-memory index:** the catalog already lives in Postgres, and filtering by owner, enabled Server and availability belongs in the same query as the ranking. No second store to keep in sync.
- **A local model over an embeddings API:** no API key, no per-call cost, no network dependency at query time, and tool metadata never leaves the hub.
- **Vector only over hybrid:** one ranking signal is simpler to reason about and to tune. Agents are told to search by action, which is what embeddings match well.

## Consequences
- An exact tool name is no longer guaranteed to rank first; it usually does, because the name is part of the embedded text.
- The first start downloads the model (about 64 MB) unless the image ships it; each process holds it in memory.
- The column's dimension is fixed by migration: changing `EMBEDDING_MODEL` to one of another size needs a migration that resizes the column, after which the backfill re-embeds every Tool.
- Postgres must run pgvector 0.8 or later (the `pgvector/pgvector:pg17` image does); older versions reject `hnsw.iterative_scan`. An iterative scan is still bounded (`hnsw.max_scan_tuples`, and `work_mem` × `hnsw.scan_mem_multiplier`), so a very large shared table could still return fewer than `top_k` for a small account; raising those, or partitioning by account, is the next step if that happens.
- Every query returns its `top_k` nearest Tools, however weak the match. A minimum similarity can be added later if results get noisy.
