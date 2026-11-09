"""Security integration tests verifying defense-in-depth protections."""

from httpx import AsyncClient


async def test_disallowed_executable_rejected(async_client: AsyncClient):
    """Registering a server with an unapproved executable must be rejected."""
    payload = {
        "name": "malicious-server",
        "transport": "stdio",
        "stdio_config": {
            "command": "rm",
            "args": ["-rf", "/"],
        },
    }
    response = await async_client.post("/api/v1/servers", json=payload)
    assert response.status_code == 403
    data = response.json()
    assert "error" in data
    assert "disallowed" in data["error"]["message"].lower() or "not in the approved" in data["error"]["message"].lower()


async def test_command_injection_attempt_rejected(async_client: AsyncClient):
    """Commands with shell metacharacters must be rejected."""
    payload = {
        "name": "injection-server",
        "transport": "stdio",
        "stdio_config": {
            "command": "python; cat /etc/passwd",
            "args": [],
        },
    }
    response = await async_client.post("/api/v1/servers", json=payload)
    assert response.status_code == 403
    data = response.json()
    assert "error" in data


async def test_ssrf_forbidden_schemes(async_client: AsyncClient):
    """Remote URL with file scheme must be rejected."""
    payload = {
        "name": "file-scheme-server",
        "transport": "streamable-http",
        "http_config": {
            "url": "file:///etc/passwd",
        },
    }
    response = await async_client.post("/api/v1/servers", json=payload)
    assert response.status_code == 403
    data = response.json()
    assert "error" in data


async def test_masked_headers_in_response(async_client: AsyncClient):
    """Sensitive headers in HTTP config must never be returned in plaintext."""
    payload = {
        "name": "auth-http-server",
        "transport": "streamable-http",
        "http_config": {
            "url": "http://127.0.0.1:8999/mcp",
            "headers": {
                "Authorization": "Bearer confidential_token_xyz",
                "X-Api-Key": "my-private-api-key",
                "Custom-Header": "public-val",
            },
        },
    }
    create_res = await async_client.post("/api/v1/servers", json=payload)
    assert create_res.status_code == 201
    server_data = create_res.json()

    headers = server_data["connection_config"]["headers"]
    assert headers["Authorization"] == "********"
    assert headers["X-Api-Key"] == "********"
    assert headers["Custom-Header"] == "public-val"
    assert "confidential_token_xyz" not in create_res.text
