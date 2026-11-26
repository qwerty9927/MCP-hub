"""Constants for SEARCH_TOOLS vector search (ADR-0006)."""

EMBEDDING_BACKFILL_JOB_ID: str = "backfill-tool-embeddings"
EMBEDDING_BACKFILL_BATCH: int = 64  # Tools embedded per model call
EMBEDDING_BACKFILL_INTERVAL_MINUTES: int = 10
EMBEDDING_BACKFILL_MISFIRE_GRACE_SECONDS: int = 300
# pgvector >= 0.8: keep scanning the HNSW index until LIMIT is filled by rows that pass the filters, instead of
# filtering only its first hnsw.ef_search candidates. strict_order keeps results exactly ordered by distance.
HNSW_ITERATIVE_SCAN: str = "strict_order"
