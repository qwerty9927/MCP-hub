"""Unit tests for MCPServer and MCPProxyASGI."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from mcp.server.context import ServerRequestContext
from mcp.types import (
    CallToolRequestParams,
    PaginatedRequestParams,
)

from app.core.constants.meta_tools import (
    MULTI_EXECUTE_TOOLS_NAME,
    SEARCH_TOOLS_NAME,
)
from app.core.enums.execution_enum import ExecutionOutcomeKind
from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.core.exceptions import UnauthorizedError
from app.domain.principal_entity import Principal
from app.domain.session_entity import SessionEntity
from app.mcp.mcp_proxy_asgi import MCPProxyASGI, authenticated_user
from app.mcp.mcp_server import MCPServer
from app.mcp.multi_execute_tools import MULTI_EXECUTE_TOOLS_SCHEMA
from app.mcp.search_tools import SEARCH_TOOLS_SCHEMA
from app.schemas.common_schema import PaginatedResponse
from app.schemas.server_schema import ServerResponse
from app.schemas.tool_schema import ToolResponse
from app.services.session_tracker import SessionTrackerService
from app.services.tool_executor import ExecutionOutcome


@pytest.fixture
def mock_registry():
    return AsyncMock()


@pytest.fixture
def mock_tool_catalog():
    return AsyncMock()


@pytest.fixture
def mock_connection_mgr():
    return AsyncMock()


@pytest.fixture
def mock_tool_executor():
    return AsyncMock()


@pytest.fixture
def mock_session_repo():
    return AsyncMock()


@pytest.fixture
def mock_auth_service():
    return AsyncMock()


@pytest.fixture
def mcp_server(mock_registry, mock_tool_catalog, mock_connection_mgr, mock_tool_executor, mock_session_repo, mock_auth_service):
    return MCPServer(
        server_registry=mock_registry,
        tool_catalog=mock_tool_catalog,
        connection_manager=mock_connection_mgr,
        tool_executor=mock_tool_executor,
        session_tracker=SessionTrackerService(mock_session_repo),
        auth_service=mock_auth_service,
    )


PRINCIPAL = Principal(user_id=uuid4(), api_key_id=uuid4())


def _create_mock_context(
    session_id: str | None = "test-session-123",
    request_headers: dict[str, str] | None = None,
    client_info_name: str | None = None,
    client_info_version: str | None = None,
    principal: Principal | None = PRINCIPAL,
) -> ServerRequestContext:
    """Helper to create a typed ServerRequestContext for testing."""
    mock_session = MagicMock()
    mock_conn = MagicMock()
    mock_conn.session_id = session_id
    mock_conn.protocol_version = "2024-11-05"
    mock_session._connection = mock_conn

    if client_info_name:
        mock_client_params = MagicMock()
        mock_client_info = MagicMock()
        mock_client_info.name = client_info_name
        mock_client_info.version = client_info_version or "1.0.0"
        mock_client_params.client_info = mock_client_info
        mock_session.client_params = mock_client_params
    else:
        mock_session.client_params = None

    mock_session.protocol_version = "2024-11-05"

    ctx = MagicMock(spec=ServerRequestContext)
    ctx.session = mock_session
    ctx.protocol_version = "2024-11-05"
    if request_headers is not None or principal is not None:
        mock_req = MagicMock()
        mock_req.headers = request_headers or {}
        mock_req.scope = {"user": authenticated_user(principal, "mhk_test")} if principal else {}
        ctx.request = mock_req
    else:
        ctx.request = None
    return ctx


def test_discover_session_id_from_headers(mcp_server):
    """Verify session ID is discovered from HTTP request headers."""
    ctx = _create_mock_context(session_id="fallback-conn-id", request_headers={"mcp-session-id": "header-session-456"})
    discovered = mcp_server._discover_session_id(ctx)
    assert discovered == "header-session-456"


def test_discover_session_id_from_connection(mcp_server):
    """Verify session ID falls back to connection session_id when request headers are absent."""
    ctx = _create_mock_context(session_id="fallback-conn-id", request_headers=None, principal=None)
    discovered = mcp_server._discover_session_id(ctx)
    assert discovered == "fallback-conn-id"


def test_discover_session_id_none(mcp_server):
    """Verify None is returned when neither header nor connection provides session_id."""
    ctx = _create_mock_context(session_id=None, request_headers=None, principal=None)
    discovered = mcp_server._discover_session_id(ctx)
    assert discovered is None


@pytest.mark.asyncio
async def test_transport_session_is_registered_to_the_caller(mcp_server, mock_session_repo):
    """A handshake-era session is registered with the caller as owner and the client's metadata."""
    ctx = _create_mock_context(session_id="sess-registered", client_info_name="TestClient", client_info_version="2.1.0")

    await mcp_server.handle_list_tools(ctx, params=PaginatedRequestParams())

    mock_session_repo.get_or_create.assert_awaited_once_with(
        session_id="sess-registered",
        owner_id=PRINCIPAL.user_id,
        api_key_id=PRINCIPAL.api_key_id,
        title="TestClient (sess-reg)",
        metadata={
            "session_source": "transport",
            "client_name": "TestClient",
            "client_version": "2.1.0",
            "protocol_version": "2024-11-05",
        },
    )


