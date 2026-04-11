"""Unit tests for the Claude Code log-to-span converter."""
from __future__ import annotations

import time

import pytest

from ocw.api.routes.logs import (
    _api_error_to_span,
    _api_request_to_span,
    _span_id_from_prompt,
    _tool_decision_to_span,
    _tool_result_to_span,
    _trace_id_from_session,
    _user_prompt_to_span,
)
from ocw.core.models import SpanKind, SpanStatus
from ocw.otel.semconv import GenAIAttributes
from tests.factories import (
    make_claude_code_api_error_log,
    make_claude_code_api_request_log,
    make_claude_code_tool_result_log,
)


NOW_NS = int(time.time() * 1e9)
SESSION_ID = "test-session-abc"
PROMPT_ID = "test-prompt-xyz"
RESOURCE = {"service.name": "claude-code"}


def _req_attrs(**overrides) -> dict:
    base = {
        "session.id": SESSION_ID,
        "prompt.id": PROMPT_ID,
        "model": "claude-sonnet-4-6",
        "input_tokens": 1000,
        "output_tokens": 200,
        "cache_read_tokens": 500,
        "cache_creation_tokens": 100,
        "cost_usd": 0.003,
        "duration_ms": 1200.0,
        "event.sequence": 1,
    }
    base.update(overrides)
    return base


def test_api_request_produces_llm_span():
    span = _api_request_to_span(_req_attrs(), RESOURCE, NOW_NS)
    assert span.name == GenAIAttributes.SPAN_LLM_CALL
    assert span.kind == SpanKind.CLIENT
    assert span.status_code == SpanStatus.OK
    assert span.model == "claude-sonnet-4-6"
    assert span.provider == "anthropic"
    assert span.input_tokens == 1000
    assert span.output_tokens == 200
    assert span.cost_usd == pytest.approx(0.003)
    assert span.duration_ms == pytest.approx(1200.0)
    assert span.agent_id == "claude-code"
    assert span.session_id == SESSION_ID


def test_api_request_cache_tokens():
    span = _api_request_to_span(_req_attrs(), RESOURCE, NOW_NS)
    # cache_read_tokens -> cache_tokens field
    assert span.cache_tokens == 500
    # cache_creation_tokens goes into attributes
    assert span.attributes.get("cache_creation_tokens") == 100


def test_tool_result_success_produces_ok_span():
    attrs = {
        "session.id": SESSION_ID,
        "prompt.id": PROMPT_ID,
        "tool_name": "Read",
        "success": True,
        "duration_ms": 50.0,
        "event.sequence": 2,
    }
    span = _tool_result_to_span(attrs, RESOURCE, NOW_NS)
    assert span.name == GenAIAttributes.SPAN_TOOL_CALL
    assert span.kind == SpanKind.INTERNAL
    assert span.status_code == SpanStatus.OK
    assert span.tool_name == "Read"
    assert span.duration_ms == pytest.approx(50.0)
    assert span.status_message is None


def test_tool_result_failure_produces_error_span():
    attrs = {
        "session.id": SESSION_ID,
        "prompt.id": PROMPT_ID,
        "tool_name": "Bash",
        "success": False,
        "error": "command not found",
        "duration_ms": 10.0,
        "event.sequence": 3,
    }
    span = _tool_result_to_span(attrs, RESOURCE, NOW_NS)
    assert span.status_code == SpanStatus.ERROR
    assert span.status_message == "command not found"


def test_api_error_produces_error_llm_span():
    attrs = {
        "session.id": SESSION_ID,
        "model": "claude-sonnet-4-6",
        "error": "rate_limit_exceeded",
        "status_code": 429,
        "attempt": 1,
        "duration_ms": 100.0,
        "event.sequence": 4,
    }
    span = _api_error_to_span(attrs, RESOURCE, NOW_NS)
    assert span.name == GenAIAttributes.SPAN_LLM_CALL
    assert span.status_code == SpanStatus.ERROR
    assert span.status_message == "rate_limit_exceeded"
    assert span.attributes.get("status_code") == 429


def test_user_prompt_produces_invoke_agent_span():
    attrs = {
        "session.id": SESSION_ID,
        "prompt.id": PROMPT_ID,
        "prompt_length": 42,
        "event.sequence": 1,
    }
    span = _user_prompt_to_span(attrs, RESOURCE, NOW_NS)
    assert span.name == GenAIAttributes.SPAN_INVOKE_AGENT
    assert span.kind == SpanKind.SERVER
    assert span.status_code == SpanStatus.OK
    assert span.attributes.get("prompt_length") == 42


def test_tool_decision_produces_internal_span():
    attrs = {
        "session.id": SESSION_ID,
        "prompt.id": PROMPT_ID,
        "tool_name": "Bash",
        "decision": "allow",
        "source": "rules",
        "event.sequence": 5,
    }
    span = _tool_decision_to_span(attrs, RESOURCE, NOW_NS)
    assert span.name == "tool_decision"
    assert span.kind == SpanKind.INTERNAL
    assert span.attributes.get("decision") == "allow"
    assert span.attributes.get("source") == "rules"


