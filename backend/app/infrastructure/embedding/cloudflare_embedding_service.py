"""EMBEDDING_PROVIDER=cloudflare: the same model, run by Cloudflare Workers AI (ADR-0010)."""

import asyncio
import json
import time
from typing import Any

from app.core.constants.cloudflare_constants import CLOUDFLARE_MAX_BATCH_PAYLOAD_BYTES, CLOUDFLARE_MAX_TEXTS_PER_REQUEST
from app.infrastructure.cloudflare.workers_ai_client import CloudflareWorkersAIClient
from app.infrastructure.embedding.embedding_service import EmbeddingServiceAbstract, check_dimension


class CloudflareEmbeddingService(EmbeddingServiceAbstract):
    """Embeds through Workers AI, in requests of at most CLOUDFLARE_MAX_TEXTS_PER_REQUEST texts."""

    def __init__(
        self,
        client: CloudflareWorkersAIClient,
        model_id: str,
        dimension: int,
        pooling: str,
        *,
        batch_poll_interval_seconds: float,
        batch_timeout_seconds: float,
    ) -> None:
        self._client = client
        self._model_id = model_id
        self._dimension = dimension
        self._pooling = pooling  # from EMBEDDING_MODELS: the pooling that matches the local model's vectors
        self._poll_interval = batch_poll_interval_seconds  # CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS
        self._batch_timeout = batch_timeout_seconds  # CLOUDFLARE_BATCH_TIMEOUT_SECONDS

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), CLOUDFLARE_MAX_TEXTS_PER_REQUEST):
            vectors.extend(await self._embed(texts[start : start + CLOUDFLARE_MAX_TEXTS_PER_REQUEST]))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        [vector] = await self._embed([text])
        return vector

    async def embed_documents_queued(self, texts: list[str]) -> list[list[float]]:
        """One Batch API submission holding every chunk of texts, polled until done (ADR-0010).

        Raises TimeoutError after CLOUDFLARE_BATCH_TIMEOUT_SECONDS; the batch is then abandoned and its Tools stay
        unembedded for the next backfill to resubmit.
        """
        if not texts:
            return []
        chunks = [
            texts[start : start + CLOUDFLARE_MAX_TEXTS_PER_REQUEST] for start in range(0, len(texts), CLOUDFLARE_MAX_TEXTS_PER_REQUEST)
        ]
        requests = [{"text": chunk, "pooling": self._pooling} for chunk in chunks]
        size = len(json.dumps({"requests": requests}).encode())
        if size >= CLOUDFLARE_MAX_BATCH_PAYLOAD_BYTES:
            raise ValueError(f"Batch of {len(texts)} texts is {size} bytes; the Batch API takes under {CLOUDFLARE_MAX_BATCH_PAYLOAD_BYTES}")

        request_id = await self._client.submit_batch(self._model_id, requests)
        deadline = time.monotonic() + self._batch_timeout
        while (responses := await self._client.poll_batch(self._model_id, request_id)) is None:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Batch {request_id} for '{self._model_id}' not done after {self._batch_timeout:g}s")
            await asyncio.sleep(self._poll_interval)

        by_id = {response.get("id"): response for response in responses if isinstance(response, dict)}
        vectors: list[list[float]] = []
        for index, chunk in enumerate(chunks):
            response = by_id.get(index)
            if response is None or not response.get("success") or not isinstance(response.get("result"), dict):
                raise ValueError(f"Batch {request_id} for '{self._model_id}' has no successful result for request {index}")
            vectors.extend(self._vectors(response["result"], len(chunk)))
        return vectors

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        result = await self._client.run(self._model_id, {"text": texts, "pooling": self._pooling})
        return self._vectors(result, len(texts))

    def _vectors(self, result: dict[str, Any], expected: int) -> list[list[float]]:
        """The `data` rows of one embedding result, checked and normalized."""
        data: Any = result.get("data")
        if not isinstance(data, list) or len(data) != expected:
            got = len(data) if isinstance(data, list) else "no"
            raise ValueError(f"Embedding model '{self._model_id}' returned {got} vectors for {expected} texts")
        return [check_dimension(vector, model=self._model_id, dimension=self._dimension) for vector in data]
