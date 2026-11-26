"""Background job: embed Tools that have no embedding yet (ADR-0006).

Discovery embeds a Server's Tools as it stores them, but stores them without an embedding when the model
fails, so connecting a Server never fails because of search. Such Tools, and Tools stored before embeddings
existed, are not searchable; this job, run at startup and on a schedule by app/background_service/scheduler.py,
embeds them.
"""

from app.core.logging import logger
from app.infrastructure.embedding.embedding_service import EmbeddingServiceAbstract
from app.infrastructure.repositories.tool_repository import ToolRepositoryAbstract
from app.services.tool_catalog import tool_embedding_text


class EmbeddingBackfillService:
    """Embeds every stored Tool, of any account, whose embedding is NULL."""

    def __init__(
        self,
        tool_repository: ToolRepositoryAbstract,
        embedding_service: EmbeddingServiceAbstract,
        batch_size: int,
        *,
        queued: bool = False,
    ) -> None:
        self._tool_repository = tool_repository
        self._embedding_service = embedding_service
        self._batch_size = batch_size
        # EMBEDDING_BACKFILL_QUEUED: the provider's batch queue (no hurry here) instead of direct calls
        self._embed = embedding_service.embed_documents_queued if queued else embedding_service.embed_documents

    async def backfill_embeddings(self) -> int:
        """Run one backfill, in batches of `batch_size` (EMBEDDING_BACKFILL_BATCH); returns how many Tools were embedded.

        A failure raises after the batches already stored are kept: the scheduler's logged_job logs the run as
        failed and the next one picks up the Tools still without an embedding.
        """
        embedded = 0
        try:
            while tools := await self._tool_repository.list_tools_without_embedding(self._batch_size):
                vectors = await self._embed([tool_embedding_text(tool) for tool in tools])
                await self._tool_repository.set_embeddings({tool.id: vector for tool, vector in zip(tools, vectors, strict=True)})
                embedded += len(tools)
        except Exception:
            if embedded:
                logger.warning(f"Backfill stopped after embedding {embedded} tool(s); the rest are retried on the next run")
            raise
        return embedded
