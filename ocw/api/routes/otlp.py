"""Standard OTLP/HTTP route aliases.

POST /v1/traces — forwards to the same OTLP JSON ingest logic as /api/v1/spans.
POST /v1/metrics — stub (200 OK, silently discards).
POST /v1/logs — stub (200 OK, silently discards).

These exist so that OTel exporters configured with a bare endpoint
(e.g. ``http://127.0.0.1:7391``) work out of the box — OpenClaw's
diagnostics-otel plugin uses this convention.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ocw.api.routes.spans import ingest_spans

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/traces")
async def otlp_traces(request: Request) -> JSONResponse:
    """Accept OTLP JSON traces — same handler as /api/v1/spans."""
    return await ingest_spans(request)


@router.post("/v1/metrics")
async def otlp_metrics(request: Request) -> JSONResponse:
    """Stub — accept and discard OTLP metrics to avoid noisy client warnings."""
    return JSONResponse(status_code=200, content={"status": "ok"})


@router.post("/v1/logs")
async def otlp_logs(request: Request) -> JSONResponse:
    """Stub — accept and discard OTLP logs to avoid noisy client warnings."""
    return JSONResponse(status_code=200, content={"status": "ok"})
