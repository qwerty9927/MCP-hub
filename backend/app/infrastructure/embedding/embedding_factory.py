"""Builds the embedding service EMBEDDING_PROVIDER names (ADR-0010). The only module that reads the setting."""

from app.core.config import Settings
from app.infrastructure.cloudflare.workers_ai_client import CloudflareWorkersAIClient
from app.infrastructure.embedding.cloudflare_embedding_service import CloudflareEmbeddingService
from app.infrastructure.embedding.embedding_service import EmbeddingServiceAbstract
from app.infrastructure.embedding.fastembed_service import FastEmbedService


def create_embedding_service(settings: Settings) -> EmbeddingServiceAbstract:
    """The EMBEDDING_MODEL, run by EMBEDDING_PROVIDER. Settings validation has already checked both."""
    spec = settings.embedding_model_spec
    if settings.EMBEDDING_PROVIDER == "cloudflare":
        client = CloudflareWorkersAIClient(
            account_id=settings.CLOUDFLARE_ACCOUNT_ID,
            api_token=settings.CLOUDFLARE_API_TOKEN,
            base_url=settings.CLOUDFLARE_API_BASE_URL,
            timeout_seconds=settings.CLOUDFLARE_REQUEST_TIMEOUT_SECONDS,
        )
        return CloudflareEmbeddingService(
            client=client,
            model_id=spec.cloudflare_id,
            dimension=spec.dimension,
            pooling=spec.cloudflare_pooling,
            batch_poll_interval_seconds=settings.CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS,
            batch_timeout_seconds=settings.CLOUDFLARE_BATCH_TIMEOUT_SECONDS,
        )
    return FastEmbedService(model_name=spec.local_id, dimension=spec.dimension, cache_dir=settings.EMBEDDING_CACHE_DIR)
