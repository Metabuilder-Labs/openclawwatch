# OCW MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ocw mcp` — a stdio MCP server that gives Claude Code two-way access to OCW observability data without requiring `ocw serve`.

**Architecture:** New `ocw/mcp/server.py` holds a FastMCP instance and all 12 tool handlers as plain testable functions; `ocw/cli/cmd_mcp.py` opens a read-only DuckDB connection and calls `mcp.run()`. The MCP server never uses `DuckDBBackend` directly — it opens the DB file with `read_only=True` to avoid lock collisions with `ocw serve`. The single write tool (`acknowledge_alert`) opens a short-lived read-write connection only for its UPDATE.

**Tech Stack:** `fastmcp` (optional dep), `duckdb` (already a dep), Click (already a dep), `InMemoryBackend` for tests (already in `ocw/core/db.py`).

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `ocw/mcp/__init__.py` | empty package marker |
| Create | `ocw/mcp/server.py` | FastMCP instance, module-level state, all 12 tool handlers |
| Create | `ocw/cli/cmd_mcp.py` | `ocw mcp` Click command — bootstrap + `mcp.run()` |
| Modify | `ocw/cli/main.py` | register cmd_mcp; add `"mcp"` to `no_db_commands` |
| Modify | `pyproject.toml` | add `mcp = ["fastmcp"]` optional dep |
| Modify | `.github/workflows/ci.yml` | install `.[dev,mcp]` instead of `.[dev]` |
| Create | `tests/unit/test_mcp_server.py` | unit tests for all tool handlers |

---

## Task 1: Scaffold — deps, empty package, CLI registration

**Files:**
- Modify: `pyproject.toml`
- Create: `ocw/mcp/__init__.py`
- Create: `ocw/mcp/server.py` (skeleton only)
- Create: `ocw/cli/cmd_mcp.py`
- Modify: `ocw/cli/main.py`

- [ ] **Step 1.1: Add fastmcp optional dependency**

In `pyproject.toml`, after the `dev` line in `[project.optional-dependencies]`:

```toml
mcp       = ["fastmcp"]
```

Full section becomes:
```toml
[project.optional-dependencies]
langchain = ["langchain>=0.2"]
crewai    = ["crewai>=0.28"]
autogen   = ["pyautogen>=0.2"]
litellm   = ["litellm>=1.40"]
dev       = ["pytest", "pytest-asyncio", "httpx", "ruff", "mypy"]
mcp       = ["fastmcp"]
```

- [ ] **Step 1.2: Install the new optional dep**

```bash
pip install -e ".[dev,mcp]"
```

Expected: installs without error; `python -c "import fastmcp"` succeeds.

- [ ] **Step 1.3: Create the mcp package**

Create `ocw/mcp/__init__.py` — empty file.

Create `ocw/mcp/server.py` with just the skeleton:

```python
"""OCW MCP server — exposes observability data to Claude Code via stdio."""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("ocw")

# Module-level state initialised by init() or cmd_mcp.py
_ro_conn = None   # duckdb read-only connection
_config = None    # OcwConfig


def init(ro_conn, config) -> None:
    """Inject DB connection and config. Called by cmd_mcp.py and tests."""
    global _ro_conn, _config
    _ro_conn, _config = ro_conn, config


def _no_config() -> dict:
    return {"error": "No OCW config found. Run 'ocw onboard --claude-code' to set up."}
```

- [ ] **Step 1.4: Create cmd_mcp.py**

```python
"""ocw mcp — start the stdio MCP server."""
from __future__ import annotations

from pathlib import Path

import click
import duckdb

from ocw.core.config import find_config_file, load_config


@click.command("mcp")
@click.pass_context
def cmd_mcp(ctx: click.Context) -> None:
    """Start the OCW MCP server (stdio transport for Claude Code)."""
    from ocw.mcp.server import mcp, init

    config_path = find_config_file()
    if config_path is not None:
        config = load_config(str(config_path))
        db_path = str(Path(config.storage.path).expanduser())
        ro_conn = duckdb.connect(db_path, read_only=True)
        init(ro_conn, config)
    # If no config: init is not called; tools return the no-config sentinel.

    mcp.run()
```

- [ ] **Step 1.5: Register in main.py**

Add `"mcp"` to `no_db_commands` (line 27) and register the command.

In `main.py`, change:
```python
no_db_commands = {"stop", "uninstall", "onboard"}
```
to:
```python
no_db_commands = {"stop", "uninstall", "onboard", "mcp"}
```

At the bottom of `main.py`, add:
```python
from ocw.cli.cmd_mcp import cmd_mcp  # noqa: E402
cli.add_command(cmd_mcp, name="mcp")
```

- [ ] **Step 1.6: Verify scaffold**

```bash
ocw mcp --help
```

Expected output includes `Start the OCW MCP server`.

- [ ] **Step 1.7: Commit scaffold**

```bash
git add ocw/mcp/__init__.py ocw/mcp/server.py ocw/cli/cmd_mcp.py ocw/cli/main.py pyproject.toml
git commit -m "feat(mcp): scaffold ocw mcp package, cmd, and fastmcp dep"
```

---

## Task 2: Self-monitoring tools — get_status, get_budget_headroom

**Files:**
- Modify: `ocw/mcp/server.py`
- Create: `tests/unit/test_mcp_server.py`

- [ ] **Step 2.1: Write failing tests**

Create `tests/unit/test_mcp_server.py`:

