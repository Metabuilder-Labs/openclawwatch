"""Integration tests for the REST API using httpx.AsyncClient + ASGITransport."""
from __future__ import annotations

import pytest
import httpx

from ocw.api.app import create_app
from ocw.core.config import (
    AlertsConfig,
    ApiAuthConfig,
    ApiConfig,
    OcwConfig,
    SecurityConfig,
)
from ocw.core.db import InMemoryBackend
from ocw.core.ingest import IngestPipeline
from tests.factories import make_llm_span, make_tool_span


INGEST_SECRET = "test-secret-token"


@pytest.fixture
def db():
    backend = InMemoryBackend()
    yield backend
    backend.close()


@pytest.fixture
def config():
    return OcwConfig(
        version="1",
        security=SecurityConfig(ingest_secret=INGEST_SECRET),
        api=ApiConfig(auth=ApiAuthConfig(enabled=False)),
    )


@pytest.fixture
def config_with_api_auth():
    return OcwConfig(
        version="1",
        security=SecurityConfig(ingest_secret=INGEST_SECRET),
        api=ApiConfig(auth=ApiAuthConfig(enabled=True, api_key="my-api-key")),
    )


@pytest.fixture
def app(config, db):
    pipeline = IngestPipeline(db=db, config=config)
    return create_app(config=config, db=db, ingest_pipeline=pipeline)


@pytest.fixture
def app_with_auth(config_with_api_auth, db):
    pipeline = IngestPipeline(db=db, config=config_with_api_auth)
    return create_app(config=config_with_api_auth, db=db, ingest_pipeline=pipeline)


@pytest.fixture
def client(app):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def auth_client(app_with_auth):
    transport = httpx.ASGITransport(app=app_with_auth)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _otlp_body(spans: list[dict] | None = None) -> dict:
    """Build a minimal OTLP JSON body."""
    if spans is None:
        spans = [_make_otlp_span()]
    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "gen_ai.agent.id", "value": {"stringValue": "test-agent"}},
                    {"key": "gen_ai.provider.name", "value": {"stringValue": "anthropic"}},
                ],
            },
            "scopeSpans": [{"spans": spans}],
        }],
    }


def _make_otlp_span(
    span_id: str = "abc123def456",
    trace_id: str = "aabbccdd" * 4,
    name: str = "gen_ai.llm.call",
    status_code: int = 1,
    **extra_attrs: str,
) -> dict:
    """Build a single OTLP span dict."""
    attrs = [
        {"key": "gen_ai.request.model", "value": {"stringValue": "claude-haiku-4-5"}},
        {"key": "gen_ai.usage.input_tokens", "value": {"intValue": "500"}},
        {"key": "gen_ai.usage.output_tokens", "value": {"intValue": "100"}},
    ]
    for k, v in extra_attrs.items():
        attrs.append({"key": k, "value": {"stringValue": v}})
    return {
        "traceId": trace_id,
        "spanId": span_id,
        "name": name,
        "kind": 3,  # CLIENT
        "startTimeUnixNano": "1711600000000000000",
        "endTimeUnixNano": "1711600001000000000",
        "status": {"code": status_code},
        "attributes": attrs,
    }


# ── Ingest auth ────────────────────────────────────────────────────────────

async def test_post_spans_without_auth_returns_401(client):
    resp = await client.post("/api/v1/spans", json=_otlp_body())
    assert resp.status_code == 401


