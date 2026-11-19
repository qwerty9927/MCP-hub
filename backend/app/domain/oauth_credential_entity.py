"""OAuth credential domain entity (ADR-0008)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class OAuthCredentialEntity:
    """The OAuth client registration and tokens the hub uses for one server, decrypted."""

    server_id: UUID
    user_id: UUID  # the server's owner
    client_info_json: str | None = None  # OAuthClientInformationFull JSON
    tokens_json: str | None = None  # OAuthToken JSON
    access_token_expires_at: float | None = None  # unix seconds
