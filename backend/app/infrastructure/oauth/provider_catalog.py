"""The catalog of hosted MCP servers a user can connect with OAuth (`oauth_providers.json` beside this file)."""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

CATALOG_PATH = Path(__file__).resolve().parent / "oauth_providers.json"


class OAuthProvider(BaseModel):
    """One hosted MCP server in the catalog."""

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]{0,49}$")
    name: str
    description: str
    category: str
    mcp_url: str
    docs_url: str | None = None
    logo: str | None = None
    scopes: str | None = None
    # True when the provider has no dynamic client registration: an admin must register an OAuth app with it
    # and put its client id and secret in OAUTH_CLIENTS under this provider's id.
    requires_client: bool = False


class OAuthProviderCatalog:
    """Read-only lookup over the provider catalog."""

    def __init__(self, providers: list[OAuthProvider]) -> None:
        ids = [provider.id for provider in providers]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate provider id in the OAuth provider catalog")
        self._providers = {provider.id: provider for provider in providers}

    def list(self) -> list[OAuthProvider]:
        """All providers, in catalog order."""
        return list(self._providers.values())

    def get(self, provider_id: str) -> OAuthProvider | None:
        """The provider with this id, or None."""
        return self._providers.get(provider_id)

    @classmethod
    def from_file(cls, path: Path = CATALOG_PATH) -> "OAuthProviderCatalog":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls([OAuthProvider.model_validate(item) for item in data["providers"]])


@lru_cache
def get_provider_catalog() -> OAuthProviderCatalog:
    """The catalog shipped with the app, loaded once."""
    return OAuthProviderCatalog.from_file()