async def test_post_spans_with_wrong_secret_returns_401(client):
    resp = await client.post(
        "/api/v1/spans",
        json=_otlp_body(),
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


async def test_post_spans_with_correct_auth_ingests_spans(client):
    resp = await client.post(
        "/api/v1/spans",
        json=_otlp_body(),
        headers={"Authorization": f"Bearer {INGEST_SECRET}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingested"] == 1
    assert data["rejected"] == 0


async def test_post_spans_invalid_json_returns_400(client):
    resp = await client.post(
        "/api/v1/spans",
        content=b"not json",
        headers={
            "Authorization": f"Bearer {INGEST_SECRET}",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 400


async def test_post_spans_missing_resource_spans_returns_400(client):
    resp = await client.post(
        "/api/v1/spans",
        json={"wrong_key": []},
        headers={"Authorization": f"Bearer {INGEST_SECRET}"},
    )
    assert resp.status_code == 400


async def test_post_spans_partial_rejection_returns_200(client, db, config):
    """Batch of 2 spans where 1 has oversized attributes — should partially succeed."""
    good_span = _make_otlp_span(span_id="good11111111")
    # Create a span with an attribute exceeding the default max_attribute_bytes (65536)
    big_value = "x" * 70000
    bad_span = _make_otlp_span(span_id="bad111111111")
    bad_span["attributes"].append(
        {"key": "huge_attr", "value": {"stringValue": big_value}}
    )
    body = _otlp_body(spans=[good_span, bad_span])
    resp = await client.post(
        "/api/v1/spans",
        json=body,
        headers={"Authorization": f"Bearer {INGEST_SECRET}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingested"] == 1
    assert data["rejected"] == 1
    assert len(data["rejections"]) == 1


# ── GET endpoints ──────────────────────────────────────────────────────────

async def _ingest_sample_span(client):
    """Helper: ingest one span so GET endpoints have data."""
    resp = await client.post(
        "/api/v1/spans",
        json=_otlp_body(),
        headers={"Authorization": f"Bearer {INGEST_SECRET}"},
    )
    assert resp.status_code == 200


async def test_get_traces_returns_list(client):
    await _ingest_sample_span(client)
    resp = await client.get("/api/v1/traces")
    assert resp.status_code == 200
    data = resp.json()
    assert "traces" in data
    assert len(data["traces"]) >= 1


async def test_get_traces_filter_by_agent_id(client):
    await _ingest_sample_span(client)
    resp = await client.get("/api/v1/traces", params={"agent_id": "test-agent"})
    assert resp.status_code == 200
    data = resp.json()
    for t in data["traces"]:
        assert t["agent_id"] == "test-agent"


async def test_get_trace_by_id_returns_span_waterfall(client):
    await _ingest_sample_span(client)
    trace_id = "aabbccdd" * 4
    resp = await client.get(f"/api/v1/traces/{trace_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace_id"] == trace_id
    assert "spans" in data
    assert len(data["spans"]) >= 1


async def test_get_cost_returns_aggregated_rows(client):
    await _ingest_sample_span(client)
    resp = await client.get("/api/v1/cost")
    assert resp.status_code == 200
    data = resp.json()
    assert "rows" in data
    assert "total_cost_usd" in data


async def test_get_alerts_returns_list(client):
    resp = await client.get("/api/v1/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert isinstance(data["alerts"], list)


async def test_get_tools_returns_list(client):
    resp = await client.get("/api/v1/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data


async def test_get_metrics_returns_prometheus_format(client):
    await _ingest_sample_span(client)
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "ocw_cost_usd_total" in text
    assert "# HELP" in text
    assert "# TYPE" in text


async def test_get_drift_requires_agent_id(client):
    resp = await client.get("/api/v1/drift")
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data


# ── API key auth ───────────────────────────────────────────────────────────

async def test_get_endpoint_requires_api_key_when_auth_enabled(auth_client):
    resp = await auth_client.get("/api/v1/traces")
    assert resp.status_code in (401, 403)


async def test_get_endpoint_works_with_valid_api_key(auth_client):
    resp = await auth_client.get(
        "/api/v1/traces",
        headers={"Authorization": "Bearer my-api-key"},
    )
    assert resp.status_code == 200


# ── Docs endpoint ──────────────────────────────────────────────────────────

async def test_docs_endpoint_is_accessible(client):
    resp = await client.get("/docs")
    assert resp.status_code == 200
