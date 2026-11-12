"""Unit tests for the MULTI_EXECUTE_TOOLS adapter over the Execution module.

The Execution module itself is covered in test_tool_executor.py; here a stub executor returns canned
Outcomes so only the adapter's job is exercised: payload validation, parallel fan-out with isolation,
meta-tool recursion guard, and mapping Outcomes to the agent-facing result shape.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.core.constants.meta_tools import MULTI_EXECUTE_TOOLS_NAME, SEARCH_TOOLS_NAME
from app.core.enums.execution_enum import ExecutionOutcomeKind, RejectionReason
from app.core.exceptions import ValidationError
from app.mcp.multi_execute_tools import (
    MULTI_EXECUTE_TOOLS_SCHEMA,
    get_multi_execute_tool_definition,
    handle_multi_execute_tools,
)
from app.services.tool_executor import ExecutionOutcome


def outcome(kind: ExecutionOutcomeKind, ref: str, **kwargs: Any) -> ExecutionOutcome:
    return ExecutionOutcome(kind=kind, tool_reference=ref, executed_at=datetime.now(UTC), execution_id=uuid4(), **kwargs)


class StubExecutor:
    def __init__(self, outcomes: dict[str, ExecutionOutcome | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []

    async def execute(self, tool_reference: str, arguments: dict[str, Any], session_id: str | None = None, timeout: float | None = None):
        self.calls.append((tool_reference, arguments, session_id))
        result = self.outcomes[tool_reference]
        if isinstance(result, Exception):
            raise result
        return result


async def run(executor: StubExecutor, *slugs: str, session_id: str | None = None) -> list[dict[str, Any]]:
    payload = {"executions": [{"tool_slug": s, "arguments": {"x": 1}} for s in slugs]}
    res = await handle_multi_execute_tools(arguments=payload, executor=executor, session_id=session_id)
    return res["results"]


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
    assert not any(line.startswith("            ") for line in tool.description.splitlines())


async def test_succeeded_single_json_text_block_is_parsed():
    executor = StubExecutor(
        {"m__a": outcome(ExecutionOutcomeKind.SUCCEEDED, "m__a", content=[{"type": "text", "text": '{"sum": 3}'}])},
    )
    [item] = await run(executor, "m__a", session_id="sess-1")

    assert item == {"tool_slug": "m__a", "status": "success", "data": {"sum": 3}, "error": None}
    assert executor.calls == [("m__a", {"x": 1}, "sess-1")]


async def test_succeeded_plain_text_and_multi_block_shapes():
    executor = StubExecutor(
        {
            "m__text": outcome(ExecutionOutcomeKind.SUCCEEDED, "m__text", content=[{"type": "text", "text": "42"}]),
            "m__multi": outcome(
                ExecutionOutcomeKind.SUCCEEDED,
                "m__multi",
                content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}],
            ),
            "m__empty": outcome(ExecutionOutcomeKind.SUCCEEDED, "m__empty"),
        }
    )
    text, multi, empty = await run(executor, "m__text", "m__multi", "m__empty")

    assert text["data"] == "42"
    assert multi["data"] == [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
    assert empty["data"] is None


async def test_outcomes_map_to_agent_statuses():
    executor = StubExecutor(
        {
            "m__bad_args": outcome(
                ExecutionOutcomeKind.REJECTED,
                "m__bad_args",
                rejection_reason=RejectionReason.INVALID_ARGUMENTS,
                error_message="'b' is a required property",
            ),
            "m__disabled": outcome(
                ExecutionOutcomeKind.REJECTED,
                "m__disabled",
                rejection_reason=RejectionReason.SERVER_DISABLED,
                error_message="Server 'm' is disabled",
            ),
            "m__tool_error": outcome(ExecutionOutcomeKind.TOOL_ERROR, "m__tool_error", error_message="boom"),
            "m__failed": outcome(ExecutionOutcomeKind.FAILED, "m__failed", error_message="timed out"),
        }
    )
    bad_args, disabled, tool_error, failed = await run(executor, "m__bad_args", "m__disabled", "m__tool_error", "m__failed")

    assert bad_args["status"] == "validation_error"
    assert bad_args["error"] == "Argument validation failed: 'b' is a required property"
    assert (disabled["status"], disabled["error"]) == ("error", "Server 'm' is disabled")
    assert (tool_error["status"], tool_error["error"]) == ("error", "boom")
    assert (failed["status"], failed["error"]) == ("error", "timed out")
    assert all(r["data"] is None for r in (bad_args, disabled, tool_error, failed))


async def test_infrastructure_fault_in_one_item_is_isolated():
    executor = StubExecutor(
        {
            "m__ok": outcome(ExecutionOutcomeKind.SUCCEEDED, "m__ok", content=[{"type": "text", "text": "fine"}]),
            "m__db_down": RuntimeError("database unavailable"),
        }
    )
    ok, broken = await run(executor, "m__ok", "m__db_down")

    assert ok["status"] == "success"
    assert broken["status"] == "error"
    assert "database unavailable" in broken["error"]


async def test_meta_tools_cannot_be_executed_recursively():
    executor = StubExecutor({})
    results = await run(executor, SEARCH_TOOLS_NAME, MULTI_EXECUTE_TOOLS_NAME, "Search")

    assert [r["status"] for r in results] == ["error", "error", "error"]
    assert all("not permitted" in r["error"] for r in results)
    assert executor.calls == []


async def test_payload_validation():
    executor = StubExecutor({})
    for bad in ({"executions": []}, {}, {"executions": [{"tool_slug": "calc", "arguments": {}}], "extra_key": True}):
        with pytest.raises(ValidationError):
            await handle_multi_execute_tools(arguments=bad, executor=executor)