@pytest.mark.asyncio
async def test_handle_list_tools_returns_strictly_two_tools(mcp_server):
    """Verify handle_list_tools returns only Search and Multi-Execute without downstream tools."""
    ctx = _create_mock_context("sess-abc")

    result = await mcp_server.handle_list_tools(ctx, params=PaginatedRequestParams())
    tool_names = [t.name for t in result.tools]

    assert len(tool_names) == 2
    assert SEARCH_TOOLS_NAME in tool_names
    assert MULTI_EXECUTE_TOOLS_NAME in tool_names


@pytest.mark.asyncio
async def test_call_without_principal_is_refused(mcp_server, mock_tool_executor):
    ctx = _create_mock_context("sess-anon", principal=None)
    params = CallToolRequestParams(name=MULTI_EXECUTE_TOOLS_NAME, arguments={"executions": [{"tool_slug": "a__b", "arguments": {}}]})

    res = await mcp_server.handle_call_tool(ctx, params)

    assert res.is_error is True
    assert "Authentication required" in res.content[0].text
    mock_tool_executor.execute.assert_not_awaited()


def test_get_tool_input_schema(mcp_server):
    assert mcp_server.get_tool_input_schema(SEARCH_TOOLS_NAME) == SEARCH_TOOLS_SCHEMA
    assert mcp_server.get_tool_input_schema("Search") == SEARCH_TOOLS_SCHEMA
    assert mcp_server.get_tool_input_schema(MULTI_EXECUTE_TOOLS_NAME) == MULTI_EXECUTE_TOOLS_SCHEMA
    assert mcp_server.get_tool_input_schema("Multi-Execute") == MULTI_EXECUTE_TOOLS_SCHEMA
    assert mcp_server.get_tool_input_schema("unknown_tool") is None


@pytest.mark.asyncio
async def test_handle_call_tool_unsupported_tool(mcp_server):
    """Calling any tool other than Search or Multi-Execute directly is rejected."""
    ctx = _create_mock_context("sess-xyz")
    params = CallToolRequestParams(name="math__calculate", arguments={"expr": "1+1"})

    res = await mcp_server.handle_call_tool(ctx, params)
    assert res.is_error is True
    assert "Unsupported tool" in res.content[0].text
    assert SEARCH_TOOLS_NAME in res.content[0].text


