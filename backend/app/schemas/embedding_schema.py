"""Embedding model descriptions for tool search (ADR-0006, ADR-0010)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingModelSpec:
    """One embedding model as each source names it. Both sources run the same weights, so their vectors match."""

    dimension: int
    local_id: str  # fastembed model name (EMBEDDING_PROVIDER=local)
    cloudflare_id: str  # Workers AI model id (EMBEDDING_PROVIDER=cloudflare)
    # Workers AI pooling ("cls" or "mean") that reproduces the local model's vectors
    cloudflare_pooling: str
