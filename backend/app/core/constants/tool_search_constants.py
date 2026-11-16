"""Constants for SEARCH_TOOLS vector search (ADR-0006)."""

EMBEDDING_BACKFILL_JOB_ID: str = "backfill-tool-embeddings"
EMBEDDING_BACKFILL_BATCH: int = 64  # Tools embedded per model call
EMBEDDING_BACKFILL_INTERVAL_MINUTES: int = 10
EMBEDDING_BACKFILL_MISFIRE_GRACE_SECONDS: int = 300