```python
"""Unit tests for OCW MCP server tool handlers."""
from __future__ import annotations

import pytest
from ocw.core.db import InMemoryBackend
from ocw.core.config import OcwConfig, AgentConfig, BudgetConfig, DefaultsConfig
from ocw.core.models import AlertType, Severity, Alert
from ocw.utils.time_parse import utcnow
from ocw.utils.ids import new_uuid
from tests.factories import make_session, make_llm_span, make_tool_span

from ocw.mcp.server import (
    _tool_get_status,
    _tool_get_budget_headroom,
)


def _make_config(agent_id: str = "test-agent", daily_usd: float | None = 5.0) -> OcwConfig:
    return OcwConfig(
        version="1",
        defaults=DefaultsConfig(budget=BudgetConfig(daily_usd=daily_usd)),
        agents={agent_id: AgentConfig(budget=BudgetConfig(daily_usd=daily_usd))},
    )


# --- get_status ---

def test_get_status_active_session():
    db = InMemoryBackend()
    session = make_session(agent_id="alpha", status="active", input_tokens=100, output_tokens=50)
    db.upsert_session(session)
    config = _make_config("alpha")

    result = _tool_get_status(db.conn, config, agent_id="alpha")

    assert result["agent_id"] == "alpha"
    assert result["status"] == "active"
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 50
    assert result["active_alerts"] == 0


def test_get_status_no_session():
    db = InMemoryBackend()
    config = _make_config("ghost")

    result = _tool_get_status(db.conn, config, agent_id="ghost")

    assert result["agent_id"] == "ghost"
    assert result["status"] == "idle"
    assert result["session_id"] is None


def test_get_status_no_config():
    from ocw.mcp.server import _no_config
    db = InMemoryBackend()
    # Simulate no config by passing None
    result = _tool_get_status(db.conn, None, agent_id="x")
    assert "error" in result


# --- get_budget_headroom ---

def test_get_budget_headroom_within_budget():
    db = InMemoryBackend()
    config = _make_config("alpha", daily_usd=10.0)
    span = make_llm_span(agent_id="alpha", cost_usd=2.50)
    db.insert_span(span)

    result = _tool_get_budget_headroom(db.conn, config, agent_id="alpha")

    assert result["agent_id"] == "alpha"
    assert result["daily_limit_usd"] == 10.0
    assert abs(result["daily_spent_usd"] - 2.50) < 0.01
    assert abs(result["daily_remaining_usd"] - 7.50) < 0.01


def test_get_budget_headroom_no_limit():
    db = InMemoryBackend()
    config = _make_config("alpha", daily_usd=None)

    result = _tool_get_budget_headroom(db.conn, config, agent_id="alpha")

    assert result["daily_limit_usd"] is None
    assert result["daily_remaining_usd"] is None
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
pytest tests/unit/test_mcp_server.py -v 2>&1 | head -30
```

Expected: `ImportError` — `_tool_get_status` not defined yet.

- [ ] **Step 2.3: Implement the handlers in server.py**

Add to `ocw/mcp/server.py` after the `_no_config()` function:

```python
# ---------------------------------------------------------------------------
# Handler functions — called by @mcp.tool() wrappers and directly in tests
# ---------------------------------------------------------------------------

def _tool_get_status(conn, config, agent_id: str | None = None) -> dict:
    if config is None:
        return _no_config()
    from ocw.core.models import AlertFilters
    from ocw.utils.time_parse import utcnow

    # Find most recent active session for this agent, or latest completed
    if agent_id:
        aids = [agent_id]
    else:
        rows = conn.execute(
            "SELECT DISTINCT agent_id FROM sessions ORDER BY agent_id"
        ).fetchall()
        aids = [r[0] for r in rows]

    results = []
    for aid in aids:
        row = conn.execute(
            "SELECT session_id, status, started_at, ended_at, input_tokens, "
            "output_tokens, tool_call_count, error_count, total_cost_usd "
            "FROM sessions WHERE agent_id = $1 AND status = 'active' "
            "ORDER BY started_at DESC LIMIT 1",
            [aid],
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT session_id, status, started_at, ended_at, input_tokens, "
                "output_tokens, tool_call_count, error_count, total_cost_usd "
                "FROM sessions WHERE agent_id = $1 "
                "ORDER BY started_at DESC LIMIT 1",
                [aid],
            ).fetchone()

        active_alerts = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE agent_id = $1 "
            "AND acknowledged = false AND suppressed = false",
            [aid],
        ).fetchone()[0]

        today_cost = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) FROM spans "
            "WHERE agent_id = $1 AND CAST(start_time AT TIME ZONE 'UTC' AS DATE) = $2",
            [aid, utcnow().date()],
        ).fetchone()[0]

        if row:
            results.append({
                "agent_id": aid,
                "session_id": row[0],
                "status": row[1],
                "input_tokens": row[4] or 0,
                "output_tokens": row[5] or 0,
                "tool_call_count": row[6] or 0,
                "error_count": row[7] or 0,
                "cost_today_usd": float(today_cost),
                "active_alerts": active_alerts,
            })
        else:
            results.append({
                "agent_id": aid,
                "session_id": None,
                "status": "idle",
                "input_tokens": 0,
                "output_tokens": 0,
                "tool_call_count": 0,
                "error_count": 0,
                "cost_today_usd": float(today_cost),
                "active_alerts": active_alerts,
            })

    if agent_id:
        return results[0] if results else {"agent_id": agent_id, "status": "idle",
            "session_id": None, "input_tokens": 0, "output_tokens": 0,
            "tool_call_count": 0, "error_count": 0, "cost_today_usd": 0.0,
            "active_alerts": 0}
    return {"agents": results}


def _tool_get_budget_headroom(conn, config, agent_id: str) -> dict:
    if config is None:
        return _no_config()
    from ocw.core.config import resolve_effective_budget
    from ocw.utils.time_parse import utcnow

    budget = resolve_effective_budget(agent_id, config)
    today_cost = float(conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) FROM spans "
        "WHERE agent_id = $1 AND CAST(start_time AT TIME ZONE 'UTC' AS DATE) = $2",
        [agent_id, utcnow().date()],
    ).fetchone()[0])

    active_session = conn.execute(
        "SELECT COALESCE(total_cost_usd, 0.0) FROM sessions "
        "WHERE agent_id = $1 AND status = 'active' ORDER BY started_at DESC LIMIT 1",
        [agent_id],
    ).fetchone()
    session_cost = float(active_session[0]) if active_session else 0.0

    return {
        "agent_id": agent_id,
        "daily_limit_usd": budget.daily_usd,
        "daily_spent_usd": today_cost,
        "daily_remaining_usd": (budget.daily_usd - today_cost) if budget.daily_usd else None,
        "session_limit_usd": budget.session_usd,
        "session_spent_usd": session_cost,
        "session_remaining_usd": (budget.session_usd - session_cost) if budget.session_usd else None,
    }
```

