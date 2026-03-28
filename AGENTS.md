# AGENTS.md — OpenClawWatch

Instructions for AI coding agents (Claude Code, OpenClaw, Codex) working on this codebase.
Read this before touching any file.

---

## What this project is

`ocw` is a local-first, OTel-native observability CLI for AI agents. It runs entirely on the
developer's machine — no cloud backend, no signup required. It captures telemetry from agent
runtimes, stores it in a local DuckDB database, and exposes a CLI and local REST API for
querying.

Install: `pip install ocw`
Command: `ocw <subcommand>`

---

## Repo layout

```
openclawwatch/
├── ocw/                    Python package
│   ├── cli/                Click CLI commands (one file per command)
│   ├── core/               Domain logic — NO CLI or HTTP imports allowed here
│   ├── otel/               OTel SDK wiring
│   ├── api/                FastAPI local REST API
│   ├── sdk/                Python instrumentation SDK
│   └── utils/              Formatting, time parsing, ID generation
├── sdk-ts/                 TypeScript SDK (@ocw/sdk)
├── pricing/                models.toml — community-maintained model pricing
├── schemas/                config.schema.json
└── tests/
    ├── factories.py        Span factory — use this in all synthetic tests
    ├── unit/               Pure logic tests, no I/O
    ├── synthetic/          Span injection tests via factories.py
    ├── agents/             Mock agent scenario scripts
    ├── integration/        CLI + API integration tests
    └── e2e/                Real LLM tests — skipped without API key env vars
```

---

## Critical rules — read these before writing any code

### 1. Never use SQLite
The storage engine is **DuckDB**. Never import `sqlite3`. Never write SQLite-style queries.
DuckDB is columnar. Use `TIMESTAMPTZ` not `TEXT` for timestamps. Use `JSON` not `TEXT` for
JSON blobs. See `ocw/core/db.py` for the schema and `StorageBackend` protocol.

### 2. Config is TOML — binary mode required
Config is loaded via `tomllib` (stdlib 3.11+) or `tomli` backport (3.10).
`tomllib.load()` requires **binary mode**: `open(path, "rb")` not `open(path, "r")`.
Using text mode raises `TypeError` at runtime. Every config load must use `"rb"`.
Writing config uses `tomli_w`.

### 3. `ocw/core/` has no CLI or HTTP imports
The `core/` package contains pure domain logic. It must not import from `ocw.api` or
`ocw.cli`. CLI commands import from core. The API imports from core. Core imports from
nothing in this package.

### 4. `@watch()` alone does not create LLM spans
The `@watch()` decorator in `ocw/sdk/agent.py` creates session start/end spans only.
Individual LLM call spans require `patch_anthropic()`, `patch_openai()`, or similar provider
patches. Tests must verify LLM call spans exist, not just session spans.

### 5. Never use unicode bullet characters in output
Rich handles bullet formatting. Never hardcode `•` or `\u2022` in text output.

### 6. Ingest endpoint requires authentication
`POST /api/v1/spans` requires `Authorization: Bearer <ingest_secret>`. The secret is stored
in `security.ingest_secret` in `ocw.toml`. Reject with 401 if missing or wrong. Tests must
cover both authenticated and unauthenticated cases.

### 7. Alert payloads strip captured content by default
Before dispatching to external channels (ntfy, webhook, Discord, Telegram), remove
`prompt_content`, `completion_content`, `tool_input`, `tool_output` from the detail dict
unless `alerts.include_captured_content = true` in config. Stdout and file channels always
get the full payload.

---

## Test commands

```bash
# Unit tests only (pure logic, no I/O, <1 second)
pytest tests/unit/

# Synthetic span injection tests (zero cost, deterministic)
pytest tests/synthetic/

# Mock agent scenario tests (full SDK path, zero cost)
pytest tests/agents/

# CLI + API integration tests
pytest tests/integration/

# Real LLM tests (requires OCW_ANTHROPIC_API_KEY env var — auto-skipped otherwise)
pytest tests/e2e/

# All non-e2e tests (what CI runs on every commit)
pytest tests/unit/ tests/synthetic/ tests/agents/ tests/integration/
```

---

## Code quality commands

```bash
ruff check ocw/          # linting
mypy ocw/                # type checking
```

---

## Database migrations

Migrations live in `ocw/core/db.py` as a `MIGRATIONS` list of `(version, sql)` tuples.
To add a migration:
1. Add a new tuple at the end of `MIGRATIONS` with the next version number
2. The migration runner applies unapplied migrations automatically on startup
3. Never modify existing migrations — always add new ones

---

## Span factory

All synthetic and mock-agent tests use `tests/factories.py`. Never create `NormalizedSpan`
objects directly in tests — always go through the factory. This ensures consistency and
makes tests readable.

```python
from tests.factories import make_llm_span, make_session

span = make_llm_span(agent_id="test-agent", input_tokens=1000, output_tokens=200)
session = make_session(agent_id="test-agent")
```

---

## Dependency structure (what can be worked on in parallel)

1. `tasks/00-foundation.md` — must be done first; defines all interfaces
2. All other task files are parallelisable once foundation is complete

Do not import between parallel tracks except through the interfaces defined in foundation.
