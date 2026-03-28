# Task 04 — Alert Engine
**Depends on:** Task 00 (foundation), Task 01 (StorageBackend interface).
**Parallel with:** Tasks 02, 03, 05–11.
**Estimated scope:** Medium.

---

## What this task covers

- `ocw/core/alerts.py` — all alert rule evaluation and dispatch
- All 6 output channels: stdout, file, ntfy, webhook, Discord, Telegram
- Alert cooldown/suppression
- `ocw alerts` CLI command

---

## Alert types

| Type constant | When it fires |
|---|---|
| `COST_BUDGET_DAILY` | Daily spend for an agent exceeds `budget.daily_usd` |
| `COST_BUDGET_SESSION` | Session cost exceeds `budget.session_usd` |
| `SENSITIVE_ACTION` | `span.tool_name` matches an entry in `sensitive_actions` |
| `RETRY_LOOP` | Same tool called ≥ 4 times in the last 6 spans of the same session |
| `TOKEN_ANOMALY` | Session token usage > baseline mean + N×stddev (fired at session end, see Task 05) |
| `SESSION_DURATION` | Session wall time > configurable threshold |
| `SCHEMA_VIOLATION` | Tool output fails JSON Schema (fired by Task 06) |
| `DRIFT_DETECTED` | Session drift score exceeds threshold (fired by Task 05) |
| `FAILURE_RATE` | error_count / total span count > 20% in a rolling window |
| `NETWORK_EGRESS_BLOCKED` | NemoClaw: agent tried to reach an unlisted host |
| `FILESYSTEM_ACCESS_DENIED` | NemoClaw: agent tried to write outside sandbox |
| `SYSCALL_DENIED` | NemoClaw: process attempted privilege escalation |
| `INFERENCE_REROUTED` | NemoClaw: inference endpoint changed from expected |

---

## Deliverables

### `ocw/core/alerts.py`

