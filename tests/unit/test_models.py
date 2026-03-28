from datetime import datetime, timezone, timedelta

from ocw.core.models import (
    SessionRecord, Severity, AlertType, SpanStatus, SpanKind,
)


class TestSessionRecord:
    def test_duration_seconds_with_both_times(self):
        started = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        ended = datetime(2026, 3, 28, 12, 5, 30, tzinfo=timezone.utc)
        session = SessionRecord(
            session_id="s1",
            agent_id="a1",
            started_at=started,
            ended_at=ended,
        )
        assert session.duration_seconds == 330.0

    def test_duration_seconds_none_without_end_time(self):
        session = SessionRecord(
            session_id="s1",
            agent_id="a1",
            started_at=datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert session.duration_seconds is None

    def test_default_status_is_active(self):
        session = SessionRecord(
            session_id="s1",
            agent_id="a1",
            started_at=datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert session.status == "active"


class TestEnums:
    def test_severity_values(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"

    def test_alert_type_values(self):
        assert AlertType.COST_BUDGET_DAILY.value == "cost_budget_daily"
        assert AlertType.RETRY_LOOP.value == "retry_loop"
        assert AlertType.DRIFT_DETECTED.value == "drift_detected"

    def test_span_status_values(self):
        assert SpanStatus.OK.value == "ok"
        assert SpanStatus.ERROR.value == "error"
        assert SpanStatus.UNSET.value == "unset"

    def test_span_kind_values(self):
        assert SpanKind.CLIENT.value == "client"
        assert SpanKind.INTERNAL.value == "internal"
        assert SpanKind.SERVER.value == "server"

    def test_severity_is_string(self):
        assert isinstance(Severity.CRITICAL, str)
        assert Severity.CRITICAL == "critical"

    def test_alert_type_is_string(self):
        assert isinstance(AlertType.RETRY_LOOP, str)
        assert AlertType.RETRY_LOOP == "retry_loop"
