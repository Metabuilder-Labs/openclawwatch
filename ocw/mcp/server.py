"""OCW MCP server — exposes observability data to Claude Code via stdio."""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("ocw")

# Module-level state initialised by init() or cmd_mcp.py
_ro_conn = None   # duckdb read-only connection
_config = None    # OcwConfig
_ro_db = None     # _ReadOnlyDB wrapping _ro_conn


def init(ro_conn, config) -> None:
    """Inject DB connection and config. Called by cmd_mcp.py and tests."""
    global _ro_conn, _config, _ro_db
    _ro_conn, _config = ro_conn, config
    _ro_db = _ReadOnlyDB(ro_conn) if ro_conn is not None else None


def _no_config() -> dict:
    return {"error": "No OCW config found. Run 'ocw onboard --claude-code' to set up."}


class _ReadOnlyDB:
    """Wraps a read-only duckdb connection to satisfy StorageBackend protocol methods."""
    def __init__(self, conn):
        self.conn = conn

    def get_cost_summary(self, filters):
        from ocw.core.db import DuckDBBackend
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


# ---------------------------------------------------------------------------
# Handler functions — called by @mcp.tool() wrappers and directly in tests
# ---------------------------------------------------------------------------

def _tool_get_status(conn, config, agent_id: str | None = None) -> dict:
    if config is None:
        return _no_config()
    from ocw.utils.time_parse import utcnow

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
        return results[0] if results else {
            "agent_id": agent_id,
            "session_id": None,
            "status": "idle",
            "input_tokens": 0,
            "output_tokens": 0,
            "tool_call_count": 0,
            "error_count": 0,
            "cost_today_usd": 0.0,
            "active_alerts": 0,
        }
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


def _tool_open_dashboard(config) -> dict:
    """Start ocw serve in the background if not running, return the dashboard URL."""
    if config is None:
        return _no_config()
    import socket
    import subprocess
    import sys
    import time

    host = config.api.host
    port = config.api.port
    url = f"http://{host}:{port}/ui"

    # Check if something is already listening on the port
    already_running = False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            already_running = True
        except (ConnectionRefusedError, OSError):
            pass

    if already_running:
        return {"url": url, "started": False, "message": "ocw serve is already running."}

    # Spawn ocw serve detached from this process
    ocw_bin = sys.argv[0] if sys.argv[0].endswith("ocw") else "ocw"
    try:
        subprocess.Popen(
            [ocw_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        return {"error": f"Could not find '{ocw_bin}' on PATH. Run 'ocw serve' manually."}

    # Wait up to 5 seconds for the port to open
    for _ in range(10):
        time.sleep(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return {"url": url, "started": True, "message": "Dashboard started."}
            except (ConnectionRefusedError, OSError):
                pass

    return {
        "url": url,
        "started": True,
        "message": "Server launched but not yet ready — try opening the URL in a moment.",
    }


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


@mcp.tool()
def open_dashboard() -> dict:
    """Open the OCW web dashboard. Starts ocw serve in the background if not already running."""
    return _tool_open_dashboard(_config)
