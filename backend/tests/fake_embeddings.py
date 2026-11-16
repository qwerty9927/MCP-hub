"""A deterministic stand-in for the fastembed model, so tests need no model download."""

import hashlib
import re

from app.core.config import get_settings
from app.services.embedding_service import EmbeddingServiceAbstract, normalize

_STOP_WORDS = {"a", "an", "the", "of", "to", "and", "or", "for", "in", "on", "with", "server"}


class FakeEmbeddingService(EmbeddingServiceAbstract):
    """Hashed bag of words: texts sharing words get similar vectors, so ranking still means something."""

    def __init__(self, dimension: int | None = None) -> None:
        self._dimension = dimension or get_settings().EMBEDDING_DIMENSION

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        words = [w for w in re.split(r"[^a-z0-9]+", text.lower()) if w and w not in _STOP_WORDS]
        for word in words or ["<empty>"]:
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % self._dimension] += 1.0
        return normalize(vector)


class FailingEmbeddingService(FakeEmbeddingService):
    """Fails every call, as when the model cannot be loaded."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("model unavailable")

    async def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("model unavailable")