```python
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ocw.core.models import Alert, AlertType, Severity
from ocw.core.config import OcwConfig, AlertChannelConfig
from ocw.utils.ids import new_uuid
from ocw.utils.time_parse import utcnow

if TYPE_CHECKING:
    from ocw.core.db import StorageBackend
    from ocw.core.models import NormalizedSpan, SessionRecord

logger = logging.getLogger(__name__)


# ── Cooldown tracker ───────────────────────────────────────────────────────

class CooldownTracker:
    """
    Prevents alert storms by suppressing repeat alerts of the same type
    for the same agent within the cooldown window.
    Stored in-memory — resets when the process restarts.
    """

    def __init__(self, cooldown_seconds: int = 60):
        self.cooldown_seconds = cooldown_seconds
        self._last_fired: dict[tuple[str, str], datetime] = {}

    def is_suppressed(self, agent_id: str | None, alert_type: AlertType) -> bool:
        key = (agent_id or "", alert_type.value)
        last = self._last_fired.get(key)
        if last is None:
            return False
        return (utcnow() - last).total_seconds() < self.cooldown_seconds

    def record(self, agent_id: str | None, alert_type: AlertType) -> None:
        key = (agent_id or "", alert_type.value)
        self._last_fired[key] = utcnow()


# ── Alert engine ───────────────────────────────────────────────────────────

class AlertEngine:
    """
    Post-ingest hook. Evaluates all alert rules after each span is written.
    Called by IngestPipeline.process() after the span is in the DB.
    """

    def __init__(self, db: StorageBackend, config: OcwConfig):
        self.db = db
        self.config = config
        self.cooldown = CooldownTracker(config.alerts.cooldown_seconds)
        self.dispatcher = AlertDispatcher(config)

    def evaluate(self, span: NormalizedSpan) -> None:
        """
        Evaluate all per-span alert rules against this span.
        Call this after every span ingest.
        """
        self._check_sensitive_action(span)
        self._check_retry_loop(span)
        self._check_failure_rate(span)
        # NemoClaw sandbox events (only if span has sandbox attributes)
        self._check_sandbox_events(span)

    def evaluate_session_end(self, session: SessionRecord) -> None:
        """
        Evaluate all per-session alert rules. Call this when a session ends.
        Note: DRIFT_DETECTED and TOKEN_ANOMALY are fired from Task 05 (drift.py),
        not here. This method handles only cost budgets and session duration.
        """
        self._check_cost_budgets(session)
        self._check_session_duration(session)

    def fire(self, alert_type: AlertType, span_or_session, detail: dict,
             severity: Severity | None = None) -> None:
        """
        External entry point. Used by SchemaValidator and DriftDetector
        to fire alerts they detect.
        """
        ...

    def _check_sensitive_action(self, span: NormalizedSpan) -> None:
        """
        If span.tool_name matches any entry in the agent's sensitive_actions list,
        fire a SENSITIVE_ACTION alert with the configured severity.
        """
        ...

    def _check_retry_loop(self, span: NormalizedSpan) -> None:
        """
        Fetch the last 6 spans for this session.
        If the same tool_name appears 4+ times among them, fire RETRY_LOOP.
        """
        ...

    def _check_cost_budgets(self, session: SessionRecord) -> None:
        """
        Check daily and session cost thresholds against the agent's budget config.
        Fire COST_BUDGET_DAILY or COST_BUDGET_SESSION if exceeded.
        """
        ...

    def _check_session_duration(self, session: SessionRecord) -> None:
        """
        If session.duration_seconds exceeds a configurable threshold, fire
        SESSION_DURATION. Default threshold: 3600 seconds (1 hour).
        """
        ...

    def _check_failure_rate(self, span: NormalizedSpan) -> None:
        """
        In a rolling window of the last 20 spans for this session,
        if error_count / total > 0.20, fire FAILURE_RATE.
        Avoid firing on every single error span — check only every 5th error.
        """
        ...

    def _check_sandbox_events(self, span: NormalizedSpan) -> None:
        """
        Check for NemoClaw/OpenShell sandbox event attributes.
        ocw.sandbox.event values: network_blocked, fs_denied, syscall_denied,
        inference_rerouted → map to corresponding AlertType.
        No-op if span has no sandbox event attributes.
        """
        ...

    def _fire(self, alert: Alert) -> None:
        """
        Internal: persist alert to DB and dispatch to channels.
        Respects cooldown — suppressed alerts are persisted but not dispatched.
        """
        if self.cooldown.is_suppressed(alert.agent_id, alert.type):
            alert.suppressed = True
            self.db.insert_alert(alert)
            return
        self.db.insert_alert(alert)
        self.cooldown.record(alert.agent_id, alert.type)
        self.dispatcher.dispatch(alert)


# ── Alert dispatcher ───────────────────────────────────────────────────────

class AlertDispatcher:
    """Routes a fired alert to all configured output channels."""

    def __init__(self, config: OcwConfig):
        self.channels = [
            _build_channel(ch_config, config.alerts.include_captured_content)
            for ch_config in config.alerts.channels
        ]

    def dispatch(self, alert: Alert) -> None:
        for channel in self.channels:
            try:
                channel.send(alert)
            except Exception as exc:
                logger.warning("Alert channel %s failed: %s", channel, exc)


def _build_channel(config: AlertChannelConfig, include_captured_content: bool):
    """Factory: return the correct channel instance for the config type."""
    match config.type:
        case "stdout":   return StdoutChannel()
        case "file":     return FileChannel(config.path, include_captured_content)
        case "ntfy":     return NtfyChannel(config, include_captured_content)
        case "webhook":  return WebhookChannel(config, include_captured_content)
        case "discord":  return DiscordChannel(config, include_captured_content)
        case "telegram": return TelegramChannel(config, include_captured_content)
        case _: raise ValueError(f"Unknown alert channel type: {config.type!r}")


# ── Channel implementations ────────────────────────────────────────────────

class StdoutChannel:
    """
    Always active. Prints to stdout using Rich.
    Format: [HH:MM:SS]  ⚠ CRITICAL  sensitive_action  my-agent  send_email called

    Colour: CRITICAL=red, WARNING=yellow, INFO=blue
    Icon: CRITICAL=⚠, WARNING=⚠, INFO=ℹ
    """
    def send(self, alert: Alert) -> None: ...


class FileChannel:
    """
    Appends a JSON line to the configured log file path.
    One JSON object per line. Always includes full detail.
    Creates parent directories if they don't exist.
    """
    def __init__(self, path: str, include_captured_content: bool): ...
    def send(self, alert: Alert) -> None: ...


class NtfyChannel:
    """
    Sends a push notification via ntfy.sh or self-hosted ntfy.
    POST https://<server>/<topic>

    Payload: title = alert.title, body = formatted detail summary
    Headers: Authorization: Bearer <token> (if token is set)
    Only sends alerts at or above min_severity.

    Content stripping: remove captured content fields from body if
    include_captured_content is False.
    """
    def __init__(self, config: AlertChannelConfig, include_captured_content: bool): ...
    def send(self, alert: Alert) -> None: ...


class WebhookChannel:
    """
    HTTP POST to configured URL with JSON payload.
    Uses httpx. Timeout: 5 seconds. Do not retry on failure — just log.

    Payload: full Alert dict with captured content stripped if configured.
    """
    def __init__(self, config: AlertChannelConfig, include_captured_content: bool): ...
    def send(self, alert: Alert) -> None: ...


class DiscordChannel:
    """
    POST to Discord webhook URL.
    Formats alert as a Discord embed with colour matching severity.
    Strips captured content if configured.
    """
    def __init__(self, config: AlertChannelConfig, include_captured_content: bool): ...
    def send(self, alert: Alert) -> None: ...


class TelegramChannel:
    """
    POST to Telegram Bot API sendMessage endpoint.
    Uses Markdown formatting for the message.
    Strips captured content if configured.
    """
    def __init__(self, config: AlertChannelConfig, include_captured_content: bool): ...
    def send(self, alert: Alert) -> None: ...
```

