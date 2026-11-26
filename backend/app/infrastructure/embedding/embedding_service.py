"""The embedding port for tool search (ADR-0006): text in, unit-length vectors out, stored in pgvector.

Services depend on EmbeddingServiceAbstract only. Its implementations, one per EMBEDDING_PROVIDER (ADR-0010), live
next to it, and embedding_factory.create_embedding_service picks one when the app is wired up.
"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from app.core.logging import logger


class EmbeddingServiceAbstract(ABC):
    """Turns text into unit-length vectors of `dimension` floats."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Length of every vector this service returns."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed texts that will be searched (tool descriptions)."""

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query."""

    async def embed_documents_queued(self, texts: list[str]) -> list[list[float]]:
        """Embed texts where waiting is fine (the backfill): a provider with a batch queue may take minutes.

        Same result as embed_documents. Providers without a queue just call it.
        """
        return await self.embed_documents(texts)

    async def aclose(self) -> None:  # noqa: B027 - optional hook: only services holding connections override it
        """Release what the service holds (an HTTP client, say). Called once at shutdown."""


async def warm_up(embedding_service: EmbeddingServiceAbstract) -> None:
    """Embed once now, so the first search is not slow, and fail fast if the model returns the wrong dimension.

    Any other failure (model not downloadable, API unreachable, say) is logged; search and discovery then retry on use.
    """
    try:
        await embedding_service.embed_query("warmup")
    except ValueError:
        raise
    except Exception as exc:
        logger.error(f"Could not reach the embedding model; SEARCH_TOOLS will fail until it does: {exc}")
        return
    logger.info(f"Embedding model ready ({embedding_service.dimension} dimensions)")


def normalize(vector: Any) -> list[float]:
    """Scale to unit length, so cosine similarity is a plain dot product."""
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    return (array / norm if norm else array).tolist()


def check_dimension(vector: Any, *, model: str, dimension: int) -> list[float]:
    """The vector, normalized, after checking it has `dimension` floats."""
    if len(vector) != dimension:
        raise ValueError(f"Embedding model '{model}' returns {len(vector)} dimensions, but EMBEDDING_DIMENSION is {dimension}")
    return normalize(vector)
