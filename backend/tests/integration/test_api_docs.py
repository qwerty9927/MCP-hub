"""Swagger UI, ReDoc and the OpenAPI schema are served everywhere but production."""

import pytest
from httpx import ASGITransport, AsyncClient

import app.main as main_module
from app.core.config import get_settings

DOCS_PATHS = ["/docs", "/redoc", "/openapi.json"]


async def get_status(environment: str, path: str, monkeypatch: pytest.MonkeyPatch) -> int:
    settings = get_settings().model_copy(update={"ENVIRONMENT": environment})
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    application = main_module.create_app()
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://testserver") as client:
        return (await client.get(path)).status_code


@pytest.mark.parametrize("path", DOCS_PATHS)
@pytest.mark.parametrize("environment", ["development", "test"])
async def test_docs_are_served_outside_production(environment, path, monkeypatch):
    assert await get_status(environment, path, monkeypatch) == 200


@pytest.mark.parametrize("path", DOCS_PATHS)
async def test_docs_are_hidden_in_production(path, monkeypatch):
    assert await get_status("production", path, monkeypatch) == 404


async def test_the_api_still_answers_in_production(monkeypatch):
    assert await get_status("production", "/health", monkeypatch) == 200
