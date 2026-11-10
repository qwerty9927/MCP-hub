"""System health, readiness, and metrics schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str = Field(default="ok")
    version: str
    timestamp: datetime


class ReadyResponse(BaseModel):
    """Readiness probe response."""

    status: str = Field(default="ready")
    checks: dict[str, bool] = Field(default_factory=dict)
    timestamp: datetime


class MetricsResponse(BaseModel):
    """Basic system telemetry and operational metrics."""

    active_sessions: int
    total_servers: int
    healthy_servers: int
    total_executions: int
    uptime_seconds: float
