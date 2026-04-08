# Task 01 — Database Layer
**Depends on:** Task 00 (foundation) complete.
**Parallel with:** Tasks 02–11 once this task's `StorageBackend` protocol is defined.
**Estimated scope:** Medium.

---

## What this task covers

- DuckDB schema and migration runner
- `StorageBackend` protocol (the interface all other tasks build against)
- All database query methods
- Storage retention cleanup job

---

## Deliverables

### `ocw/core/db.py`

#### StorageBackend protocol

Define this protocol first — other tasks depend on it to write against a stable interface
even before the DuckDB implementation is complete. Other tasks may use a mock/stub
implementation during development.

```python
from typing import Protocol, runtime_checkable
from ocw.core.models import (
    NormalizedSpan, SessionRecord, AgentRecord, Alert, DriftBaseline,
    SchemaValidationResult, TraceRecord, CostRow,
    TraceFilters, CostFilters, AlertFilters,
)


@runtime_checkable
class StorageBackend(Protocol):
    def insert_span(self, span: NormalizedSpan) -> None: ...
    def insert_alert(self, alert: Alert) -> None: ...
    def insert_validation(self, result: SchemaValidationResult) -> None: ...
    def upsert_session(self, session: SessionRecord) -> None: ...
    def upsert_agent(self, agent: AgentRecord) -> None: ...
    def upsert_baseline(self, baseline: DriftBaseline) -> None: ...
    def get_session(self, session_id: str) -> SessionRecord | None: ...
    def get_session_by_conversation(self, conversation_id: str) -> SessionRecord | None: ...
    def get_traces(self, filters: TraceFilters) -> list[TraceRecord]: ...
    def get_trace_spans(self, trace_id: str) -> list[NormalizedSpan]: ...
    def get_cost_summary(self, filters: CostFilters) -> list[CostRow]: ...
    def get_alerts(self, filters: AlertFilters) -> list[Alert]: ...
    def get_baseline(self, agent_id: str) -> DriftBaseline | None: ...
    def get_completed_sessions(self, agent_id: str, limit: int) -> list[SessionRecord]: ...
    def get_completed_session_count(self, agent_id: str) -> int: ...
    def get_tool_calls(self, agent_id: str | None, since: datetime | None,
                       tool_name: str | None) -> list[dict]: ...
    def get_daily_cost(self, agent_id: str, date: date) -> float: ...
    def get_session_cost(self, session_id: str) -> float: ...
    def get_recent_spans(self, session_id: str, limit: int) -> list[NormalizedSpan]: ...
    def delete_spans_before(self, cutoff: datetime) -> int: ...
    def close(self) -> None: ...
```

#### DuckDB schema

```sql
-- migrations/001_initial.sql (embedded as a string in MIGRATIONS list)

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id    TEXT PRIMARY KEY,
    name        TEXT,
    version     TEXT,
    provider    TEXT,
    first_seen  TIMESTAMPTZ NOT NULL,
    last_seen   TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id          TEXT PRIMARY KEY,
    agent_id            TEXT NOT NULL REFERENCES agents(agent_id),
    conversation_id     TEXT,
    started_at          TIMESTAMPTZ NOT NULL,
    ended_at            TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'active',
    total_cost_usd      DOUBLE,
    input_tokens        BIGINT DEFAULT 0,
    output_tokens       BIGINT DEFAULT 0,
    cache_tokens        BIGINT DEFAULT 0,
    tool_call_count     INTEGER DEFAULT 0,
    error_count         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS spans (
    span_id             TEXT PRIMARY KEY,
    trace_id            TEXT NOT NULL,
    parent_span_id      TEXT,
    session_id          TEXT REFERENCES sessions(session_id),
    agent_id            TEXT,
    name                TEXT NOT NULL,
    kind                TEXT NOT NULL,
    status_code         TEXT NOT NULL,
    status_message      TEXT,
    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ,
    duration_ms         DOUBLE,
    attributes          JSON NOT NULL DEFAULT '{}',
    provider            TEXT,
    model               TEXT,
    tool_name           TEXT,
    input_tokens        BIGINT,
    output_tokens       BIGINT,
    cache_tokens        BIGINT,
    cost_usd            DOUBLE,
    request_type        TEXT,
    conversation_id     TEXT,
    events              JSON DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        TEXT PRIMARY KEY,
    agent_id        TEXT,
    session_id      TEXT,
    span_id         TEXT,
    fired_at        TIMESTAMPTZ NOT NULL,
    type            TEXT NOT NULL,
    severity        TEXT NOT NULL,
    title           TEXT NOT NULL,
    detail          JSON NOT NULL,
    acknowledged    BOOLEAN DEFAULT false,
    suppressed      BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS drift_baselines (
    agent_id                TEXT PRIMARY KEY REFERENCES agents(agent_id),
    sessions_sampled        INTEGER NOT NULL,
    computed_at             TIMESTAMPTZ NOT NULL,
    avg_input_tokens        DOUBLE,
    stddev_input_tokens     DOUBLE,
    avg_output_tokens       DOUBLE,
    stddev_output_tokens    DOUBLE,
    avg_session_duration_s  DOUBLE,
    stddev_session_duration DOUBLE,
    avg_tool_call_count     DOUBLE,
    stddev_tool_call_count  DOUBLE,
    common_tool_sequences   JSON,
    output_schema_inferred  JSON
);

CREATE TABLE IF NOT EXISTS schema_validations (
    validation_id   TEXT PRIMARY KEY,
    span_id         TEXT NOT NULL REFERENCES spans(span_id),
    agent_id        TEXT,
    validated_at    TIMESTAMPTZ NOT NULL,
    passed          BOOLEAN NOT NULL,
    errors          JSON DEFAULT '[]'
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_spans_trace_id     ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_agent_id     ON spans(agent_id);
CREATE INDEX IF NOT EXISTS idx_spans_start_time   ON spans(start_time);
CREATE INDEX IF NOT EXISTS idx_spans_tool_name    ON spans(tool_name);
CREATE INDEX IF NOT EXISTS idx_spans_conv_id      ON spans(conversation_id);
CREATE INDEX IF NOT EXISTS idx_sessions_agent_id  ON sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_conv_id   ON sessions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_alerts_agent_id    ON alerts(agent_id);
CREATE INDEX IF NOT EXISTS idx_alerts_fired_at    ON alerts(fired_at);
```