Also add the FastMCP tool wrappers at the bottom of server.py:

```python
# ---------------------------------------------------------------------------
# FastMCP tool registrations
# ---------------------------------------------------------------------------

@mcp.tool()
def get_status(agent_id: str | None = None) -> dict:
    """Get current status for one agent (or all agents if agent_id is omitted)."""
    return _tool_get_status(_ro_conn, _config, agent_id)


@mcp.tool()
def get_budget_headroom(agent_id: str) -> dict:
    """Get budget limits vs current spend for an agent."""
    return _tool_get_budget_headroom(_ro_conn, _config, agent_id)
```

- [ ] **Step 2.4: Run tests**

```bash
pytest tests/unit/test_mcp_server.py::test_get_status_active_session \
       tests/unit/test_mcp_server.py::test_get_status_no_session \
       tests/unit/test_mcp_server.py::test_get_status_no_config \
       tests/unit/test_mcp_server.py::test_get_budget_headroom_within_budget \
       tests/unit/test_mcp_server.py::test_get_budget_headroom_no_limit -v
```

Expected: all 5 PASS.

- [ ] **Step 2.5: Commit**

```bash
git add ocw/mcp/server.py tests/unit/test_mcp_server.py
git commit -m "feat(mcp): get_status and get_budget_headroom tools"
```

---

## Task 3: Dashboard tools — list_agents, list_active_sessions

**Files:**
- Modify: `ocw/mcp/server.py`
- Modify: `tests/unit/test_mcp_server.py`

- [ ] **Step 3.1: Write failing tests**

Append to `tests/unit/test_mcp_server.py`:

```python
from ocw.mcp.server import _tool_list_agents, _tool_list_active_sessions


def test_list_agents_returns_all_known():
    db = InMemoryBackend()
    from ocw.core.models import AgentRecord
    db.upsert_agent(AgentRecord(agent_id="a1", first_seen=utcnow(), last_seen=utcnow()))
    db.upsert_agent(AgentRecord(agent_id="a2", first_seen=utcnow(), last_seen=utcnow()))
    span = make_llm_span(agent_id="a1", cost_usd=1.50)
    db.insert_span(span)

    result = _tool_list_agents(db.conn)

    ids = [a["agent_id"] for a in result["agents"]]
    assert "a1" in ids and "a2" in ids
    a1 = next(a for a in result["agents"] if a["agent_id"] == "a1")
    assert abs(a1["lifetime_cost_usd"] - 1.50) < 0.01


def test_list_agents_empty():
    db = InMemoryBackend()
    result = _tool_list_agents(db.conn)
    assert result["agents"] == []


def test_list_active_sessions_one_per_session():
    db = InMemoryBackend()
    s1 = make_session(agent_id="proj-a", status="active")
    s2 = make_session(agent_id="proj-a", status="active")
    s3 = make_session(agent_id="proj-b", status="active")
    s4 = make_session(agent_id="proj-b", status="completed")
    for s in [s1, s2, s3, s4]:
        db.upsert_session(s)

    result = _tool_list_active_sessions(db.conn)

    assert result["count"] == 3  # s1, s2, s3 — s4 excluded
    session_ids = {r["session_id"] for r in result["sessions"]}
    assert s1.session_id in session_ids
    assert s2.session_id in session_ids
    assert s3.session_id in session_ids
    assert s4.session_id not in session_ids


def test_list_active_sessions_empty():
    db = InMemoryBackend()
    result = _tool_list_active_sessions(db.conn)
    assert result["sessions"] == []
    assert result["count"] == 0
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
pytest tests/unit/test_mcp_server.py::test_list_agents_returns_all_known -v 2>&1 | tail -5
```

Expected: `ImportError` — `_tool_list_agents` not defined.

- [ ] **Step 3.3: Implement handlers**

Add to `ocw/mcp/server.py` (before the FastMCP wrappers section):

