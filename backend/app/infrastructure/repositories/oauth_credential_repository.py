"""Persistence for per-server OAuth credentials (ADR-0008). Values are stored encrypted; callers see plaintext JSON."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

import app.infrastructure.database as db_module
from app.helpers.crypto import SecretCipher
from app.models.server_oauth_credential_model import ServerOAuthCredentialModel


@dataclass
class OAuthCredentialRecord:
    """Decrypted credentials of one server."""

    client_info_json: str | None = None
    tokens_json: str | None = None
    access_token_expires_at: float | None = None


class OAuthCredentialRepositoryAbstract(ABC):
    """Stores the OAuth client registration and tokens for a server."""

    @abstractmethod
    async def get(self, server_id: UUID) -> OAuthCredentialRecord | None:
        """The server's credentials, or None if it has none."""

    @abstractmethod
    async def save_client_info(self, server_id: UUID, client_info_json: str) -> None:
        """Create or replace the client registration."""

    @abstractmethod
    async def save_tokens(self, server_id: UUID, tokens_json: str, access_token_expires_at: float | None) -> None:
        """Create or replace the tokens."""


class PostgresOAuthCredentialRepository(OAuthCredentialRepositoryAbstract):
    """PostgreSQL implementation; encrypts with `cipher` on the way in and decrypts on the way out."""

    def __init__(self, cipher: SecretCipher) -> None:
        self._cipher = cipher

    async def get(self, server_id: UUID) -> OAuthCredentialRecord | None:
        async with db_module.async_session_factory() as session:
            model = await session.get(ServerOAuthCredentialModel, str(server_id))
            if model is None:
                return None
            return OAuthCredentialRecord(
                client_info_json=self._cipher.decrypt(model.client_info_enc) if model.client_info_enc else None,
                tokens_json=self._cipher.decrypt(model.tokens_enc) if model.tokens_enc else None,
                access_token_expires_at=model.access_token_expires_at,
            )

    async def save_client_info(self, server_id: UUID, client_info_json: str) -> None:
        async with db_module.async_session_factory() as session:
            model = await self._get_or_new(session, server_id)
            model.client_info_enc = self._cipher.encrypt(client_info_json)
            await session.commit()

    async def save_tokens(self, server_id: UUID, tokens_json: str, access_token_expires_at: float | None) -> None:
        async with db_module.async_session_factory() as session:
            model = await self._get_or_new(session, server_id)
            model.tokens_enc = self._cipher.encrypt(tokens_json)
            model.access_token_expires_at = access_token_expires_at
            await session.commit()

    @staticmethod
    async def _get_or_new(session, server_id: UUID) -> ServerOAuthCredentialModel:
        result = await session.execute(
            select(ServerOAuthCredentialModel).where(ServerOAuthCredentialModel.server_id == str(server_id)).with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = ServerOAuthCredentialModel(server_id=str(server_id))
            session.add(model)
        return model
