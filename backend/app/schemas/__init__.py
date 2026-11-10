"""Pydantic request and response schemas for MCP Hub Backend."""

from app.schemas.common_schema import ErrorDetail, ErrorResponse, PaginatedResponse
from app.schemas.connection_schema import (
    ConnectionConfigRead,
    ConnectionConfigResponse,
    HttpConfig,
    StdioConfig,
)
from app.schemas.execution_schema import ExecutionRead, ExecutionResponse
from app.schemas.server_schema import (
    ServerBase,
    ServerCreate,
    ServerCreateRequest,
    ServerResponse,
    ServerTestResponse,
    ServerUpdate,
    ServerUpdateRequest,
)
from app.schemas.session_schema import (
    SessionCreate,
    SessionCreateRequest,
    SessionDetailResponse,
    SessionRead,
    SessionResponse,
    ToolCallResponse,
)
from app.schemas.system_schema import HealthResponse, MetricsResponse, ReadyResponse
from app.schemas.tool_schema import (
    ToolContentItem,
    ToolExecuteRequest,
    ToolExecuteResponse,
    ToolRead,
    ToolResponse,
    ToolSummaryRead,
    ToolSummaryResponse,
)

__all__ = [
    "ConnectionConfigRead",
    "ConnectionConfigResponse",
    "ErrorDetail",
    "ErrorResponse",
    "ExecutionRead",
    "ExecutionResponse",
    "HealthResponse",
    "HttpConfig",
    "MetricsResponse",
    "PaginatedResponse",
    "ReadyResponse",
    "ServerBase",
    "ServerCreate",
    "ServerCreateRequest",
    "ServerResponse",
    "ServerTestResponse",
    "ServerUpdate",
    "ServerUpdateRequest",
    "SessionCreate",
    "SessionCreateRequest",
    "SessionDetailResponse",
    "SessionRead",
    "SessionResponse",
    "StdioConfig",
    "ToolCallResponse",
    "ToolContentItem",
    "ToolExecuteRequest",
    "ToolExecuteResponse",
    "ToolRead",
    "ToolResponse",
    "ToolSummaryRead",
    "ToolSummaryResponse",
]