```python
def _tool_list_agents(conn) -> dict:
    rows = conn.execute(
        "SELECT a.agent_id, a.first_seen, a.last_seen, "
        "COALESCE(SUM(s.cost_usd), 0.0) AS lifetime_cost "
        "FROM agents a LEFT JOIN spans s ON a.agent_id = s.agent_id "
        "GROUP BY a.agent_id, a.first_seen, a.last_seen "
        "ORDER BY a.last_seen DESC"
    ).fetchall()
    return {
        "agents": [
            {
                "agent_id": r[0],
                "first_seen": r[1].isoformat() if r[1] else None,
                "last_seen": r[2].isoformat() if r[2] else None,
                "lifetime_cost_usd": float(r[3]),
            }
            for r in rows
        ]
    }


def _tool_list_active_sessions(conn) -> dict:
    rows = conn.execute(
        "SELECT session_id, agent_id, started_at, total_cost_usd, "
        "input_tokens, output_tokens, tool_call_count, error_count "
        "FROM sessions WHERE status = 'active' ORDER BY started_at DESC"
    ).fetchall()
    sessions = [
        {
            "session_id": r[0],
            "agent_id": r[1],
            "started_at": r[2].isoformat() if r[2] else None,
            "total_cost_usd": float(r[3]) if r[3] else 0.0,
            "input_tokens": r[4] or 0,
            "output_tokens": r[5] or 0,
            "tool_call_count": r[6] or 0,
            "error_count": r[7] or 0,
        }
        for r in rows
    ]
    return {"sessions": sessions, "count": len(sessions)}
```

Add FastMCP wrappers:

```python
@mcp.tool()
def list_agents() -> dict:
    """Historical summary of all known agents with lifetime cost."""
    if _ro_conn is None:
        return _no_config()
    return _tool_list_agents(_ro_conn)


@mcp.tool()
def list_active_sessions() -> dict:
    """All currently running sessions — one row per session, duplicates agent_id if parallel."""
    if _ro_conn is None:
        return _no_config()
    return _tool_list_active_sessions(_ro_conn)
```

- [ ] **Step 3.4: Run tests**

```bash
pytest tests/unit/test_mcp_server.py -k "list_agents or list_active_sessions" -v
```

Expected: all 4 PASS.

- [ ] **Step 3.5: Commit**

```bash
git add ocw/mcp/server.py tests/unit/test_mcp_server.py
git commit -m "feat(mcp): list_agents and list_active_sessions tools"
```

---

## Task 4: Dashboard tools — get_cost_summary, list_alerts

**Files:**
- Modify: `ocw/mcp/server.py`
- Modify: `tests/unit/test_mcp_server.py`

- [ ] **Step 4.1: Write failing tests**

Append to `tests/unit/test_mcp_server.py`:

```python
from ocw.mcp.server import _tool_get_cost_summary, _tool_list_alerts
from ocw.core.models import CostFilters, AlertFilters


def test_get_cost_summary_total():
    db = InMemoryBackend()
    s1 = make_llm_span(agent_id="a", cost_usd=1.00)
    s2 = make_llm_span(agent_id="a", cost_usd=2.50)
    db.insert_span(s1)
    db.insert_span(s2)

    result = _tool_get_cost_summary(db, agent_id="a", since=None, group_by="day")

    assert abs(result["total_cost_usd"] - 3.50) < 0.01
    assert len(result["rows"]) >= 1


def test_get_cost_summary_empty():
    db = InMemoryBackend()
    result = _tool_get_cost_summary(db, agent_id="nobody", since=None, group_by="day")
    assert result["total_cost_usd"] == 0.0
    assert result["rows"] == []


def test_list_alerts_returns_alerts():
    db = InMemoryBackend()
    alert = Alert(
        alert_id=new_uuid(),
        fired_at=utcnow(),
        type=AlertType.COST_BUDGET_DAILY,
        severity=Severity.WARNING,
        title="Budget exceeded",
        detail={"cost": 6.0},
        agent_id="a",
        session_id=None,
        span_id=None,
        acknowledged=False,
        suppressed=False,
    )
    db.insert_alert(alert)

    result = _tool_list_alerts(db, agent_id="a", severity=None, unread=False)

    assert result["count"] == 1
    assert result["alerts"][0]["alert_id"] == alert.alert_id
    assert result["alerts"][0]["type"] == "cost_budget_daily"


def test_list_alerts_empty():
    db = InMemoryBackend()
    result = _tool_list_alerts(db, agent_id="x", severity=None, unread=False)
    assert result["count"] == 0
    assert result["alerts"] == []
```

- [ ] **Step 4.2: Run to verify failures**

```bash
pytest tests/unit/test_mcp_server.py::test_get_cost_summary_total -v 2>&1 | tail -5
```

Expected: `ImportError`.

- [ ] **Step 4.3: Implement handlers**

Add to `ocw/mcp/server.py`:

```python
def _tool_get_cost_summary(
    db, agent_id: str | None, since: str | None, group_by: str
) -> dict:
    from ocw.core.models import CostFilters
    from ocw.utils.time_parse import parse_since
    filters = CostFilters(
        agent_id=agent_id,
        since=parse_since(since) if since else None,
        group_by=group_by,
    )
    rows = db.get_cost_summary(filters)
    total = sum(r.cost_usd for r in rows)
    return {
        "rows": [
            {
                "group": r.group,
                "agent_id": r.agent_id,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd,
            }
            for r in rows
        ],
        "total_cost_usd": total,
    }


def _tool_list_alerts(
    db, agent_id: str | None, severity: str | None, unread: bool
) -> dict:
    from ocw.core.models import AlertFilters, Severity
    filters = AlertFilters(
        agent_id=agent_id,
        severity=Severity(severity) if severity else None,
        unread=unread,
    )
    alerts = db.get_alerts(filters)
    return {
        "alerts": [
            {
                "alert_id": a.alert_id,
                "fired_at": a.fired_at.isoformat(),
                "type": a.type.value,
                "severity": a.severity.value,
                "title": a.title,
                "agent_id": a.agent_id,
                "acknowledged": a.acknowledged,
                "suppressed": a.suppressed,
            }
            for a in alerts
        ],
        "count": len(alerts),
    }
```

Note: these handlers take `db` (a `StorageBackend`) instead of `conn` — they use the protocol methods `get_cost_summary` and `get_alerts`. In tests pass `InMemoryBackend` directly. In FastMCP wrappers, pass a thin `_ProtocolDB` adapter that wraps `_ro_conn`.

