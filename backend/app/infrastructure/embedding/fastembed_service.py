"""EMBEDDING_PROVIDER=local: a fastembed ONNX model run in the hub process (ADR-0006, ADR-0010)."""

import asyncio
import threading
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR
from app.core.logging import logger
from app.infrastructure.embedding.embedding_service import EmbeddingServiceAbstract, check_dimension


class FastEmbedService(EmbeddingServiceAbstract):
    """Runs a fastembed ONNX model in-process. The model is loaded on first use; inference runs in a worker thread."""

    def __init__(self, model_name: str, dimension: int, cache_dir: str) -> None:
        self._model_name = model_name
        self._dimension = dimension
        path = Path(cache_dir)
        self._cache_dir = str(path if path.is_absolute() else BASE_DIR / path)
        self._model: Any = None
        self._load_lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._passages, texts)

    async def embed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._query, text)

    def _get_model(self) -> Any:
        with self._load_lock:
            if self._model is None:
                from fastembed import TextEmbedding  # heavy import, only when embeddings are first needed

                logger.info(f"Loading embedding model '{self._model_name}' (cache: {self._cache_dir})")
                self._model = TextEmbedding(model_name=self._model_name, cache_dir=self._cache_dir)
            return self._model

    def _passages(self, texts: list[str]) -> list[list[float]]:
        return [self._check(vector) for vector in self._get_model().passage_embed(texts)]

    def _query(self, text: str) -> list[float]:
        return self._check(next(iter(self._get_model().query_embed(text))))

    def _check(self, vector: Any) -> list[float]:
        return check_dimension(vector, model=self._model_name, dimension=self._dimension)
