# Task 08 — REST API
**Depends on:** Task 00 (foundation), Task 01 (StorageBackend interface), Task 02 (IngestPipeline interface).
**Parallel with:** Tasks 03–07, 09–11.
**Estimated scope:** Medium.

---

## What this task covers

- `ocw/api/app.py` — FastAPI application factory
- `ocw/api/middleware.py` — ingest auth middleware
- All route modules under `ocw/api/routes/`
- Prometheus metrics endpoint

---

## Deliverables

### `ocw/api/app.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ocw.core.config import OcwConfig
from ocw.api.middleware import IngestAuthMiddleware


def create_app(config: OcwConfig, db, ingest_pipeline) -> FastAPI:
    """
    FastAPI application factory.
    Called by `ocw serve` (Task 07, cmd_serve.py).

    Registers all routers and middleware.
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

    # Store shared state on app.state so routes can access it
    app.state.config   = config
    app.state.db       = db
    app.state.pipeline = ingest_pipeline

    # Register routers
    from ocw.api.routes.spans   import router as spans_router
    from ocw.api.routes.traces  import router as traces_router
    from ocw.api.routes.cost    import router as cost_router
    from ocw.api.routes.tools   import router as tools_router
    from ocw.api.routes.alerts  import router as alerts_router
    from ocw.api.routes.drift   import router as drift_router
    from ocw.api.routes.metrics import router as metrics_router

    app.include_router(spans_router,   prefix="/api/v1")
    app.include_router(traces_router,  prefix="/api/v1")
    app.include_router(cost_router,    prefix="/api/v1")
    app.include_router(tools_router,   prefix="/api/v1")
    app.include_router(alerts_router,  prefix="/api/v1")
    app.include_router(drift_router,   prefix="/api/v1")
    app.include_router(metrics_router)   # /metrics — no prefix

    return app
```

---

### `ocw/api/middleware.py`

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class IngestAuthMiddleware(BaseHTTPMiddleware):
    """
    Validates the ingest secret on POST /api/v1/spans.
    All other endpoints use the optional API key check in each route.

    If security.ingest_secret is empty string, auth is disabled (not recommended).
    Returns 401 with JSON error if secret is wrong or missing.
    """

    PROTECTED_PATHS = {"/api/v1/spans"}

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path in self.PROTECTED_PATHS:
            secret = request.app.state.config.security.ingest_secret
            if secret:   # empty string = auth disabled
                auth = request.headers.get("Authorization", "")
                if not auth.startswith("Bearer ") or auth[7:] != secret:
                    raise HTTPException(status_code=401, detail="Invalid ingest secret")
        return await call_next(request)
```

---

### `ocw/api/routes/spans.py`

```
POST /api/v1/spans
```

Accepts a batch of spans in OTLP JSON format. Auth enforced by middleware.

Request body: `{ "resourceSpans": [...] }` (standard OTLP JSON format)

For each span in the batch:
1. Parse into `NormalizedSpan`
2. Call `request.app.state.pipeline.process(span)`
3. Catch `SpanRejectedError` and collect it (don't abort the whole batch)

Response:
```json
{
  "ingested": 5,
  "rejected": 1,
  "rejections": [{"span_id": "...", "reason": "..."}]
}
```

Status 200 even if some spans were rejected (partial success). Status 400 only if the
entire request body is malformed (not valid OTLP JSON).

---

### `ocw/api/routes/traces.py`

```
GET /api/v1/traces
GET /api/v1/traces/{trace_id}
```

`GET /api/v1/traces` — query params: `agent_id`, `since`, `until`, `limit`, `offset`,
`status`, `span_name`

`GET /api/v1/traces/{trace_id}` — returns the full span waterfall for a single trace,
with all child spans in a nested structure.

All responses: JSON. Use the `TraceFilters` dataclass for querying.

---

### `ocw/api/routes/cost.py`

```
GET /api/v1/cost
```

Query params: `agent_id`, `since`, `until`, `group_by` (agent|model|day|tool)

Returns:
```json
{
  "rows": [
    {"group": "2026-03-27", "agent_id": "my-agent", "model": "claude-haiku-4-5",
     "input_tokens": 12000, "output_tokens": 3000, "cost_usd": 0.021}
  ],
  "total_cost_usd": 0.021
}
```

---

### `ocw/api/routes/tools.py`

```
GET /api/v1/tools
```

Query params: `agent_id`, `since`, `tool_name`

Returns list of tool call records with aggregated stats.

---

### `ocw/api/routes/alerts.py`

```
GET /api/v1/alerts
```

Query params: `agent_id`, `since`, `severity`, `type`, `unread` (bool)

Returns list of `Alert` objects as JSON. Uses `AlertFilters`.

---

### `ocw/api/routes/drift.py`

```
GET /api/v1/drift
```

Query params: `agent_id`

Returns baseline data and latest session comparison for each agent.

---

### `ocw/api/routes/metrics.py`

```
GET /metrics
```

Prometheus text format. Scraped by Prometheus or Grafana Agent.

Metrics to expose:

```
# HELP ocw_cost_usd_total Running cost total per agent
# TYPE ocw_cost_usd_total gauge
ocw_cost_usd_total{agent_id="my-agent"} 0.034

# HELP ocw_spans_total Total spans ingested
# TYPE ocw_spans_total counter
ocw_spans_total{agent_id="my-agent",span_name="gen_ai.llm.call"} 142

# HELP ocw_tool_calls_total Total tool calls per agent and tool
# TYPE ocw_tool_calls_total counter
ocw_tool_calls_total{agent_id="my-agent",tool_name="send_email"} 12

# HELP ocw_alerts_total Total alerts fired
# TYPE ocw_alerts_total counter
ocw_alerts_total{agent_id="my-agent",type="sensitive_action",severity="critical"} 3

# HELP ocw_session_duration_seconds Duration of last completed session
# TYPE ocw_session_duration_seconds gauge
ocw_session_duration_seconds{agent_id="my-agent"} 263.4

# HELP ocw_tokens_total Token usage by type
# TYPE ocw_tokens_total counter
ocw_tokens_total{agent_id="my-agent",type="input"} 12000
ocw_tokens_total{agent_id="my-agent",type="output"} 3000
```

Build these by querying the DB (aggregated queries) on each `/metrics` request.
Do not use the OTel Prometheus exporter for these — generate the text format directly
from DB queries so the data is always accurate even after `ocw serve` restarts.

---

## API auth for non-ingest endpoints

If `api.auth.enabled = true` in config, all `GET` endpoints require:
```
Authorization: Bearer <api.auth.api_key>
```

Implement this as a FastAPI dependency, not middleware:

```python
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
):
    config = request.app.state.config
    if not config.api.auth.enabled:
        return   # auth disabled, all good
    if credentials is None or credentials.credentials != config.api.auth.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
```

Apply to each `GET` router with `dependencies=[Depends(require_api_key)]`.

---

## Tests to write

**`tests/integration/test_api.py`** using `httpx.AsyncClient` and `ASGITransport`:

```python
@pytest.fixture
def test_app():
    # Create app with InMemoryBackend and test config
    # Include a valid ingest_secret in the test config
    ...

async def test_post_spans_without_auth_returns_401()
async def test_post_spans_with_correct_auth_ingests_spans()
async def test_post_spans_with_wrong_secret_returns_401()
async def test_post_spans_partial_rejection_returns_200()
    # Batch of 5 spans where 1 has an oversized attribute
    # Should return 200 with ingested=4, rejected=1
async def test_get_traces_returns_list()
async def test_get_traces_filter_by_agent_id()
async def test_get_trace_by_id_returns_span_waterfall()
async def test_get_cost_returns_aggregated_rows()
async def test_get_alerts_returns_list()
async def test_get_metrics_returns_prometheus_format()
    # Response text should contain "ocw_cost_usd_total"
async def test_get_endpoint_requires_api_key_when_auth_enabled()
async def test_docs_endpoint_is_accessible()
    # GET /docs should return 200
```
