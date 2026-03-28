import tempfile
from pathlib import Path

import pytest

from ocw.core.config import (
    load_config, _parse, _serialise, OcwConfig, AgentConfig, BudgetConfig,
    SensitiveAction, SecurityConfig, CaptureConfig, StorageConfig,
)


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.version == "1"
        assert config.storage.path == "~/.ocw/telemetry.duckdb"
        assert config.security.ingest_secret == ""

    def test_loads_from_file(self, tmp_path):
        toml_content = b'version = "1"\n\n[storage]\npath = "/tmp/test.duckdb"\n'
        config_file = tmp_path / "ocw.toml"
        config_file.write_bytes(toml_content)
        config = load_config(str(config_file))
        assert config.storage.path == "/tmp/test.duckdb"

    def test_raises_on_missing_override(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("/nonexistent/path/ocw.toml")

    def test_binary_mode_required(self, tmp_path):
        # Verify the file is opened in binary mode by testing a valid TOML
        config_file = tmp_path / "ocw.toml"
        config_file.write_bytes(b'version = "2"\n')
        config = load_config(str(config_file))
        assert config.version == "2"


class TestParse:
    def test_empty_dict_returns_defaults(self):
        config = _parse({})
        assert config.version == "1"
        assert config.agents == {}
        assert config.capture.prompts is False

    def test_agents_parsed(self):
        raw = {
            "agents": {
                "my-agent": {
                    "description": "Test agent",
                    "budget": {"daily_usd": 5.0, "session_usd": 1.0},
                    "sensitive_actions": [
                        {"name": "send_email", "severity": "critical"}
                    ],
                }
            }
        }
        config = _parse(raw)
        assert "my-agent" in config.agents
        agent = config.agents["my-agent"]
        assert agent.description == "Test agent"
        assert agent.budget.daily_usd == 5.0
        assert agent.budget.session_usd == 1.0
        assert len(agent.sensitive_actions) == 1
        assert agent.sensitive_actions[0].name == "send_email"
        assert agent.sensitive_actions[0].severity == "critical"

    def test_security_parsed(self):
        raw = {"security": {"ingest_secret": "my-secret", "max_attribute_bytes": 1024}}
        config = _parse(raw)
        assert config.security.ingest_secret == "my-secret"
        assert config.security.max_attribute_bytes == 1024

    def test_capture_parsed(self):
        raw = {"capture": {"prompts": True, "tool_outputs": True}}
        config = _parse(raw)
        assert config.capture.prompts is True
        assert config.capture.completions is False
        assert config.capture.tool_outputs is True

    def test_alerts_channels_parsed(self):
        raw = {
            "alerts": {
                "cooldown_seconds": 120,
                "channels": [
                    {"type": "stdout"},
                    {"type": "ntfy", "topic": "my-topic"},
                ],
            }
        }
        config = _parse(raw)
        assert config.alerts.cooldown_seconds == 120
        assert len(config.alerts.channels) == 2
        assert config.alerts.channels[1].topic == "my-topic"

    def test_default_alert_channel_is_stdout(self):
        config = _parse({})
        assert len(config.alerts.channels) == 1
        assert config.alerts.channels[0].type == "stdout"

    def test_api_auth_parsed(self):
        raw = {"api": {"port": 8080, "auth": {"enabled": True, "api_key": "key123"}}}
        config = _parse(raw)
        assert config.api.port == 8080
        assert config.api.auth.enabled is True
        assert config.api.auth.api_key == "key123"

    def test_drift_config_parsed(self):
        raw = {
            "agents": {
                "a1": {"drift": {"enabled": False, "token_threshold": 3.0}}
            }
        }
        config = _parse(raw)
        assert config.agents["a1"].drift.enabled is False
        assert config.agents["a1"].drift.token_threshold == 3.0
        assert config.agents["a1"].drift.baseline_sessions == 10  # default


class TestSerialise:
    def test_roundtrip(self):
        config = OcwConfig(
            version="1",
            agents={
                "test": AgentConfig(
                    description="A test agent",
                    budget=BudgetConfig(daily_usd=5.0),
                    sensitive_actions=[SensitiveAction(name="rm_rf", severity="critical")],
                )
            },
            security=SecurityConfig(ingest_secret="secret123"),
            capture=CaptureConfig(prompts=True),
        )
        serialised = _serialise(config)
        restored = _parse(serialised)

        assert restored.version == "1"
        assert restored.agents["test"].description == "A test agent"
        assert restored.agents["test"].budget.daily_usd == 5.0
        assert restored.agents["test"].sensitive_actions[0].name == "rm_rf"
        assert restored.security.ingest_secret == "secret123"
        assert restored.capture.prompts is True
