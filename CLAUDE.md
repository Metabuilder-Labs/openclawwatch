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
├── schemas/                config.schema.json
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

- **`ocw/core/db.py`**: `StorageBackend` protocol + `DuckDBBackend` + `InMemoryBackend` (for tests) + migration runner. Migrations are `(version, sql)` tuples in a `MIGRATIONS` list — never modify existing ones, only append.
- **`ocw/core/ingest.py`**: `IngestPipeline` (central hub), `SpanSanitizer` (rejects oversized/malformed spans).
- **`ocw/core/cost.py`**: `CostEngine` + `calculate_cost()`. Pricing loaded from `pricing/models.toml`.
- **`ocw/core/alerts.py`**: `AlertEngine` with 13 alert types, `CooldownTracker`, `AlertDispatcher` routing to 6 channel types (stdout, file, ntfy, webhook, Discord, Telegram).
- **`ocw/core/drift.py`**: `DriftDetector` — Z-score based behavioral drift detection, fires at session end.
- **`ocw/core/schema_validator.py`**: Validates tool outputs against declared or genson-inferred JSON Schema.
- **`ocw/core/models.py`**: All domain dataclasses — `NormalizedSpan`, `SessionRecord`, `Alert`, `DriftBaseline`, filter types, etc.
- **`ocw/core/config.py`**: `OcwConfig` dataclass tree, TOML loading/writing, config file discovery.
- **`ocw/sdk/agent.py`**: `@watch()` decorator creates session spans only. LLM call spans require `patch_anthropic()`, `patch_openai()`, etc.
- **`ocw/api/app.py`**: FastAPI app factory. `ocw serve` starts it with uvicorn.
- **`ocw/otel/semconv.py`**: `GenAIAttributes` and `OcwAttributes` — OTel GenAI semantic convention constants.

### Session Continuity

When a span has a `conversation_id` matching an existing session, it's attributed to that session (even across process restarts). New `conversation_id` = new session.

## Critical Rules

1. **DuckDB only** — never import `sqlite3` or write SQLite-style queries. Use `TIMESTAMPTZ` not `TEXT` for timestamps, `JSON` not `TEXT` for JSON.
2. **TOML binary mode** — `tomllib.load()` requires `open(path, "rb")` not `"r"`. Text mode raises `TypeError` at runtime. Use the conditional import: `tomllib` (3.11+) or `tomli` (3.10). Writing config uses `tomli_w`.
3. **`@watch()` alone does NOT create LLM spans** — only session start/end. Provider patches (`patch_anthropic()`, `patch_openai()`, etc.) are needed for individual LLM call spans.
4. **Ingest auth** — `POST /api/v1/spans` requires `Authorization: Bearer <ingest_secret>` from `security.ingest_secret` in `ocw.toml`.
5. **Alert content stripping** — remove `prompt_content`, `completion_content`, `tool_input`, `tool_output` from alert payloads sent to external channels unless `alerts.include_captured_content = true`. Stdout and file channels always get full payload.
6. **No unicode bullets** — never hardcode `•` or `\u2022`; Rich handles bullet formatting.
7. **Parameterised SQL only** — never use f-string SQL.
8. **All test spans via factory** — never construct `NormalizedSpan` directly in tests; use `tests/factories.py` (`make_llm_span`, `make_session`, `make_tool_span`, `make_session_with_spans`).
9. **Use `utcnow()` for timestamps** — always use `ocw.utils.time_parse.utcnow()` instead of `datetime.now()` or `datetime.utcnow()`. It returns timezone-aware UTC datetimes.
10. **Use semconv constants** — reference `GenAIAttributes` and `OcwAttributes` from `ocw/otel/semconv.py` instead of hardcoding OTel attribute name strings.

## Config

Config is TOML, discovered at: `ocw.toml` -> `.ocw/config.toml` -> `~/.config/ocw/config.toml`. Override with `--config` or `OCW_CONFIG` env var. Full config hierarchy is in `ocw/core/config.py` (`OcwConfig` dataclass).
