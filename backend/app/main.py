"""Main FastAPI application entry point for MCP Hub Backend."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Route

from app.api.dependencies import get_connection_manager, get_mcp_gateway, get_tool_catalog
from app.api.v1.executions import router as executions_router
from app.api.v1.servers import router as servers_router
from app.api.v1.system import router as system_router
from app.api.v1.tools import router as tools_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_correlation_id, logger, setup_logging
from app.infrastructure.database import init_db
from app.middlewares.correlation import CorrelationAndLoggingMiddleware
from app.schemas.common import ErrorDetail, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown hooks."""
    setup_logging()
    settings = get_settings()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")

    # Initialize SQLite database schema
    await init_db()

    # Preload discovered tools into catalog cache
    tool_catalog = get_tool_catalog()
    await tool_catalog.initialize_cache()

    # Start MCP Gateway Streamable HTTP lifecycle
    mcp_gateway = get_mcp_gateway()
    async with mcp_gateway.run():
        yield

    logger.info("Initiating graceful shutdown...")
    connection_manager = get_connection_manager()
    await connection_manager.shutdown()
    logger.info("Graceful shutdown complete.")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Production-oriented MCP Hub Backend that centrally manages multiple "
            "Model Context Protocol (MCP) servers and exposes their tools through a unified REST API."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "x-correlation-id"],
    )

    # Pure ASGI middleware for correlation IDs (outermost layer to trace all incoming requests)
    app.add_middleware(CorrelationAndLoggingMiddleware)

    # Custom Exception Handlers
    @app.exception_handler(AppError)
    async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
        corr_id = get_correlation_id()
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=str(exc.status_code),
                message=exc.message,
                details=exc.details,
                correlation_id=corr_id,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": corr_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        corr_id = get_correlation_id()
        errors = [
            {
                "loc": list(err.get("loc", [])),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        error_response = ErrorResponse(
            error=ErrorDetail(
                code="ValidationError",
                message="Request validation failed",
                details=errors,
                correlation_id=corr_id,
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": corr_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        corr_id = get_correlation_id()
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                correlation_id=corr_id,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": corr_id},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        corr_id = get_correlation_id()
        logger.error(f"Unhandled server error: {exc}", exc_info=True)
        error_response = ErrorResponse(
            error=ErrorDetail(
                code="InternalServerError",
                message="An unexpected internal error occurred. Please try again later.",
                details={"correlation_id": corr_id},
                correlation_id=corr_id,
            )
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": corr_id},
        )

    # Mount System probes at Root (/health, /ready, /metrics)
    app.include_router(system_router)

    # Mount API v1 routes
    from fastapi import APIRouter

    v1_router = APIRouter(prefix=settings.API_V1_STR)
    v1_router.include_router(servers_router)
    v1_router.include_router(tools_router)
    v1_router.include_router(executions_router)
    v1_router.include_router(system_router, prefix="/system")

    app.include_router(v1_router)

    # Mount unified Streamable HTTP MCP Gateway endpoint at /mcp
    mcp_gateway = get_mcp_gateway()
    app.routes.append(
        Route(
            "/mcp",
            endpoint=mcp_gateway.get_proxy_asgi_app(),
            name="mcp_gateway",
            include_in_schema=False,
        )
    )

    return app


app = create_app()