Add a minimal adapter class near the top of `server.py` (after `_config = None`):

```python
class _ReadOnlyDB:
    """Wraps a read-only duckdb connection to satisfy StorageBackend protocol methods."""
    def __init__(self, conn):
        self.conn = conn

    def get_cost_summary(self, filters):
        from ocw.core.db import DuckDBBackend
        # Reuse DuckDBBackend's implementation via mixin — borrow the method
        return DuckDBBackend.get_cost_summary(self, filters)

    def get_alerts(self, filters):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_alerts(self, filters)

    def get_traces(self, filters):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_traces(self, filters)

    def get_trace_spans(self, trace_id):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_trace_spans(self, trace_id)

    def get_tool_calls(self, agent_id, since, tool_name):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_tool_calls(self, agent_id, since, tool_name)

    def get_baseline(self, agent_id):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_baseline(self, agent_id)

    def get_completed_sessions(self, agent_id, limit):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_completed_sessions(self, agent_id, limit)
```

And update `init()`:

```python
_ro_db = None   # _ReadOnlyDB wrapping _ro_conn

def init(ro_conn, config) -> None:
    global _ro_conn, _config, _ro_db
    _ro_conn, _config = ro_conn, config
    _ro_db = _ReadOnlyDB(ro_conn)
```

Add FastMCP wrappers:

```python
@mcp.tool()
def get_cost_summary(
    agent_id: str | None = None,
    since: str | None = None,
    group_by: str = "day",
) -> dict:
    """Cost breakdown grouped by day/agent/model. since accepts '24h', '7d', '2026-04-01'."""
    if _ro_db is None:
        return _no_config()
    return _tool_get_cost_summary(_ro_db, agent_id, since, group_by)


@mcp.tool()
def list_alerts(
    agent_id: str | None = None,
    severity: str | None = None,
    unread: bool = False,
) -> dict:
    """Alert history. severity: 'critical'|'warning'|'info'. unread=True for active only."""
    if _ro_db is None:
        return _no_config()
    return _tool_list_alerts(_ro_db, agent_id, severity, unread)
```

- [ ] **Step 4.4: Run tests**

```bash
pytest tests/unit/test_mcp_server.py -k "cost_summary or list_alerts" -v
```

Expected: all 4 PASS.

- [ ] **Step 4.5: Commit**

```bash
git add ocw/mcp/server.py tests/unit/test_mcp_server.py
git commit -m "feat(mcp): get_cost_summary and list_alerts tools"
```

---

## Task 5: Dashboard tools — list_traces, get_trace

**Files:**
- Modify: `ocw/mcp/server.py`
- Modify: `tests/unit/test_mcp_server.py`

- [ ] **Step 5.1: Write failing tests**

Append to `tests/unit/test_mcp_server.py`:

```python
from ocw.mcp.server import _tool_list_traces, _tool_get_trace


def test_list_traces_returns_recent():
    db = InMemoryBackend()
    span = make_llm_span(agent_id="a", cost_usd=0.50)
    db.insert_span(span)

    result = _tool_list_traces(db, agent_id="a", since=None, limit=20)

    assert result["count"] >= 1
    assert result["traces"][0]["trace_id"] == span.trace_id


def test_list_traces_empty():
    db = InMemoryBackend()
    result = _tool_list_traces(db, agent_id="nobody", since=None, limit=20)
    assert result["count"] == 0
    assert result["traces"] == []


def test_get_trace_returns_spans():
    db = InMemoryBackend()
    span = make_llm_span(agent_id="a")
    db.insert_span(span)

    result = _tool_get_trace(db, trace_id=span.trace_id)

    assert result["trace_id"] == span.trace_id
    assert result["span_count"] == 1
    assert result["spans"][0]["span_id"] == span.span_id


def test_get_trace_unknown():
    db = InMemoryBackend()
    result = _tool_get_trace(db, trace_id="nonexistent-trace")
    assert result["span_count"] == 0
    assert result["spans"] == []
```

- [ ] **Step 5.2: Run to verify failures**

```bash
pytest tests/unit/test_mcp_server.py::test_list_traces_returns_recent -v 2>&1 | tail -5
```

Expected: `ImportError`.

- [ ] **Step 5.3: Implement handlers**

Add to `ocw/mcp/server.py`:

```python
def _tool_list_traces(db, agent_id: str | None, since: str | None, limit: int) -> dict:
    from ocw.core.models import TraceFilters
    from ocw.utils.time_parse import parse_since
    filters = TraceFilters(
        agent_id=agent_id,
        since=parse_since(since) if since else None,
        limit=limit,
    )
    traces = db.get_traces(filters)
    return {
        "traces": [
            {
                "trace_id": t.trace_id,
                "agent_id": t.agent_id,
                "name": t.name,
                "start_time": t.start_time.isoformat() if t.start_time else None,
                "duration_ms": t.duration_ms,
                "cost_usd": t.cost_usd,
                "status_code": t.status_code,
                "span_count": t.span_count,
            }
            for t in traces
        ],
        "count": len(traces),
    }


def _tool_get_trace(db, trace_id: str) -> dict:
    spans = db.get_trace_spans(trace_id)
    return {
        "trace_id": trace_id,
        "spans": [
            {
                "span_id": s.span_id,
                "parent_span_id": s.parent_span_id,
                "name": s.name,
                "kind": s.kind.value,
                "status_code": s.status_code.value,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "duration_ms": s.duration_ms,
                "provider": s.provider,
                "model": s.model,
                "tool_name": s.tool_name,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
                "cost_usd": s.cost_usd,
            }
            for s in spans
        ],
        "span_count": len(spans),
    }
```

