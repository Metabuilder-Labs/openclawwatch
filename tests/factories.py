"""
Span factory for tests. Never construct NormalizedSpan directly in tests --
use these factory functions. This ensures consistent defaults and readable tests.
"""
from __future__ import annotations
from datetime import timedelta
from ocw.core.models import (
    NormalizedSpan, SessionRecord,
    SpanStatus, SpanKind,
)
from ocw.utils.ids import new_uuid, new_trace_id, new_span_id
from ocw.utils.time_parse import utcnow


def make_llm_span(
    agent_id: str = "test-agent",
    model: str = "claude-haiku-4-5",
    provider: str = "anthropic",
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cache_tokens: int = 0,
    cost_usd: float | None = None,
    tool_name: str | None = None,
    status: str = "ok",
    duration_ms: float = 800.0,
    start_time=None,
    conversation_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    session_id: str | None = None,
    extra_attributes: dict | None = None,
) -> NormalizedSpan:
    """Create a NormalizedSpan representing a single LLM call."""
    now = start_time or utcnow()
    end = now + timedelta(milliseconds=duration_ms)
    attrs = extra_attributes.copy() if extra_attributes else {}

    return NormalizedSpan(
        span_id=span_id or new_span_id(),
        trace_id=trace_id or new_trace_id(),
        name="gen_ai.llm.call",
        kind=SpanKind.CLIENT,
        status_code=SpanStatus(status),
        start_time=now,
        end_time=end,
        duration_ms=duration_ms,
        agent_id=agent_id,
        session_id=session_id,
        provider=provider,
        model=model,
        tool_name=tool_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_tokens=cache_tokens,
        cost_usd=cost_usd,
        conversation_id=conversation_id,
        attributes=attrs,
    )


def make_tool_span(
    agent_id: str = "test-agent",
    tool_name: str = "test_tool",
    status: str = "ok",
    duration_ms: float = 100.0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    conversation_id: str | None = None,
    trace_id: str | None = None,
) -> NormalizedSpan:
    """Create a NormalizedSpan representing a single tool call."""
    now = utcnow()
    end = now + timedelta(milliseconds=duration_ms)

    return NormalizedSpan(
        span_id=new_span_id(),
        trace_id=trace_id or new_trace_id(),
        name="gen_ai.tool.call",
        kind=SpanKind.INTERNAL,
        status_code=SpanStatus(status),
        start_time=now,
        end_time=end,
        duration_ms=duration_ms,
        agent_id=agent_id,
        tool_name=tool_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        conversation_id=conversation_id,
    )


def make_session(
    agent_id: str = "test-agent",
    session_id: str | None = None,
    conversation_id: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    tool_call_count: int = 0,
    error_count: int = 0,
    total_cost_usd: float | None = None,
    status: str = "completed",
    duration_seconds: float = 60.0,
) -> SessionRecord:
    """Create a SessionRecord with sensible defaults."""
    now = utcnow()
    started = now - timedelta(seconds=duration_seconds)

    return SessionRecord(
        session_id=session_id or new_uuid(),
        agent_id=agent_id,
        started_at=started,
        ended_at=now if status == "completed" else None,
        conversation_id=conversation_id or new_uuid(),
        status=status,
        total_cost_usd=total_cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_call_count=tool_call_count,
        error_count=error_count,
    )


def make_session_with_spans(
    agent_id: str = "test-agent",
    span_count: int = 5,
    model: str = "claude-haiku-4-5",
    input_tokens_per_span: int = 1000,
    output_tokens_per_span: int = 200,
) -> tuple[SessionRecord, list[NormalizedSpan]]:
    """Create a session and a matching list of spans sharing a conversation_id."""
    conv_id = new_uuid()
    session_id = new_uuid()
    trace_id = new_trace_id()

    total_input = input_tokens_per_span * span_count
    total_output = output_tokens_per_span * span_count

    session = make_session(
        agent_id=agent_id,
        session_id=session_id,
        conversation_id=conv_id,
        input_tokens=total_input,
        output_tokens=total_output,
        tool_call_count=0,
        duration_seconds=span_count * 1.0,
    )

    spans = []
    for i in range(span_count):
        span = make_llm_span(
            agent_id=agent_id,
            model=model,
            input_tokens=input_tokens_per_span,
            output_tokens=output_tokens_per_span,
            trace_id=trace_id,
            session_id=session_id,
            conversation_id=conv_id,
            duration_ms=800.0,
        )
        spans.append(span)

    return session, spans
