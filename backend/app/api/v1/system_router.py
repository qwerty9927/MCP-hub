"""System health, readiness, and metrics endpoints."""

import asyncio
import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text

from app.api.dependencies import (
    get_connection_manager,
    get_current_principal,
    get_database,
    get_execution_repository,
    get_server_repository,
)
from app.core.config import get_settings
from app.core.enums.server_enum import ServerHealthStatus
from app.core.logging import logger
from app.domain.principal_entity import Principal
from app.infrastructure.database import Database
from app.infrastructure.repositories.execution_repository import ExecutionRepositoryAbstract
from app.infrastructure.repositories.server_repository import ServerRepositoryAbstract
from app.schemas.system_schema import HealthResponse, MetricsResponse, ReadyResponse
from app.services.connection_manager import ConnectionManager

router = APIRouter(tags=["System"])

START_TIME = time.perf_counter()

# /ready gives up on the database after this long: a probe must answer quickly even when the database hangs.
READY_DATABASE_TIMEOUT_SECONDS = 2.0


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
    responses={503: {"model": ReadyResponse, "description": "A dependency (the database) is unreachable"}},
)
async def readiness(response: Response, database: Annotated[Database, Depends(get_database)]) -> ReadyResponse:
    """Readiness probe: 200 when the database answers, 503 (`not_ready`) when it does not."""
    checks = {"database": await _database_is_reachable(database)}
    ready = all(checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status="ready" if ready else "not_ready",
        checks=checks,
        timestamp=datetime.now(UTC),
    )


async def _database_is_reachable(database: Database) -> bool:
    try:
        async with asyncio.timeout(READY_DATABASE_TIMEOUT_SECONDS):
            async with database.session() as session:
                await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning(f"Readiness check: database unreachable: {type(exc).__name__}: {exc}")
        return False
    return True


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
    total_servers = await server_repository.count(user_id=principal.user_id)
    healthy_servers = await server_repository.count(user_id=principal.user_id, health_status=ServerHealthStatus.HEALTHY)
    _, total_executions = await execution_repository.list(page=1, page_size=1, user_id=principal.user_id)
    uptime_seconds = round(time.perf_counter() - START_TIME, 2)

    return MetricsResponse(
        active_sessions=connection_manager.get_active_session_count(user_id=principal.user_id),
        total_servers=total_servers,
        healthy_servers=healthy_servers,
        total_executions=total_executions,
        uptime_seconds=uptime_seconds,
    )
