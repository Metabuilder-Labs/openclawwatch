# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`ocw` (OpenClawWatch) is a local-first, OTel-native observability CLI for AI agents. No cloud backend, no signup. It captures telemetry from agent runtimes, stores it in a local DuckDB database, and exposes a CLI + local REST API for querying. Install via `pip install ocw`, run via `ocw <subcommand>`. Requires Python >=3.10.

## Build & Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Linting and type checking
ruff check ocw/                  # line-length=100, target py310
mypy ocw/                        # strict mode

# Tests (CI runs all except e2e)
pytest tests/unit/ tests/synthetic/ tests/agents/ tests/integration/

# Individual test layers
pytest tests/unit/               # Pure logic, no I/O, <1s
pytest tests/synthetic/          # Span injection via factories, zero cost
pytest tests/agents/             # Mock agent scenarios, full SDK path
pytest tests/integration/        # CLI + API integration

# Run a single test file or test function
pytest tests/unit/test_config.py
pytest tests/unit/test_config.py::test_function_name -v

# Real LLM tests (requires OCW_ANTHROPIC_API_KEY — auto-skipped otherwise)
pytest tests/e2e/

# TypeScript SDK (independent package)
cd sdk-ts && npm install && npm test
```


## Repo Layout

```
openclawwatch/
├── ocw/                    Python package
│   ├── cli/                Click CLI commands (one file per command)
│   ├── core/               Domain logic — NO CLI or HTTP imports allowed here
│   ├── otel/               OTel SDK wiring + semantic conventions
│   ├── api/                FastAPI local REST API
│   ├── sdk/                Python instrumentation SDK
│   └── utils/              Formatting, time parsing, ID generation
├── sdk-ts/                 TypeScript SDK (@ocw/sdk)
├── pricing/                models.toml — community-maintained model pricing (USD per million tokens)
└── tests/
    ├── factories.py        Span factory — use this in ALL tests
    ├── unit/               Pure logic tests, no I/O
    ├── synthetic/          Span injection tests via factories.py
    ├── agents/             Mock agent scenario scripts
    ├── integration/        CLI + API integration tests
    └── e2e/                Real LLM tests — skipped without API key env vars