Add FastMCP wrappers:

```python
@mcp.tool()
def list_traces(
    agent_id: str | None = None,
    since: str | None = None,
    limit: int = 20,
) -> dict:
    """Recent traces with cost, duration, span count. since accepts '24h', '7d', '2026-04-01'."""
    if _ro_db is None:
        return _no_config()
    return _tool_list_traces(_ro_db, agent_id, since, limit)


@mcp.tool()
def get_trace(trace_id: str) -> dict:
    """Full span waterfall for a single trace."""
    if _ro_db is None:
        return _no_config()
    return _tool_get_trace(_ro_db, trace_id)
```

- [ ] **Step 5.4: Run tests**

```bash
pytest tests/unit/test_mcp_server.py -k "traces or get_trace" -v
```

Expected: all 4 PASS.

- [ ] **Step 5.5: Commit**

```bash
git add ocw/mcp/server.py tests/unit/test_mcp_server.py
git commit -m "feat(mcp): list_traces and get_trace tools"
```

---

## Task 6: Dashboard tools — get_tool_stats, get_drift_report

**Files:**
- Modify: `ocw/mcp/server.py`
- Modify: `tests/unit/test_mcp_server.py`

- [ ] **Step 6.1: Write failing tests**

Append to `tests/unit/test_mcp_server.py`:

```python
from ocw.mcp.server import _tool_get_tool_stats, _tool_get_drift_report
from ocw.core.models import DriftBaseline


def test_get_tool_stats_aggregates():
    db = InMemoryBackend()
    db.insert_span(make_tool_span(agent_id="a", tool_name="Read", duration_ms=100.0))
    db.insert_span(make_tool_span(agent_id="a", tool_name="Read", duration_ms=200.0))
    db.insert_span(make_tool_span(agent_id="a", tool_name="Edit", duration_ms=50.0))

    result = _tool_get_tool_stats(db, agent_id="a", since=None)

    tools = {t["tool_name"]: t for t in result["tools"]}
    assert tools["Read"]["call_count"] == 2
    assert tools["Edit"]["call_count"] == 1
    assert result["count"] == 2


def test_get_tool_stats_empty():
    db = InMemoryBackend()
    result = _tool_get_tool_stats(db, agent_id="nobody", since=None)
    assert result["tools"] == []
    assert result["count"] == 0


def test_get_drift_report_with_baseline():
    db = InMemoryBackend()
    baseline = DriftBaseline(
        agent_id="a",
        sessions_sampled=10,
        computed_at=utcnow(),
        avg_input_tokens=1000.0,
        stddev_input_tokens=100.0,
        avg_output_tokens=200.0,
        stddev_output_tokens=20.0,
        avg_session_duration_s=120.0,
        stddev_session_duration=15.0,
        avg_tool_call_count=5.0,
        stddev_tool_call_count=1.0,
    )
    db.upsert_baseline(baseline)

    result = _tool_get_drift_report(db, agent_id="a")

    assert result["agent_id"] == "a"
    assert result["baseline"]["sessions_sampled"] == 10
    assert result["baseline"]["avg_input_tokens"] == 1000.0


def test_get_drift_report_no_baseline():
    db = InMemoryBackend()
    result = _tool_get_drift_report(db, agent_id="ghost")
    assert result["agent_id"] == "ghost"
    assert result["baseline"] is None
```

- [ ] **Step 6.2: Verify failures**

```bash
pytest tests/unit/test_mcp_server.py::test_get_tool_stats_aggregates -v 2>&1 | tail -5
```

Expected: `ImportError`.

- [ ] **Step 6.3: Implement handlers**

Add to `ocw/mcp/server.py`:

```python
def _tool_get_tool_stats(db, agent_id: str | None, since: str | None) -> dict:
    from ocw.utils.time_parse import parse_since
    since_dt = parse_since(since) if since else None
    rows = db.get_tool_calls(agent_id, since_dt, None)
    return {"tools": rows, "count": len(rows)}


def _tool_get_drift_report(db, agent_id: str | None) -> dict:
    if agent_id:
        baseline = db.get_baseline(agent_id)
        latest_sessions = db.get_completed_sessions(agent_id, limit=1)
        latest = None
        if latest_sessions:
            s = latest_sessions[0]
            latest = {
                "session_id": s.session_id,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
                "tool_call_count": s.tool_call_count,
                "duration_seconds": s.duration_seconds,
            }
        return {
            "agent_id": agent_id,
            "baseline": {
                "sessions_sampled": baseline.sessions_sampled,
                "computed_at": baseline.computed_at.isoformat() if baseline.computed_at else None,
                "avg_input_tokens": baseline.avg_input_tokens,
                "stddev_input_tokens": baseline.stddev_input_tokens,
                "avg_output_tokens": baseline.avg_output_tokens,
                "stddev_output_tokens": baseline.stddev_output_tokens,
                "avg_session_duration_s": baseline.avg_session_duration_s,
                "avg_tool_call_count": baseline.avg_tool_call_count,
            } if baseline else None,
            "latest_session": latest,
        }
    # All agents with baselines
    agents_with_baselines = db.conn.execute(
        "SELECT DISTINCT agent_id FROM drift_baselines ORDER BY agent_id"
    ).fetchall()
    return {
        "agents": [_tool_get_drift_report(db, row[0]) for row in agents_with_baselines]
    }
```

Add FastMCP wrappers:

