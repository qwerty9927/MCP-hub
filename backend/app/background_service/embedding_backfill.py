"""Background job: embed Tools that have no embedding yet (ADR-0006).

Discovery embeds a Server's Tools as it stores them, but stores them without an embedding when the model
fails, so connecting a Server never fails because of search. Such Tools, and Tools stored before embeddings
existed, are not searchable; this job, run at startup and on a schedule by app/background_service/scheduler.py,
embeds them.
"""

from app.core.constants.tool_search_constants import EMBEDDING_BACKFILL_BATCH
from app.core.logging import logger
from app.infrastructure.repositories.tool_repository import ToolRepositoryAbstract
from app.services.embedding_service import EmbeddingServiceAbstract, tool_embedding_text


class EmbeddingBackfillService:
    """Embeds every stored Tool, of any account, whose embedding is NULL."""

    def __init__(self, tool_repository: ToolRepositoryAbstract, embedding_service: EmbeddingServiceAbstract) -> None:
        self._tools = tool_repository
        self._embeddings = embedding_service

    async def backfill_embeddings(self) -> int:
        """Run one backfill, in batches of EMBEDDING_BACKFILL_BATCH; returns how many Tools were embedded.

        Never raises: a failed run is logged (keeping the batches already stored) and the scheduler runs the next one on time.
        """
        embedded = 0
        try:
            while tools := await self._tools.list_tools_without_embedding(EMBEDDING_BACKFILL_BATCH):
                vectors = await self._embeddings.embed_documents([tool_embedding_text(tool) for tool in tools])
                await self._tools.set_embeddings({tool.id: vector for tool, vector in zip(tools, vectors, strict=True)})
                embedded += len(tools)
        except Exception as exc:
            logger.error(f"Could not backfill tool embeddings: {exc}")
        if embedded:
            logger.info(f"Backfilled embeddings for {embedded} tool(s)")
        return embedded
