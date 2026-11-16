"""System health, readiness, and metrics endpoints."""

import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_connection_manager,
    get_current_principal,
    get_execution_repository,
    get_server_repository,
)
from app.core.config import get_settings
from app.core.enums.server_enum import ServerHealthStatus
from app.domain.principal_entity import Principal
from app.infrastructure.repositories.execution_repository import ExecutionRepositoryAbstract
from app.infrastructure.repositories.server_repository import ServerRepositoryAbstract
from app.schemas.system_schema import HealthResponse, MetricsResponse, ReadyResponse
from app.services.connection_manager import ConnectionManager

router = APIRouter(tags=["System"])

START_TIME = time.perf_counter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
)
async def health() -> HealthResponse:
    """Liveness probe to check if application is responding."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
)
async def readiness(
    server_repository: Annotated[ServerRepositoryAbstract, Depends(get_server_repository)],
    connection_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
) -> ReadyResponse:
    """Readiness probe checking operational dependencies."""
    checks = {
        "repository": True,
        "connection_manager": True,
    }
    return ReadyResponse(
        status="ready",
        checks=checks,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Application metrics",
)
async def metrics(
    principal: Annotated[Principal, Depends(get_current_principal)],
    server_repository: Annotated[ServerRepositoryAbstract, Depends(get_server_repository)],
    execution_repository: Annotated[ExecutionRepositoryAbstract, Depends(get_execution_repository)],
    connection_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
) -> MetricsResponse:
    """Telemetry metrics including active sessions, server health counts, and execution totals."""
    servers, total_servers = await server_repository.list(page=1, page_size=1000, user_id=principal.user_id)
    healthy_servers = sum(1 for server in servers if server.health_status == ServerHealthStatus.HEALTHY)
    _, total_executions = await execution_repository.list(page=1, page_size=1, user_id=principal.user_id)
    uptime_seconds = round(time.perf_counter() - START_TIME, 2)

    return MetricsResponse(
        active_sessions=connection_manager.get_active_session_count(user_id=principal.user_id),
        total_servers=total_servers,
        healthy_servers=healthy_servers,
        total_executions=total_executions,
        uptime_seconds=uptime_seconds,
    )
