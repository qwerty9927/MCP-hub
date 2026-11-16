"""Text embeddings for tool search (ADR-0006): a local fastembed model, vectors stored in pgvector."""

import asyncio
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import BASE_DIR
from app.core.logging import logger
from app.domain.tool_entity import ToolEntity


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
        if len(vector) != self._dimension:
            raise ValueError(
                f"Embedding model '{self._model_name}' returns {len(vector)} dimensions, but EMBEDDING_DIMENSION is {self._dimension}"
            )
        return normalize(vector)


async def warm_up(service: EmbeddingServiceAbstract) -> None:
    """Load the model now, so the first search is not slow, and fail fast if it returns the wrong dimension.

    Any other failure (model not downloadable, say) is logged; search and discovery then retry on use.
    """
    try:
        await service.embed_query("warmup")
    except ValueError:
        raise
    except Exception as exc:
        logger.error(f"Could not load the embedding model; SEARCH_TOOLS will fail until it loads: {exc}")
        return
    logger.info(f"Embedding model ready ({service.dimension} dimensions)")


def normalize(vector: Any) -> list[float]:
    """Scale to unit length, so cosine similarity is a plain dot product."""
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    return (array / norm if norm else array).tolist()


def tool_embedding_text(tool: ToolEntity) -> str:
    """The text a Tool is embedded from: its name, Server, description and parameters."""
    parts = [tool.name.replace("_", " "), f"server: {tool.server_name}"]
    if tool.description:
        parts.append(tool.description)
    properties = (tool.input_schema or {}).get("properties")
    if isinstance(properties, dict):
        for name, spec in properties.items():
            description = spec.get("description") if isinstance(spec, dict) else None
            parts.append(f"{name}: {description}" if description else str(name))
    return "\n".join(parts)