@pytest.mark.asyncio
async def test_handle_call_tool_search(mcp_server, mock_registry, mock_tool_catalog):
    """Verify Search tool query resolves candidates from mcp_servers and discovered_tools."""
    srv_id = uuid4()
    ctx = _create_mock_context("sess-search")

    # Mock enabled servers in mcp_servers table
    mock_registry.list_servers.return_value = PaginatedResponse[ServerResponse](
        items=[
            ServerResponse(
                id=srv_id,
                name="math_server",
                transport=TransportType.STDIO,
                connection_config={"command": "python"},
                enabled=True,
                health_status=ServerHealthStatus.HEALTHY,
                created_at=MagicMock(),
                updated_at=MagicMock(),
            )
        ],
        total=1,
        page=1,
        page_size=1000,
        total_pages=1,
    )

    # Mock discovered tools in discovered_tools table
    mock_tool_catalog.list_tools.return_value = PaginatedResponse[ToolResponse](
        items=[
            ToolResponse(
                id=f"{srv_id}:calculate",
                name="calculate",
                description="Evaluate math expressions",
                input_schema={
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                },
                server_id=srv_id,
                server_name="math_server",
                availability_status="AVAILABLE",
                last_discovered_at=MagicMock(),
            )
        ],
        total=1,
        page=1,
        page_size=1000,
        total_pages=1,
    )

    params = CallToolRequestParams(
        name=SEARCH_TOOLS_NAME,
        arguments={"queries": ["math calculate"]},
    )

    res = await mcp_server.handle_call_tool(ctx, params)
    assert res.is_error is False
    data = json.loads(res.content[0].text)
    assert data["matched_count"] == 1
    assert data["tools"][0]["tool_slug"] == "math_server__calculate"
    assert data["tools"][0]["server_id"] == str(srv_id)
    assert mock_registry.list_servers.await_args.kwargs["owner_id"] == PRINCIPAL.user_id
    assert mock_tool_catalog.list_tools.await_args.kwargs["owner_id"] == PRINCIPAL.user_id


@pytest.mark.asyncio
async def test_handle_call_tool_multi_execute(mcp_server, mock_tool_executor, mock_session_repo):
    """Verify Multi-Execute dispatches each item to the Execution module with the discovered session."""
    srv_id = uuid4()
    ctx = _create_mock_context("sess-multi")
    mock_session_repo.get_or_create.return_value = SessionEntity(id="sess-multi", owner_id=PRINCIPAL.user_id)
    slug = f"{srv_id}:add"
    mock_tool_executor.execute.return_value = ExecutionOutcome(
        kind=ExecutionOutcomeKind.SUCCEEDED,
        tool_reference=slug,
        executed_at=datetime.now(UTC),
        execution_id=uuid4(),
        content=[{"type": "text", "text": "42"}],
    )

    params = CallToolRequestParams(
        name=MULTI_EXECUTE_TOOLS_NAME,
        arguments={"executions": [{"tool_slug": slug, "arguments": {"a": 20, "b": 22}}]},
    )

    res = await mcp_server.handle_call_tool(ctx, params)
    assert res.is_error is False
    data = json.loads(res.content[0].text)
    assert data["results"] == [{"tool_slug": slug, "status": "success", "data": "42", "error": None}]
    mock_tool_executor.execute.assert_awaited_once_with(slug, {"a": 20, "b": 22}, owner_id=PRINCIPAL.user_id, session_id="sess-multi")


@pytest.mark.asyncio
async def test_mcp_proxy_asgi_authenticates_api_key_and_forwards(mcp_server, mock_auth_service):
    """Verify MCPProxyASGI authenticates the x-api-key header, attaches the caller, and forwards the request."""
    mock_auth_service.authenticate_api_key.return_value = PRINCIPAL
    proxy = MCPProxyASGI(mcp_server)
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"mcp-session-id", b"session-123"), (b"x-api-key", b"mhk_valid")],
    }
    receive = AsyncMock()
    send = AsyncMock()
    mcp_server.session_manager.asgi_app = AsyncMock()

    await proxy(scope, receive, send)

    mock_auth_service.authenticate_api_key.assert_awaited_once_with("mhk_valid")
    mcp_server.session_manager.asgi_app.assert_called_once_with(scope, receive, send)
    assert scope["user"].access_token.subject == str(PRINCIPAL.user_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [
        [],
        [(b"x-api-key", b"mhk_revoked")],
        [(b"authorization", b"Bearer mhk_valid")],
        [(b"x-api-key", b"not-an-api-key")],
    ],
    ids=["no-credentials", "revoked-key", "bearer-header-not-accepted", "not-an-api-key"],
)
async def test_mcp_proxy_asgi_rejects_unauthenticated(mcp_server, mock_auth_service, headers):
    mock_auth_service.authenticate_api_key.return_value = None
    proxy = MCPProxyASGI(mcp_server)
    scope = {"type": "http", "method": "POST", "headers": headers}
    mcp_server.session_manager.asgi_app = AsyncMock()

    with pytest.raises(UnauthorizedError):
        await proxy(scope, AsyncMock(), AsyncMock())

    mcp_server.session_manager.asgi_app.assert_not_called()