---

### Content stripping rule

Before dispatching to any external channel (ntfy, webhook, Discord, Telegram), strip
these keys from `alert.detail` if `include_captured_content` is `False`:

```python
SENSITIVE_DETAIL_KEYS = {
    "prompt_content", "completion_content", "tool_input", "tool_output"
}
```

Stdout and file channels always receive the full detail.

---

### `ocw/cli/cmd_alerts.py`

```python
@click.command("alerts")
@click.option("--agent", default=None)
@click.option("--since", default="24h")
@click.option("--severity", type=click.Choice(["critical", "warning", "info"]), default=None)
@click.option("--type", "alert_type", default=None)
@click.option("--unread", is_flag=True)
@click.option("--json", "output_json", is_flag=True)
@click.pass_context
def cmd_alerts(ctx, agent, since, severity, alert_type, unread, output_json):
    """Show alert history."""
    ...
```

Human output columns: TIME | SEVERITY | TYPE | AGENT | DETAIL (truncated to 60 chars)
Header line: "Alerts — last 24h   (N total: X critical, Y warning)"

---

## Tests to write

**`tests/unit/test_alerts.py`:**

```python
def test_cooldown_suppresses_repeat_alert_within_window()
def test_cooldown_allows_alert_after_window_expires()
def test_cooldown_tracks_per_agent_independently()
    # Agent A firing should not suppress Agent B's alerts of the same type
```

**`tests/synthetic/test_alert_rules.py`:**

```python
def test_sensitive_action_fires_on_matching_tool()
def test_sensitive_action_does_not_fire_on_non_matching_tool()
def test_sensitive_action_uses_configured_severity()
def test_retry_loop_fires_at_4_calls_not_3()
    # Insert 3 spans with same tool → no alert
    # Insert 4th span with same tool → RETRY_LOOP fires
def test_cost_budget_daily_fires_when_exceeded()
def test_cost_budget_session_fires_when_exceeded()
def test_content_stripped_from_webhook_payload()
def test_content_not_stripped_from_stdout_payload()
def test_suppressed_alert_persisted_to_db()
def test_suppressed_alert_not_dispatched_to_channels()
def test_sandbox_network_blocked_fires_correct_alert_type()
```
