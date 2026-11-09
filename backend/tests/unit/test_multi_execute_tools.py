"""Unit tests for MULTI_EXECUTE_TOOLS parallel dispatcher meta-tool."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from mcp.types import CallToolResult, TextContent

from app.core.constants.meta_tools import (
    MULTI_EXECUTE_TOOLS_NAME,
    SEARCH_TOOLS_NAME,
)
from app.core.enums.server_enum import TransportType
from app.core.exceptions import ValidationError
from app.domain.server_entity import ServerEntity
from app.domain.tool_entity import ToolEntity
from app.mcp.multi_execute_tools import (
    MULTI_EXECUTE_TOOLS_SCHEMA,
    get_multi_execute_tool_definition,
    handle_multi_execute_tools,
)


@dataclass
class MockMapping:
    hub_tool_name: str
    server_id: UUID
    server_name: str
    original_tool_name: str
    input_schema: dict[str, Any]
    description: str | None = None
    availability_status: str = "AVAILABLE"


def test_multi_execute_tool_definition_and_schema():
    tool = get_multi_execute_tool_definition()
    assert tool.name == MULTI_EXECUTE_TOOLS_NAME
    assert tool.input_schema == MULTI_EXECUTE_TOOLS_SCHEMA
    assert "executions" in tool.input_schema["required"]
    assert tool.input_schema["additionalProperties"] is False
    items_schema = tool.input_schema["properties"]["executions"]["items"]
    assert items_schema["additionalProperties"] is False
    assert items_schema["properties"]["tool_slug"]["minLength"] == 1
    assert items_schema["properties"]["arguments"]["default"] == {}
    assert "### Agent Execution Guidelines:" in tool.description
    # Ensure description is cleanly dedented via inspect.cleandoc
    assert not any(line.startswith("            ") for line in tool.description.splitlines())


@pytest.mark.asyncio
async def test_handle_multi_execute_tools_success():
    srv_id = uuid4()
    mock_router = AsyncMock()
    mock_registry = AsyncMock()

    mock_server = ServerEntity(
        id=srv_id,
        name="math",
        transport=TransportType.STDIO,
        enabled=True,
    )
    mock_registry.get_server_entity.return_value = mock_server

    mock_router.execute_mcp_tool.side_effect = [
        CallToolResult(
            content=[TextContent(type="text", text="42")],
            is_error=False,
        ),
        CallToolResult(
            content=[TextContent(type="text", text='{"status": "ok", "value": 100}')],
            is_error=False,
        ),
    ]

    tool_map = {
        "math__calc": MockMapping(
            hub_tool_name="math__calc",
            server_id=srv_id,
            server_name="math",
            original_tool_name="calc",
            input_schema={"type": "object"},
            description="Calculate",
        ),
        "math__eval": MockMapping(
            hub_tool_name="math__eval",
            server_id=srv_id,
            server_name="math",
            original_tool_name="eval",
            input_schema={"type": "object"},
            description="Evaluate",
        ),
    }

    result = await handle_multi_execute_tools(
        arguments={
            "executions": [
                {"tool_slug": "math__calc", "arguments": {"expr": "6*7"}},
                {"tool_slug": "math__eval", "arguments": {"expr": "10*10"}},
            ]
        },
        tool_map=tool_map,
        tool_router=mock_router,
        server_registry=mock_registry,
    )

    results = result["results"]
    assert len(results) == 2
    assert results[0]["tool_slug"] == "math__calc"
    assert results[0]["status"] == "success"
    assert results[0]["data"] == "42"
    assert results[0]["error"] is None

    assert results[1]["tool_slug"] == "math__eval"
    assert results[1]["status"] == "success"
    assert results[1]["data"] == {"status": "ok", "value": 100}
    assert results[1]["error"] is None


@pytest.mark.asyncio
async def test_handle_multi_execute_tools_via_tool_catalog():
    """Verify execution resolved directly from tool_catalog and discovered_tools table."""
    srv_id = uuid4()
    mock_router = AsyncMock()
    mock_registry = AsyncMock()
    mock_catalog = AsyncMock()

    mock_server = ServerEntity(
        id=srv_id,
        name="math",
        transport=TransportType.STDIO,
        enabled=True,
    )
    mock_registry.get_server_entity.return_value = mock_server

    tool_ent = ToolEntity(
        id=f"{srv_id}:add",
        server_id=srv_id,
        server_name="math",
        name="add",
        input_schema={"type": "object"},
        description="Add numbers",
    )
    mock_catalog.get_tool.return_value = tool_ent

    mock_router.execute_mcp_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text="10")],
        is_error=False,
    )

    result = await handle_multi_execute_tools(
        arguments={
            "executions": [
                {"tool_slug": f"{srv_id}:add", "arguments": {"a": 4, "b": 6}},
            ]
        },
        tool_router=mock_router,
        server_registry=mock_registry,
        tool_catalog=mock_catalog,
    )

    results = result["results"]
    assert len(results) == 1
    assert results[0]["status"] == "success"
    assert results[0]["data"] == "10"
    mock_router.execute_mcp_tool.assert_called_once_with(
        server_id=srv_id,
        tool_name="add",
        arguments={"a": 4, "b": 6},
    )


@pytest.mark.asyncio
async def test_handle_multi_execute_tools_failure_isolation():
    srv1_id = uuid4()
    srv2_id = uuid4()
    mock_router = AsyncMock()
    mock_registry = AsyncMock()

    server1 = ServerEntity(id=srv1_id, name="math", transport=TransportType.STDIO, enabled=True)
    server2_disabled = ServerEntity(id=srv2_id, name="disabled_srv", transport=TransportType.STDIO, enabled=False)

    def get_server_mock(sid):
        if sid == srv1_id:
            return server1
        return server2_disabled

    mock_registry.get_server_entity.side_effect = get_server_mock

    # Router handles call for tool1 (success), tool2 (validation error), tool3 (downstream error)
    async def execute_mcp_mock(server_id, tool_name, arguments):
        if tool_name == "calc":
            return CallToolResult(content=[TextContent(type="text", text="42")], is_error=False)
        if tool_name == "bad_args":
            raise ValidationError("Missing property 'x'")
        if tool_name == "crash":
            return CallToolResult(
                content=[TextContent(type="text", text="Internal computation failure")],
                is_error=True,
            )
        raise RuntimeError("Unexpected tool")

    mock_router.execute_mcp_tool.side_effect = execute_mcp_mock

    tool_map = {
        "math__calc": MockMapping(
            hub_tool_name="math__calc",
            server_id=srv1_id,
            server_name="math",
            original_tool_name="calc",
            input_schema={},
        ),
        "math__bad_args": MockMapping(
            hub_tool_name="math__bad_args",
            server_id=srv1_id,
            server_name="math",
            original_tool_name="bad_args",
            input_schema={},
        ),
        "math__crash": MockMapping(
            hub_tool_name="math__crash",
            server_id=srv1_id,
            server_name="math",
            original_tool_name="crash",
            input_schema={},
        ),
        "disabled__tool": MockMapping(
            hub_tool_name="disabled__tool",
            server_id=srv2_id,
            server_name="disabled_srv",
            original_tool_name="tool",
            input_schema={},
        ),
    }

    executions = [
        {"tool_slug": "math__calc", "arguments": {}},
        {"tool_slug": "non_existent_tool", "arguments": {}},
        {"tool_slug": "math__bad_args", "arguments": {}},
        {"tool_slug": "disabled__tool", "arguments": {}},
        {"tool_slug": "math__crash", "arguments": {}},
        {"tool_slug": SEARCH_TOOLS_NAME, "arguments": {"queries": ["test"]}},
    ]

    result = await handle_multi_execute_tools(
        arguments={"executions": executions},
        tool_map=tool_map,
        tool_router=mock_router,
        server_registry=mock_registry,
    )

    results = result["results"]
    assert len(results) == 6

    # 1. Success
    assert results[0]["tool_slug"] == "math__calc"
    assert results[0]["status"] == "success"
    assert results[0]["data"] == "42"

    # 2. Non-existent tool -> error
    assert results[1]["tool_slug"] == "non_existent_tool"
    assert results[1]["status"] == "error"
    assert "Unknown or unavailable" in results[1]["error"]

    # 3. Validation error -> validation_error
    assert results[2]["tool_slug"] == "math__bad_args"
    assert results[2]["status"] == "validation_error"
    assert "Missing property 'x'" in results[2]["error"]

    # 4. Disabled server -> error
    assert results[3]["tool_slug"] == "disabled__tool"
    assert results[3]["status"] == "error"
    assert "disabled" in results[3]["error"]

    # 5. Tool returned error result -> error
    assert results[4]["tool_slug"] == "math__crash"
    assert results[4]["status"] == "error"
    assert "Internal computation failure" in results[4]["error"]

    # 6. Recursive meta-tool call -> error
    assert results[5]["tool_slug"] == SEARCH_TOOLS_NAME
    assert results[5]["status"] == "error"
    assert "not permitted" in results[5]["error"]


@pytest.mark.asyncio
async def test_handle_multi_execute_tools_payload_validation():
    mock_router = AsyncMock()
    mock_registry = AsyncMock()

    # Empty executions
    with pytest.raises(ValidationError):
        await handle_multi_execute_tools(
            arguments={"executions": []},
            tool_map={},
            tool_router=mock_router,
            server_registry=mock_registry,
        )

    # Missing executions
    with pytest.raises(ValidationError):
        await handle_multi_execute_tools(
            arguments={},
            tool_map={},
            tool_router=mock_router,
            server_registry=mock_registry,
        )

    # Extra root argument (extra="forbid")
    with pytest.raises(ValidationError):
        await handle_multi_execute_tools(
            arguments={
                "executions": [{"tool_slug": "calc", "arguments": {}}],
                "extra_key": True,
            },
            tool_map={},
            tool_router=mock_router,
            server_registry=mock_registry,
        )

    # Extra item argument (extra="forbid")
    with pytest.raises(ValidationError):
        await handle_multi_execute_tools(
            arguments={"executions": [{"tool_slug": "calc", "arguments": {}, "extra_item_key": 123}]},
            tool_map={},
            tool_router=mock_router,
            server_registry=mock_registry,
        )

    # Empty tool_slug (min_length=1)
    with pytest.raises(ValidationError):
        await handle_multi_execute_tools(
            arguments={"executions": [{"tool_slug": "", "arguments": {}}]},
            tool_map={},
            tool_router=mock_router,
            server_registry=mock_registry,
        )

    # Whitespace-only tool_slug (stripped to empty)
    with pytest.raises(ValidationError):
        await handle_multi_execute_tools(
            arguments={"executions": [{"tool_slug": "   ", "arguments": {}}]},
            tool_map={},
            tool_router=mock_router,
            server_registry=mock_registry,
        )
