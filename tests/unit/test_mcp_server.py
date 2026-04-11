"""Unit tests for OCW MCP server tool handlers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from ocw.core.db import InMemoryBackend
from ocw.core.config import OcwConfig, AgentConfig, BudgetConfig, DefaultsConfig
from ocw.core.models import AlertType, Severity, Alert, DriftBaseline, AgentRecord
from ocw.utils.time_parse import utcnow
from ocw.utils.ids import new_uuid
from tests.factories import make_session, make_llm_span, make_tool_span

from ocw.mcp.server import (
    _tool_get_status,
    _tool_get_budget_headroom,
    _tool_list_agents,
    _tool_list_active_sessions,
    _tool_get_cost_summary,
    _tool_list_alerts,
    _tool_list_traces,
    _tool_get_trace,
    _tool_get_tool_stats,
    _tool_get_drift_report,
    _tool_acknowledge_alert,
    _tool_setup_project,
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
    db = InMemoryBackend()
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


# --- list_agents ---

def test_list_agents_returns_all_known():
    db = InMemoryBackend()
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


# --- list_active_sessions ---

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


# --- get_cost_summary ---

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


# --- list_alerts ---

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


# --- list_traces ---

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


# --- get_trace ---

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


# --- get_tool_stats ---

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


# --- get_drift_report ---

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


# --- acknowledge_alert ---

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


# --- setup_project ---

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
    # Simulate no global ~/.claude/settings.json by pointing home() to a fresh tmp dir
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake_home")
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


# --- open_dashboard ---

from unittest.mock import patch, MagicMock
from ocw.mcp.server import _tool_open_dashboard


def test_open_dashboard_already_running():
    config = _make_config()

    mock_sock = MagicMock()
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    mock_sock.connect = MagicMock()  # connect succeeds = port is bound

    with patch("socket.socket", return_value=mock_sock):
        result = _tool_open_dashboard(config)

    assert result["started"] is False
    assert "7391" in result["url"]
    assert "/ui" in result["url"]


def test_open_dashboard_starts_server():
    config = _make_config()

    call_count = 0

    def fake_socket_factory(*args, **kwargs):
        nonlocal call_count
        s = MagicMock()
        s.__enter__ = lambda self: self
        s.__exit__ = MagicMock(return_value=False)
        call_count += 1
        if call_count == 1:
            # First call: port not bound
            s.connect = MagicMock(side_effect=ConnectionRefusedError)
        else:
            # Subsequent calls (polling): port is bound
            s.connect = MagicMock()
        return s

    with patch("socket.socket", side_effect=fake_socket_factory), \
         patch("subprocess.Popen") as mock_popen, \
         patch("time.sleep"):
        result = _tool_open_dashboard(config)

    mock_popen.assert_called_once()
    assert result["started"] is True
    assert "/ui" in result["url"]


def test_open_dashboard_no_config():
    result = _tool_open_dashboard(None)
    assert "error" in result