```

## Architecture

### Data Flow

Spans enter from two paths, both converging at `IngestPipeline.process()`:
1. **In-process**: Python SDK `@watch()` + provider patches -> `OcwSpanExporter` -> `IngestPipeline`
2. **HTTP**: TypeScript SDK (or any OTLP client) -> `POST /api/v1/spans` (auth required) -> `IngestPipeline`

Post-ingest hooks run synchronously after each span is written to DB:
1. `CostEngine.process_span()` — calculates USD cost from token counts
2. `AlertEngine.evaluate()` — checks all per-span alert rules
3. `SchemaValidator.validate()` — validates tool outputs against JSON Schema

### Package Dependency Rules

- `ocw/core/` is pure domain logic. **Must never import from `ocw.cli` or `ocw.api`**. CLI and API import from core, not the reverse.
- `ocw/otel/semconv.py` is pure constants with no internal imports.
- `sdk-ts/` is fully independent from Python — communicates only via HTTP.

### Key Modules

- **`ocw/core/db.py`**: `StorageBackend` protocol + `DuckDBBackend` + `InMemoryBackend` (for tests) + migration runner. Migrations are `(version, sql)` tuples in a `MIGRATIONS` list — never modify existing ones, only append. **Note:** `StorageBackend` doesn't cover every query. Some callers (e.g. `CostEngine`, `cmd_status`) access `db.conn` directly for queries not in the protocol (cost updates, active session lookups). Helper `_row_to_session()` is used to convert raw DuckDB rows.
- **`ocw/core/ingest.py`**: `IngestPipeline` (central hub), `SpanSanitizer` (rejects oversized/malformed spans), `strip_captured_content()`. Post-ingest hooks (cost, alerts, schema) are optional and error-tolerant — hook failures are logged, never propagated.
- **`ocw/core/pricing.py`**: `ModelRates` (frozen dataclass), `load_pricing_table()` (LRU-cached), `get_rates(provider, model)`. Falls back to default rates for unknown models.
- **`ocw/core/cost.py`**: `calculate_cost()` (pure function, rounds to 8dp) + `CostEngine` (post-ingest hook that updates `spans.cost_usd` and `sessions.total_cost_usd` via `db.conn` — see db.py note). Pricing loaded from `pricing/models.toml`.
- **`ocw/core/alerts.py`**: `AlertEngine` with 13 alert types, `CooldownTracker` (in-memory, per agent+type, resets on restart), `AlertDispatcher` routing to 6 channel types (stdout, file, ntfy, webhook, Discord, Telegram). `AlertEngine.fire()` is the external entry point for other modules (SchemaValidator, DriftDetector) to fire alerts. Suppressed alerts are still persisted to DB but not dispatched to channels. Hardcoded thresholds: retry loop fires at 4+ identical tool calls in last 6 spans; failure rate fires at >20% errors in last 20 spans (checked every 5th error); session duration default 3600s. Stdout and file channels always include full detail regardless of `include_captured_content` config.
- **`ocw/core/drift.py`**: `DriftDetector` — Z-score based behavioral drift detection, fires at session end.
- **`ocw/core/schema_validator.py`**: Validates tool outputs against declared or genson-inferred JSON Schema. Only fires on `gen_ai.tool.call` spans with `gen_ai.tool.output` in attributes. Schema priority: 1) declared file from agent config `output_schema`, 2) inferred schema from `DriftBaseline.output_schema_inferred`. Caches schemas in-memory per agent.
- **`ocw/core/models.py`**: All domain dataclasses — `NormalizedSpan`, `SessionRecord`, `Alert`, `DriftBaseline`, filter types, etc.
- **`ocw/core/config.py`**: `OcwConfig` dataclass tree, TOML loading/writing, config file discovery.
- **`ocw/sdk/agent.py`**: `@watch()` decorator creates session spans only. `record_llm_call()` and `record_tool_call()` create child spans for manual instrumentation. LLM call spans from provider clients require `patch_anthropic()`, `patch_openai()`, etc.
- **`ocw/sdk/transport.py`**: `HttpTransport` — buffers up to 1000 spans, retries with exponential backoff (3 attempts, 2s base). Used when `ocw serve` runs as a separate process.
- **`ocw/sdk/bootstrap.py`**: `ensure_initialised()` — lazy, thread-safe, idempotent bootstrap of config -> DB -> IngestPipeline -> TracerProvider. Called automatically by `@watch()` and all `patch_*()` functions. Registers atexit flush.
- **`ocw/sdk/integrations/`**: `Integration` protocol in `base.py`. Provider patches (anthropic, openai, gemini, bedrock) monkey-patch client methods to create OTel spans with token usage. Framework patches (langchain, langgraph, crewai, autogen) wrap LLM/tool methods. `llamaindex.py` and `openai_agents_sdk.py` are thin wrappers around those SDKs' native OTel support. `nemoclaw.py` is a WebSocket observer for OpenShell Gateway sandbox events.
- **`ocw/otel/provider.py`**: `OcwSpanExporter` (custom `SpanExporter` that feeds spans into `IngestPipeline`), `convert_otel_span()` (OTel `ReadableSpan` → `NormalizedSpan`), `build_tracer_provider()` (sets up global `TracerProvider` with local + optional OTLP exporters).
- **`ocw/otel/exporters.py`**: Prometheus metric reader setup via `build_prometheus_exporter()`.
- **`ocw/otel/semconv.py`**: `GenAIAttributes` and `OcwAttributes` — OTel GenAI semantic convention constants.
- **`ocw/api/app.py`**: FastAPI app factory. `ocw serve` starts it with uvicorn. Accepts `db`, `config`, `ingest_pipeline` for testability. Registers all routers under `/api/v1` plus `/metrics`.
- **`ocw/api/middleware.py`**: `IngestAuthMiddleware` — protects `POST /api/v1/spans` with Bearer token. Returns `JSONResponse(401)` directly (not `HTTPException`, which doesn't propagate from `BaseHTTPMiddleware.dispatch`).
- **`ocw/api/deps.py`**: `require_api_key` — FastAPI dependency for optional API key auth on GET endpoints. Only enforced when `api.auth.enabled = true` in config.
- **`ocw/api/routes/`**: One file per resource — `spans.py` (OTLP JSON ingest), `traces.py`, `cost.py`, `tools.py`, `alerts.py`, `drift.py`, `metrics.py` (Prometheus text format from DB queries).
- **`ocw/cli/main.py`**: Root Click group with global options (`--config`, `--json`, `--no-color`, `--db`, `--agent`, `-v`). Registers all subcommands.

### CLI Commands

| Command | File | Description |
|---|---|---|
| `ocw onboard` | `cmd_onboard.py` | Setup wizard: agent ID, budget, ingest secret, optional daemon install (launchd/systemd) |
| `ocw status` | `cmd_status.py` | Agent overview: session, cost, tokens, alerts. Exit 1 if active alerts |
| `ocw traces` | `cmd_traces.py` | List recent traces in table format |
| `ocw trace <id>` | `cmd_traces.py` | Span waterfall tree for a single trace |
| `ocw cost` | `cmd_cost.py` | Cost breakdown by day/agent/model/tool with `--json` support |
| `ocw alerts` | `cmd_alerts.py` | Alert history with severity/type filtering |
| `ocw tools` | `cmd_tools.py` | Tool call summary: call counts, avg duration |
| `ocw export` | `cmd_export.py` | Export spans as json (NDJSON), csv, otlp, or openevals format |
| `ocw serve` | `cmd_serve.py` | Start FastAPI + uvicorn server with retention cleanup cron |
| `ocw doctor` | `cmd_doctor.py` | Health checks (config, DB, secrets, webhooks). Exit 0/1/2 |

All commands support `--json` for machine-readable output. Commands that query alerts use exit code 1 if active (unacknowledged, unsuppressed) alerts exist.

**CLI testing pattern:** Tests use `click.testing.CliRunner` with `unittest.mock.patch` on `ocw.cli.main.load_config` and `ocw.cli.main.open_db` to inject an `InMemoryBackend` and test config. See `tests/integration/test_cli.py`. Note: `cmd_doctor` opens its own DuckDB connection via `config.storage.path` to verify writability — in tests you must set this to a real temp path (e.g. `tmp_path / "test.duckdb"`).

### REST API

The API has two auth layers:
1. **Ingest auth** (middleware): `POST /api/v1/spans` requires `Authorization: Bearer <ingest_secret>`. Handled by `IngestAuthMiddleware`, which returns a `JSONResponse` directly — do **not** use `HTTPException` in `BaseHTTPMiddleware.dispatch` as it won't be caught by FastAPI's exception handler.
2. **API key auth** (dependency): All GET endpoints use `Depends(require_api_key)`. Only enforced when `api.auth.enabled = true`.

`POST /api/v1/spans` accepts OTLP JSON (`{"resourceSpans": [...]}`). Partial failures return 200 with `ingested`/`rejected` counts — 400 only if the entire body is malformed. The route parses OTLP spans into `NormalizedSpan` and feeds each through `IngestPipeline.process()`. Key parsing details: resource attributes are merged with span attributes (span wins on conflict); OTLP timestamps are nanosecond strings; OTLP `intValue` fields are strings (per spec for large numbers); unknown attribute value types silently become `None`.

`GET /metrics` generates Prometheus text format by querying the DB on each request (not using the OTel Prometheus exporter), so data is accurate after restarts. No caching — expensive on large datasets.

For `GET /api/v1/drift`, if `agent_id` is missing, return `JSONResponse(status_code=400)` — do not use a union return type like `dict | JSONResponse` as FastAPI cannot generate a response model for it. Use `response_model=None` on the decorator instead.

Integration tests use `httpx.AsyncClient` with `httpx.ASGITransport(app=app)` against `InMemoryBackend`. Synthetic alert tests use `unittest.mock.MagicMock` for the DB — you must explicitly set up `db.get_recent_spans.return_value` before calling `engine.evaluate()`, and silence channels with `engine.dispatcher.channels = []`.

### Session Continuity

When a span has a `conversation_id` matching an existing session, it's attributed to that session (even across process restarts). New `conversation_id` = new session.

## Critical Rules

1. **DuckDB only** — never import `sqlite3` or write SQLite-style queries. Use `TIMESTAMPTZ` not `TEXT` for timestamps, `JSON` not `TEXT` for JSON. When extracting dates from `TIMESTAMPTZ` columns, always use `CAST(col AT TIME ZONE 'UTC' AS DATE)` — bare `CAST(col AS DATE)` converts to the local timezone first, causing mismatches with Python's `utcnow().date()`.
2. **TOML binary mode** — `tomllib.load()` requires `open(path, "rb")` not `"r"`. Text mode raises `TypeError` at runtime. Use the conditional import: `tomllib` (3.11+) or `tomli` (3.10). Writing config uses `tomli_w`.
3. **`@watch()` alone does NOT create LLM spans** — only session start/end. Provider patches (`patch_anthropic()`, `patch_openai()`, etc.) are needed for individual LLM call spans.
4. **Ingest auth** — `POST /api/v1/spans` requires `Authorization: Bearer <ingest_secret>` from `security.ingest_secret` in `ocw.toml`.
5. **Alert content stripping** — remove `prompt_content`, `completion_content`, `tool_input`, `tool_output` from alert payloads sent to external channels unless `alerts.include_captured_content = true`. Stdout and file channels always get full payload.
6. **No unicode bullets** — never hardcode `•` or `\u2022`; Rich handles bullet formatting.
7. **Parameterised SQL only** — never use f-string SQL.
8. **All test spans via factory** — never construct `NormalizedSpan` directly in tests; use `tests/factories.py` (`make_llm_span`, `make_session`, `make_tool_span`, `make_session_with_spans`).
9. **Use `utcnow()` for timestamps** — always use `ocw.utils.time_parse.utcnow()` instead of `datetime.now()` or `datetime.utcnow()`. It returns timezone-aware UTC datetimes.
10. **Use semconv constants** — reference `GenAIAttributes` and `OcwAttributes` from `ocw/otel/semconv.py` instead of hardcoding OTel attribute name strings.
11. **OTel TracerProvider is global and set-once** — `trace.set_tracer_provider()` only works once per process. In tests, set the provider once at module level (not per-test in a fixture) and clear spans between tests. Use a custom `_CollectingExporter(SpanExporter)` since `InMemorySpanExporter` is not available in the installed OTel version. See `tests/agents/test_mock_scenarios.py` for the SDK test pattern and `tests/integration/test_full_pipeline.py` for the pipeline pattern.
12. **New SDK integrations must call `ensure_initialised()`** — every `patch_*()` convenience function must call `from ocw.sdk.bootstrap import ensure_initialised; ensure_initialised()` before installing hooks. This lazily bootstraps the TracerProvider + IngestPipeline on first use.

## Config

Config is TOML, discovered at: `ocw.toml` -> `.ocw/config.toml` -> `~/.config/ocw/config.toml`. Override with `--config` or `OCW_CONFIG` env var. Full config hierarchy is in `ocw/core/config.py` (`OcwConfig` dataclass).

## Pricing

Model pricing lives in `pricing/models.toml` (USD per million tokens). Structure: `[provider.model_name]` with `input_per_mtok`, `output_per_mtok`, and optional `cache_read_per_mtok`/`cache_write_per_mtok`. Unknown models fall back to default rates ($0.50/$2.00 per MTok) with a logged warning. The pricing table is LRU-cached at process startup — restart to pick up changes.

## CI

GitHub Actions workflow at `.github/workflows/ci.yml` runs on push/PR to `main`:
- **`test`** job: Python 3.10/3.11/3.12 matrix — `ruff check` and `mypy` (continue-on-error), then `pytest tests/unit/ tests/synthetic/ tests/agents/ tests/integration/` (blocking)
- **`test-ts`** job: Node 20 — `npm install && npm test` in `sdk-ts/`

All steps are blocking — lint, typecheck, and tests must pass for CI to go green.

## Packaging

Build system is hatchling. The `pyproject.toml` requires `[tool.hatch.build.targets.wheel] packages = ["ocw"]` because the package name (`openclawwatch`) differs from the directory name (`ocw`). Without this, `pip install -e .` fails.

Key runtime dependency: `pytz` is required by DuckDB for `TIMESTAMPTZ` column handling — it's listed explicitly in `dependencies` because DuckDB doesn't declare it on all platforms.

## Task Specs

Implementation specs for initial development live in `.claude/` (00-foundation.md through 11-test-harness.md). These are historical — all tasks are complete. They remain useful as architectural reference for understanding design intent behind each module.