#### Migration runner

```python
MIGRATIONS: list[tuple[int, str]] = [
    (1, INITIAL_SCHEMA_SQL),
    # Future migrations:
    # (2, "ALTER TABLE spans ADD COLUMN new_col TEXT;"),
]


def run_migrations(conn) -> None:
    """Apply any unapplied migrations. Idempotent."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ)"
    )
    applied = {row[0] for row in conn.execute(
        "SELECT version FROM schema_migrations"
    ).fetchall()}
    for version, sql in MIGRATIONS:
        if version not in applied:
            conn.execute("BEGIN")
            try:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations VALUES (?, ?)",
                    (version, utcnow().isoformat())
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
```

#### DuckDBBackend class

```python
import duckdb
from ocw.core.config import StorageConfig


class DuckDBBackend:
    """Concrete DuckDB implementation of StorageBackend."""

    def __init__(self, config: StorageConfig):
        db_path = Path(config.path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(db_path))
        run_migrations(self.conn)

    # Implement all StorageBackend methods.
    # Key implementation notes:

    # insert_span: must also upsert the agent row and update session totals atomically.
    # get_session_by_conversation: used by ingest to route spans to existing sessions.
    # get_daily_cost: used by alert engine to check budget thresholds.
    # get_recent_spans: used by alert engine for retry loop detection (last N spans).
    # delete_spans_before: used by retention cleanup job.
    # All queries: use parameterised queries — never f-string SQL.

    def close(self) -> None:
        self.conn.close()


def open_db(config: StorageConfig) -> DuckDBBackend:
    """Open the database and return a backend instance."""
    return DuckDBBackend(config)
```

#### In-memory backend for tests

```python
class InMemoryBackend:
    """
    In-memory StorageBackend for tests. Uses DuckDB with ':memory:' path.
    Provides the same interface as DuckDBBackend but resets between tests.
    """

    def __init__(self):
        self.conn = duckdb.connect(":memory:")
        run_migrations(self.conn)
        # ... delegate all methods to conn
```

---

### `ocw/core/retention.py`

```python
from datetime import timedelta
from ocw.core.db import StorageBackend
from ocw.core.config import StorageConfig
from ocw.utils.time_parse import utcnow


def run_retention_cleanup(db: StorageBackend, config: StorageConfig) -> int:
    """
    Delete spans older than config.retention_days.
    Returns the number of spans deleted.
    Called by the apscheduler background job in ocw serve.
    """
    cutoff = utcnow() - timedelta(days=config.retention_days)
    return db.delete_spans_before(cutoff)
```

---

## Session continuity rule

When inserting a new span that has a `conversation_id`:
1. Check if a session with that `conversation_id` already exists (any status)
2. If yes: attribute the span to that existing session, update `ended_at`
3. If no: create a new session

This means agents that persist conversation IDs across process restarts (e.g. OpenClaw)
correctly accumulate all their spans in one session even if `ocw` was restarted between runs.

---

## Tests to write

**`tests/integration/test_db.py`:**

```python
def test_migrations_run_on_empty_db()
def test_migrations_are_idempotent()
def test_insert_span_creates_agent_row()
def test_insert_span_upserts_session_totals()
def test_conversation_id_continuity_across_sessions()
    # Insert a session with conversation_id="conv-1"
    # Insert a span with conversation_id="conv-1" in a new session
    # Verify the span is attributed to the original session
def test_get_daily_cost_sums_correctly()
def test_get_recent_spans_returns_last_n()
def test_delete_spans_before_cutoff()
def test_in_memory_backend_resets_between_tests()
```

All tests use `InMemoryBackend`. No file I/O in DB tests.