```python
@mcp.tool()
def get_tool_stats(
    agent_id: str | None = None,
    since: str | None = None,
) -> dict:
    """Tool call counts and average duration per tool."""
    if _ro_db is None:
        return _no_config()
    return _tool_get_tool_stats(_ro_db, agent_id, since)


@mcp.tool()
def get_drift_report(agent_id: str | None = None) -> dict:
    """Behavioral drift baseline vs latest session. Omit agent_id for all agents."""
    if _ro_db is None:
        return _no_config()
    return _tool_get_drift_report(_ro_db, agent_id)
```

- [ ] **Step 6.4: Run tests**

```bash
pytest tests/unit/test_mcp_server.py -k "tool_stats or drift_report" -v
```

Expected: all 4 PASS.

- [ ] **Step 6.5: Commit**

```bash
git add ocw/mcp/server.py tests/unit/test_mcp_server.py
git commit -m "feat(mcp): get_tool_stats and get_drift_report tools"
```

---

## Task 7: Write tool — acknowledge_alert

**Files:**
- Modify: `ocw/mcp/server.py`
- Modify: `tests/unit/test_mcp_server.py`

- [ ] **Step 7.1: Write failing tests**

Append to `tests/unit/test_mcp_server.py`:

```python
from ocw.mcp.server import _tool_acknowledge_alert


def test_acknowledge_alert_sets_flag():
    db = InMemoryBackend()
    alert = Alert(
        alert_id=new_uuid(),
        fired_at=utcnow(),
        type=AlertType.RETRY_LOOP,
        severity=Severity.WARNING,
        title="Retry loop",
        detail={},
        agent_id="a",
        session_id=None,
        span_id=None,
        acknowledged=False,
        suppressed=False,
    )
    db.insert_alert(alert)

    result = _tool_acknowledge_alert(db.conn, alert.alert_id)

    assert result == {"acknowledged": True, "alert_id": alert.alert_id}
    row = db.conn.execute(
        "SELECT acknowledged FROM alerts WHERE alert_id = $1", [alert.alert_id]
    ).fetchone()
    assert row[0] is True


def test_acknowledge_alert_unknown_id():
    db = InMemoryBackend()
    result = _tool_acknowledge_alert(db.conn, "nonexistent-id")
    assert "error" in result
```

- [ ] **Step 7.2: Verify failures**

```bash
pytest tests/unit/test_mcp_server.py::test_acknowledge_alert_sets_flag -v 2>&1 | tail -5
```

Expected: `ImportError`.

- [ ] **Step 7.3: Implement handler**

Add to `ocw/mcp/server.py`:

```python
def _tool_acknowledge_alert(conn, alert_id: str) -> dict:
    """Update acknowledged flag. conn may be read-write (tests) or short-lived write (prod)."""
    result = conn.execute(
        "SELECT alert_id FROM alerts WHERE alert_id = $1", [alert_id]
    ).fetchone()
    if result is None:
        return {"error": f"Alert {alert_id} not found"}
    conn.execute(
        "UPDATE alerts SET acknowledged = true WHERE alert_id = $1", [alert_id]
    )
    return {"acknowledged": True, "alert_id": alert_id}
```

Add FastMCP wrapper:

```python
@mcp.tool()
def acknowledge_alert(alert_id: str) -> dict:
    """Mark an alert as acknowledged. Does not suppress — alert remains in history."""
    if _config is None:
        return _no_config()
    from pathlib import Path
    import duckdb as _duckdb
    db_path = str(Path(_config.storage.path).expanduser())
    with _duckdb.connect(db_path) as write_conn:
        return _tool_acknowledge_alert(write_conn, alert_id)
```

- [ ] **Step 7.4: Run tests**

```bash
pytest tests/unit/test_mcp_server.py -k "acknowledge" -v
```

Expected: both PASS.

- [ ] **Step 7.5: Commit**

```bash
git add ocw/mcp/server.py tests/unit/test_mcp_server.py
git commit -m "feat(mcp): acknowledge_alert write tool"
```

---

## Task 8: Write tool — setup_project

**Files:**
- Modify: `ocw/mcp/server.py`
- Modify: `tests/unit/test_mcp_server.py`

- [ ] **Step 8.1: Write failing tests**

Append to `tests/unit/test_mcp_server.py`:

```python
import json
from pathlib import Path
from ocw.mcp.server import _tool_setup_project


def test_setup_project_writes_settings(tmp_path):
    config = _make_config()
    config_path = tmp_path / "ocw.toml"
    config_path.write_text("")  # dummy

    result = _tool_setup_project(
        config=config,
        config_path=str(config_path),
        agent_id="my-project",
        project_path=str(tmp_path),
    )

    assert result["agent_id"] == "my-project"
    settings_file = tmp_path / ".claude" / "settings.json"
    assert settings_file.exists()
    data = json.loads(settings_file.read_text())
    assert data["env"]["OTEL_RESOURCE_ATTRIBUTES"] == "service.name=my-project"


def test_setup_project_warns_no_global_otlp(tmp_path, monkeypatch):
    # Simulate no global ~/.claude/settings.json
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    config = _make_config()
    config_path = tmp_path / "ocw.toml"
    config_path.write_text("")

    result = _tool_setup_project(
        config=config,
        config_path=str(config_path),
        agent_id="proj",
        project_path=str(tmp_path),
    )

    assert "warning" in result


def test_setup_project_no_config():
    result = _tool_setup_project(
        config=None,
        config_path=None,
        agent_id=None,
        project_path=None,
    )
    assert "error" in result
```

- [ ] **Step 8.2: Verify failures**

```bash
pytest tests/unit/test_mcp_server.py::test_setup_project_writes_settings -v 2>&1 | tail -5
```

Expected: `ImportError`.

- [ ] **Step 8.3: Implement handler**

Add to `ocw/mcp/server.py`:

