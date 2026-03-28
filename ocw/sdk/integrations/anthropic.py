"""
Anthropic provider integration.

Wraps anthropic.resources.Messages.create and .stream to automatically
create OTel spans with token usage and model attributes.
"""
from __future__ import annotations

import functools
import logging

from opentelemetry import trace

from ocw.otel.semconv import GenAIAttributes

logger = logging.getLogger(__name__)


class AnthropicIntegration:
    name = "anthropic"
    installed = False

    def __init__(self) -> None:
        self._original_create = None
        self._original_stream = None
        self._tracer = None

    def install(self, tracer) -> None:
        """Patch anthropic.resources.Messages.create and .stream."""
        if self.installed:
            return
        self._tracer = tracer
        try:
            from anthropic.resources import Messages
        except ImportError:
            logger.warning("anthropic package not installed — skipping patch")
            return

        self._original_create = Messages.create
        self._original_stream = getattr(Messages, "stream", None)

        integration = self

        @functools.wraps(self._original_create)
        def patched_create(self_msg, *args, **kwargs):
            span = integration._tracer.start_span(GenAIAttributes.SPAN_LLM_CALL)
            span.set_attribute(GenAIAttributes.PROVIDER_NAME, "anthropic")
            span.set_attribute(
                GenAIAttributes.REQUEST_MODEL,
                kwargs.get("model", "unknown"),
            )
            try:
                response = integration._original_create(self_msg, *args, **kwargs)
                if hasattr(response, "usage"):
                    span.set_attribute(
                        GenAIAttributes.INPUT_TOKENS,
                        response.usage.input_tokens,
                    )
                    span.set_attribute(
                        GenAIAttributes.OUTPUT_TOKENS,
                        response.usage.output_tokens,
                    )
                    cache_read = getattr(response.usage, "cache_read_input_tokens", None)
                    if cache_read:
                        span.set_attribute(GenAIAttributes.CACHE_READ_TOKENS, cache_read)
                    cache_create = getattr(response.usage, "cache_creation_input_tokens", None)
                    if cache_create:
                        span.set_attribute(GenAIAttributes.CACHE_CREATE_TOKENS, cache_create)
                span.set_status(trace.Status(trace.StatusCode.OK))
                return response
            except Exception as exc:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
                raise
            finally:
                span.end()

        Messages.create = patched_create

        if self._original_stream is not None:
            @functools.wraps(self._original_stream)
            def patched_stream(self_msg, *args, **kwargs):
                span = integration._tracer.start_span(GenAIAttributes.SPAN_LLM_CALL)
                span.set_attribute(GenAIAttributes.PROVIDER_NAME, "anthropic")
                span.set_attribute(
                    GenAIAttributes.REQUEST_MODEL,
                    kwargs.get("model", "unknown"),
                )
                try:
                    stream = integration._original_stream(self_msg, *args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return _StreamWrapper(stream, span)
                except Exception as exc:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
                    span.end()
                    raise

            Messages.stream = patched_stream

        self.installed = True
        logger.debug("Anthropic integration installed")

    def uninstall(self) -> None:
        if not self.installed:
            return
        try:
            from anthropic.resources import Messages
            if self._original_create:
                Messages.create = self._original_create
            if self._original_stream:
                Messages.stream = self._original_stream
        except ImportError:
            pass
        self.installed = False


class _StreamWrapper:
    """Wraps an Anthropic stream to capture final usage and end the span."""

    def __init__(self, stream, span):
        self._stream = stream
        self._span = span

    def __enter__(self):
        self._stream.__enter__()
        return self

    def __exit__(self, *args):
        result = self._stream.__exit__(*args)
        final_message = getattr(self._stream, "get_final_message", lambda: None)()
        if final_message and hasattr(final_message, "usage"):
            self._span.set_attribute(
                GenAIAttributes.INPUT_TOKENS,
                final_message.usage.input_tokens,
            )
            self._span.set_attribute(
                GenAIAttributes.OUTPUT_TOKENS,
                final_message.usage.output_tokens,
            )
        self._span.end()
        return result

    def __iter__(self):
        return iter(self._stream)

    def __next__(self):
        return next(self._stream)


def patch_anthropic() -> None:
    """Convenience function. Instantiates and installs AnthropicIntegration."""
    integration = AnthropicIntegration()
    integration.install(trace.get_tracer("ocw.sdk"))