def test_trace_id_deterministic_from_session():
    tid1 = _trace_id_from_session("session-abc")
    tid2 = _trace_id_from_session("session-abc")
    assert tid1 == tid2
    assert len(tid1) == 32


def test_trace_id_differs_across_sessions():
    tid1 = _trace_id_from_session("session-abc")
    tid2 = _trace_id_from_session("session-xyz")
    assert tid1 != tid2


def test_parent_span_from_prompt_id():
    attrs_tool = {
        "session.id": SESSION_ID, "prompt.id": PROMPT_ID,
        "tool_name": "Read", "success": True, "duration_ms": 10.0,
    }
    attrs_api = _req_attrs()

    tool_span = _tool_result_to_span(attrs_tool, RESOURCE, NOW_NS)
    api_span = _api_request_to_span(attrs_api, RESOURCE, NOW_NS)

    assert tool_span.parent_span_id == _span_id_from_prompt(PROMPT_ID)
    assert api_span.parent_span_id == _span_id_from_prompt(PROMPT_ID)
    assert tool_span.parent_span_id == api_span.parent_span_id


def test_session_id_extracted_from_attrs():
    span = _api_request_to_span(_req_attrs(**{"session.id": "my-session"}), RESOURCE, NOW_NS)
    assert span.session_id == "my-session"


def test_conversation_id_from_prompt_id():
    span = _api_request_to_span(_req_attrs(**{"prompt.id": "my-prompt"}), RESOURCE, NOW_NS)
    assert span.conversation_id == "my-prompt"


def test_event_sequence_in_attributes():
    span = _api_request_to_span(_req_attrs(**{"event.sequence": 99}), RESOURCE, NOW_NS)
    assert span.attributes.get("event.sequence") == 99


def test_cache_creation_tokens_in_attributes():
    span = _api_request_to_span(_req_attrs(**{"cache_creation_tokens": 256}), RESOURCE, NOW_NS)
    # cache_creation_tokens goes into attributes dict, not the cache_tokens field
    assert span.attributes.get("cache_creation_tokens") == 256
    # cache_tokens field is for reads
    assert span.cache_tokens == 500  # from default _req_attrs


def test_missing_optional_fields_handled():
    # Minimal attrs — no cost_usd, no cache tokens, no prompt.id
    attrs = {
        "session.id": SESSION_ID,
        "model": "claude-sonnet-4-6",
        "input_tokens": 100,
        "output_tokens": 50,
        "duration_ms": 500.0,
    }
    span = _api_request_to_span(attrs, RESOURCE, NOW_NS)
    assert span.cost_usd is None
    assert span.conversation_id is None
    assert span.parent_span_id is None


def test_user_prompt_span_id_matches_parent():
    """The user_prompt span_id should equal the parent_span_id of its children."""
    prompt_attrs = {
        "session.id": SESSION_ID,
        "prompt.id": PROMPT_ID,
        "prompt_length": 10,
    }
    tool_attrs = {
        "session.id": SESSION_ID, "prompt.id": PROMPT_ID,
        "tool_name": "Read", "success": True, "duration_ms": 10.0,
    }
    prompt_span = _user_prompt_to_span(prompt_attrs, RESOURCE, NOW_NS)
    tool_span = _tool_result_to_span(tool_attrs, RESOURCE, NOW_NS)

    assert prompt_span.span_id == _span_id_from_prompt(PROMPT_ID)
    assert tool_span.parent_span_id == prompt_span.span_id


# ── Missing required fields ──────────────────────────────────────────────


def test_api_request_missing_session_id_raises():
    attrs = _req_attrs()
    del attrs["session.id"]
    with pytest.raises(KeyError):
        _api_request_to_span(attrs, RESOURCE, NOW_NS)


def test_api_request_missing_duration_ms_raises():
    attrs = _req_attrs()
    del attrs["duration_ms"]
    with pytest.raises(KeyError):
        _api_request_to_span(attrs, RESOURCE, NOW_NS)


def test_tool_result_missing_tool_name_raises():
    attrs = {
        "session.id": SESSION_ID,
        "prompt.id": PROMPT_ID,
        "success": True,
        "duration_ms": 10.0,
    }
    with pytest.raises(KeyError):
        _tool_result_to_span(attrs, RESOURCE, NOW_NS)


def test_api_error_missing_error_raises():
    attrs = {
        "session.id": SESSION_ID,
        "model": "claude-sonnet-4-6",
        "duration_ms": 100.0,
    }
    with pytest.raises(KeyError):
        _api_error_to_span(attrs, RESOURCE, NOW_NS)