```python
def _tool_setup_project(
    config, config_path: str | None, agent_id: str | None, project_path: str | None
) -> dict:
    if config is None or config_path is None:
        return _no_config()
    import json
    import subprocess
    from pathlib import Path
    from ocw.core.config import write_config, AgentConfig

    # Derive agent_id if not provided
    if not agent_id:
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=3,
                cwd=project_path or ".",
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                name = url.rstrip("/").split("/")[-1].split(":")[-1]
                name = name.removesuffix(".git").lower()
                agent_id = f"claude-code-{name}" if name else None
        except Exception:
            pass
        if not agent_id:
            cwd = Path(project_path) if project_path else Path.cwd()
            agent_id = f"claude-code-{cwd.name.lower()}"

    # Write project-level .claude/settings.json
    proj_dir = Path(project_path) if project_path else Path.cwd()
    claude_dir = proj_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"

    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    env = existing.get("env", {})
    env["OTEL_RESOURCE_ATTRIBUTES"] = f"service.name={agent_id}"
    existing["env"] = env
    settings_path.write_text(json.dumps(existing, indent=2) + "\n")

    # Add agent entry to OCW config
    if agent_id not in config.agents:
        config.agents[agent_id] = AgentConfig()
        write_config(config, Path(config_path))

    # Warn if global OTLP endpoint not configured
    global_settings = Path.home() / ".claude" / "settings.json"
    warning = None
    if global_settings.exists():
        try:
            gs = json.loads(global_settings.read_text())
            if "OTEL_EXPORTER_OTLP_ENDPOINT" not in gs.get("env", {}):
                warning = "Global OTLP endpoint not configured. Run 'ocw onboard --claude-code' to finish setup."
        except Exception:
            warning = "Could not read ~/.claude/settings.json."
    else:
        warning = "~/.claude/settings.json not found. Run 'ocw onboard --claude-code' to configure the global OTLP endpoint."

    result = {
        "agent_id": agent_id,
        "settings_path": str(settings_path),
    }
    if warning:
        result["warning"] = warning
    return result
```

Add FastMCP wrapper:

```python
@mcp.tool()
def setup_project(agent_id: str | None = None, project_path: str | None = None) -> dict:
    """Configure this project to send telemetry to OCW. Writes .claude/settings.json."""
    from ocw.core.config import find_config_file
    cp = find_config_file()
    return _tool_setup_project(
        config=_config,
        config_path=str(cp) if cp else None,
        agent_id=agent_id,
        project_path=project_path,
    )
```

- [ ] **Step 8.4: Run tests**

```bash
pytest tests/unit/test_mcp_server.py -k "setup_project" -v
```

Expected: all 3 PASS.

- [ ] **Step 8.5: Commit**

```bash
git add ocw/mcp/server.py tests/unit/test_mcp_server.py
git commit -m "feat(mcp): setup_project write tool"
```

---

## Task 9: No-config sentinel + full test suite pass

**Files:**
- Modify: `tests/unit/test_mcp_server.py`

- [ ] **Step 9.1: Run full test suite**

```bash
pytest tests/unit/test_mcp_server.py -v
```

Expected: all tests PASS. Fix any failures before continuing.

- [ ] **Step 9.2: Run the broader unit suite to check for regressions**

```bash
pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Step 9.3: Commit if any fixes were needed**

```bash
git add -p
git commit -m "fix(mcp): resolve test failures from full suite run"
```

---

## Task 10: CI update

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 10.1: Update the install step**

In `.github/workflows/ci.yml`, change:

```yaml
      - name: Install dependencies
        run: pip install -e ".[dev]"
```

to:

```yaml
      - name: Install dependencies
        run: pip install -e ".[dev,mcp]"
```

- [ ] **Step 10.2: Verify locally**

```bash
pip install -e ".[dev,mcp]"
pytest tests/unit/ tests/synthetic/ tests/agents/ tests/integration/ -q
```

Expected: all pass.

- [ ] **Step 10.3: Final commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: install fastmcp optional dep for test runs"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Direct library mode, no `ocw serve` dependency | Task 1 cmd_mcp.py (read-only duckdb.connect) |
| `fastmcp` optional dep | Task 1 pyproject.toml |
| `ocw mcp` CLI command | Task 1 cmd_mcp.py + main.py |
| `get_status` | Task 2 |
| `get_budget_headroom` | Task 2 |
| `list_agents` (historical, lifetime cost via JOIN) | Task 3 |
| `list_active_sessions` (one row per session) | Task 3 |
| `get_cost_summary` | Task 4 |
| `list_alerts` | Task 4 |
| `list_traces` | Task 5 |
| `get_trace` | Task 5 |
| `get_tool_stats` | Task 6 |
| `get_drift_report` | Task 6 |
| `acknowledge_alert` (short-lived write conn) | Task 7 |
| `setup_project` (cwd assumption documented, project_path override) | Task 8 |
| No-config sentinel on every tool | All tasks (_no_config() guard) |
| CI install updated | Task 10 |
| `InMemoryBackend` for tests | All test tasks |

**No placeholders found.**

**Type consistency:** `_tool_get_cost_summary`, `_tool_list_alerts`, `_tool_list_traces`, `_tool_get_trace`, `_tool_get_tool_stats`, `_tool_get_drift_report` all take `db` (a `_ReadOnlyDB` or `InMemoryBackend`). `_tool_get_status`, `_tool_list_agents`, `_tool_list_active_sessions` take `conn` (raw duckdb connection). `_tool_acknowledge_alert` takes `conn` (read-write). `_tool_setup_project` takes `config, config_path, agent_id, project_path`. All consistent across tasks.
