"""Persistence for per-server OAuth credentials (ADR-0008). Values are stored encrypted; callers see plaintext JSON."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.infrastructure.database as db_module
from app.domain.oauth_credential_entity import OAuthCredentialEntity
from app.helpers.crypto import SecretCipher
from app.models.server_oauth_credential_model import ServerOAuthCredentialModel


class OAuthCredentialRepositoryAbstract(ABC):
    """Stores the OAuth client registration and tokens of a server, scoped to the server's owner."""

    @abstractmethod
    async def get(self, server_id: UUID, *, user_id: UUID) -> OAuthCredentialEntity | None:
        """The owner's credentials for the server, or None (also for another account's server)."""

    @abstractmethod
    async def save_client_info(self, server_id: UUID, client_info_json: str, *, user_id: UUID) -> None:
        """Create or replace the client registration."""

    @abstractmethod
    async def save_tokens(self, server_id: UUID, tokens_json: str, access_token_expires_at: float | None, *, user_id: UUID) -> None:
        """Create or replace the tokens."""


class PostgresOAuthCredentialRepository(OAuthCredentialRepositoryAbstract):
    """PostgreSQL implementation; encrypts with `cipher` on the way in and decrypts on the way out."""

    def __init__(self, cipher: SecretCipher) -> None:
        self._cipher = cipher

    async def get(self, server_id: UUID, *, user_id: UUID) -> OAuthCredentialEntity | None:
        async with db_module.async_session_factory() as session:
            result = await session.execute(_owned(server_id, user_id))
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return OAuthCredentialEntity(
                server_id=UUID(model.server_id),
                user_id=UUID(model.user_id),
                client_info_json=self._cipher.decrypt(model.client_info_enc) if model.client_info_enc else None,
                tokens_json=self._cipher.decrypt(model.tokens_enc) if model.tokens_enc else None,
                access_token_expires_at=model.access_token_expires_at,
            )

    async def save_client_info(self, server_id: UUID, client_info_json: str, *, user_id: UUID) -> None:
        async with db_module.async_session_factory() as session:
            model = await _get_or_new(session, server_id, user_id)
            model.client_info_enc = self._cipher.encrypt(client_info_json)
            await session.commit()

    async def save_tokens(self, server_id: UUID, tokens_json: str, access_token_expires_at: float | None, *, user_id: UUID) -> None:
        async with db_module.async_session_factory() as session:
            model = await _get_or_new(session, server_id, user_id)
            model.tokens_enc = self._cipher.encrypt(tokens_json)
            model.access_token_expires_at = access_token_expires_at
            await session.commit()


def _owned(server_id: UUID, user_id: UUID):
    return select(ServerOAuthCredentialModel).where(
        ServerOAuthCredentialModel.server_id == str(server_id),
        ServerOAuthCredentialModel.user_id == str(user_id),
    )


async def _get_or_new(session: AsyncSession, server_id: UUID, user_id: UUID) -> ServerOAuthCredentialModel:
    result = await session.execute(_owned(server_id, user_id).with_for_update())
    model = result.scalar_one_or_none()
    if model is None:
        model = ServerOAuthCredentialModel(server_id=str(server_id), user_id=str(user_id))
        session.add(model)
    return model
