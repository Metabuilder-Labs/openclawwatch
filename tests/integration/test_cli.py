"""Integration tests for CLI commands using CliRunner."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ocw.cli.main import cli
from ocw.core.config import AgentConfig, BudgetConfig, OcwConfig
from ocw.core.db import InMemoryBackend
from ocw.core.models import (
    AgentRecord,
    Alert,
    AlertType,
    Severity,
)
from ocw.utils.ids import new_uuid
from ocw.utils.time_parse import utcnow
from tests.factories import make_llm_span, make_session


@pytest.fixture
def db():
    backend = InMemoryBackend()
    yield backend
    backend.close()


@pytest.fixture
def config():
    return OcwConfig(
        version="1",
        agents={"test-agent": AgentConfig(budget=BudgetConfig(daily_usd=5.0))},
    )


@pytest.fixture
def runner():
    return CliRunner()


def _invoke(runner, db, config, args):
    """Invoke CLI with patched db and config."""
    with patch("ocw.cli.main.load_config", return_value=config), \
         patch("ocw.cli.main.open_db", return_value=db):
        return runner.invoke(cli, args)


def _seed_agent_and_session(db, agent_id="test-agent"):
    """Insert an agent and session into the DB for tests that need them."""
    now = utcnow()
    agent = AgentRecord(
        agent_id=agent_id, first_seen=now, last_seen=now,
    )
    db.upsert_agent(agent)
    session = make_session(agent_id=agent_id, status="completed")
    db.upsert_session(session)
    return session


def _seed_alert(db, agent_id="test-agent", acknowledged=False, suppressed=False):
    """Insert an alert into the DB."""
    alert = Alert(
        alert_id=new_uuid(),
        fired_at=utcnow(),
        type=AlertType.COST_BUDGET_DAILY,
        severity=Severity.WARNING,
        title="Daily budget exceeded",
        detail={"message": "Agent exceeded $5.00 daily budget"},
        agent_id=agent_id,
        acknowledged=acknowledged,
        suppressed=suppressed,
    )
    db.insert_alert(alert)
    return alert


# -- status tests --

def test_status_exits_0_when_no_alerts(runner, db, config):
    _seed_agent_and_session(db)
    result = _invoke(runner, db, config, ["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["has_active_alerts"] is False


def test_status_exits_1_when_active_alerts(runner, db, config):
    _seed_agent_and_session(db)
    _seed_alert(db, acknowledged=False)
    result = _invoke(runner, db, config, ["status", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["has_active_alerts"] is True


# -- traces tests --

def test_traces_json_output_is_valid_json(runner, db, config):
    _seed_agent_and_session(db)
    span = make_llm_span(agent_id="test-agent")
    db.upsert_agent(AgentRecord(
        agent_id="test-agent", first_seen=utcnow(), last_seen=utcnow(),
    ))
    db.insert_span(span)

    result = _invoke(runner, db, config, ["traces", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)


def test_trace_id_shows_span_waterfall(runner, db, config):
    span = make_llm_span(agent_id="test-agent")
    db.upsert_agent(AgentRecord(
        agent_id="test-agent", first_seen=utcnow(), last_seen=utcnow(),
    ))
    session = make_session(agent_id="test-agent")
    db.upsert_session(session)
    db.insert_span(span)

    result = _invoke(runner, db, config, ["trace", span.trace_id, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) >= 1
    assert data[0]["span_id"] == span.span_id


# -- export tests --

def test_export_openevals_format_is_message_list(runner, db, config):
    span = make_llm_span(
        agent_id="test-agent",
        extra_attributes={
            "gen_ai.prompt.content": "Hello",
            "gen_ai.completion.content": "Hi there",
        },
    )
    db.upsert_agent(AgentRecord(
        agent_id="test-agent", first_seen=utcnow(), last_seen=utcnow(),
    ))
    session = make_session(agent_id="test-agent")
    db.upsert_session(session)
    db.insert_span(span)

    result = _invoke(runner, db, config, ["export", "--format", "openevals", "--since", "1h"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    if data:
        assert "messages" in data[0]
        assert "trace_id" in data[0]


# -- doctor tests --

def test_doctor_exits_0_when_config_is_clean(runner, db, config, tmp_path):
    config_file = tmp_path / "ocw.toml"
    config_file.write_text('version = "1"\n')
    # Set DB path to a writable temp location
    config.storage.path = str(tmp_path / "test.duckdb")
    # Set ingest secret so no warning fires
    config.security.ingest_secret = "test-secret"
    # Disable drift so no "insufficient sessions" warning fires
    config.agents["test-agent"].drift.enabled = False
    with patch("ocw.cli.cmd_doctor.find_config_file", return_value=config_file):
        result = _invoke(runner, db, config, ["doctor", "--json"])
    assert result.exit_code == 0


def test_doctor_exits_1_when_warnings_present(runner, db, config, tmp_path):
    # No ingest secret => warning
    config.security.ingest_secret = ""
    config.storage.path = str(tmp_path / "test.duckdb")
    config.agents["test-agent"].drift.enabled = False
    config_file = tmp_path / "ocw.toml"
    config_file.write_text('version = "1"\n')
    with patch("ocw.cli.cmd_doctor.find_config_file", return_value=config_file):
        result = _invoke(runner, db, config, ["doctor", "--json"])
    assert result.exit_code == 1
    checks = json.loads(result.output)
    warnings = [c for c in checks if c["level"] == "warning"]
    assert len(warnings) > 0


def test_doctor_exits_2_when_errors_present(runner, db, config):
    # No config file found => error
    with patch("ocw.cli.cmd_doctor.find_config_file", return_value=None):
        result = _invoke(runner, db, config, ["doctor", "--json"])
    assert result.exit_code == 2


def test_doctor_warns_on_schema_without_capture(runner, db, config, tmp_path):
    config.agents["test-agent"] = AgentConfig(output_schema="schema.json")
    config.capture.tool_outputs = False
    config_file = tmp_path / "ocw.toml"
    config_file.write_text('version = "1"\n')
    with patch("ocw.cli.cmd_doctor.find_config_file", return_value=config_file):
        result = _invoke(runner, db, config, ["doctor", "--json"])
    checks = json.loads(result.output)
    schema_checks = [c for c in checks if c["name"] == "Schema vs capture"]
    assert any(c["level"] == "warning" for c in schema_checks)


# -- since flag parsing --

def test_since_flag_parses_all_formats(runner, db, config):
    _seed_agent_and_session(db)
    for since_val in ["30m", "1h", "7d", "2026-03-01"]:
        result = _invoke(runner, db, config, ["traces", "--since", since_val, "--json"])
        assert result.exit_code == 0, f"Failed for --since {since_val}: {result.output}"
