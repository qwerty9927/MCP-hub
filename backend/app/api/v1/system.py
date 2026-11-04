"""System health, readiness, and metrics endpoints."""

import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_connection_manager,
    get_execution_repository,
    get_server_repository,
)
from app.core.config import get_settings
from app.infrastructure.repositories.execution_repo import ExecutionRepositoryAbstract
from app.infrastructure.repositories.server_repo import ServerRepositoryAbstract
from app.schemas.server import ServerHealthStatus
from app.schemas.system import HealthResponse, MetricsResponse, ReadyResponse
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
    server_repo: Annotated[ServerRepositoryAbstract, Depends(get_server_repository)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
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
    server_repo: Annotated[ServerRepositoryAbstract, Depends(get_server_repository)],
    exec_repo: Annotated[ExecutionRepositoryAbstract, Depends(get_execution_repository)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
) -> MetricsResponse:
    """Telemetry metrics including active sessions, server health counts, and execution totals."""
    servers, total_servers = await server_repo.list(page=1, page_size=1000)
    healthy_servers = sum(1 for s in servers if s.health_status == ServerHealthStatus.HEALTHY)
    _, total_executions = await exec_repo.list(page=1, page_size=1)
    uptime_seconds = round(time.perf_counter() - START_TIME, 2)

    return MetricsResponse(
        active_sessions=connection_mgr.get_active_session_count(),
        total_servers=total_servers,
        healthy_servers=healthy_servers,
        total_executions=total_executions,
        uptime_seconds=uptime_seconds,
    )
