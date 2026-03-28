"""FastAPI application factory. Called by `ocw serve`."""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ocw.api.middleware import IngestAuthMiddleware
from ocw.core.config import OcwConfig

if TYPE_CHECKING:
    from ocw.core.db import StorageBackend
    from ocw.core.ingest import IngestPipeline


def create_app(
    config: OcwConfig,
    db: StorageBackend,
    ingest_pipeline: IngestPipeline,
) -> FastAPI:
    """
    Build and return the FastAPI app.

    db and ingest_pipeline are passed in (not imported globally) so tests
    can inject mocks easily.
    """
    app = FastAPI(
        title="OpenClawWatch",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    # CORS — local only by default
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Ingest auth middleware
    app.add_middleware(IngestAuthMiddleware)

    # Shared state for routes
    app.state.config = config
    app.state.db = db
    app.state.pipeline = ingest_pipeline

    # Register routers
    from ocw.api.routes.spans import router as spans_router
    from ocw.api.routes.traces import router as traces_router
    from ocw.api.routes.cost import router as cost_router
    from ocw.api.routes.tools import router as tools_router
    from ocw.api.routes.alerts import router as alerts_router
    from ocw.api.routes.drift import router as drift_router
    from ocw.api.routes.metrics import router as metrics_router

    app.include_router(spans_router, prefix="/api/v1")
    app.include_router(traces_router, prefix="/api/v1")
    app.include_router(cost_router, prefix="/api/v1")
    app.include_router(tools_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(drift_router, prefix="/api/v1")
    app.include_router(metrics_router)  # /metrics — no prefix

    return app
