# Task 09 — Python SDK
**Depends on:** Task 00 (foundation), Task 02 (IngestPipeline and OcwSpanExporter).
**Parallel with:** Tasks 03–08, 10–11.
**Estimated scope:** Medium.

---

## What this task covers

- `ocw/sdk/agent.py` — `@watch()` decorator and `AgentSession` context manager
- `ocw/sdk/transport.py` — span delivery (in-process vs HTTP)
- `ocw/sdk/integrations/base.py` — `Integration` protocol
- All framework and provider integration modules

---

## Deliverables

### `ocw/sdk/agent.py`

```python
from __future__ import annotations
import functools
import logging
from typing import Callable, TYPE_CHECKING

from opentelemetry import trace
from ocw.otel.semconv import GenAIAttributes, OcwAttributes
from ocw.utils.ids import new_uuid
from ocw.utils.time_parse import utcnow

if TYPE_CHECKING:
    from ocw.core.config import OcwConfig

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer("ocw.sdk")


def watch(
    agent_id: str,
    *,
    agent_name: str | None = None,
    agent_version: str | None = None,
    conversation_id: str | None = None,
):
    """
    Decorator that wraps an agent entry function with session tracking.

    Creates an OTel span named "invoke_agent" with:
    - gen_ai.agent.id = agent_id
    - gen_ai.agent.name = agent_name (if provided)
    - gen_ai.agent.version = agent_version (if provided)
    - gen_ai.conversation.id = conversation_id (if provided)

    IMPORTANT: This decorator tracks the session (start/end/duration) only.
    Individual LLM call spans are NOT created automatically — they require
    patch_anthropic(), patch_openai(), or equivalent provider patches.

    If no config has been loaded (ocw not onboarded), logs a warning and
    runs the function unwrapped. Never crashes the agent.

    Auto-creates agent config entry on first call if agent_id is not
    already in the config. Logs that auto-creation happened.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with AgentSession(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_version=agent_version,
                conversation_id=conversation_id,
            ):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class AgentSession:
    """
    Context manager for an agent session. Used by @watch() and can also be
    used directly for more control.

    Usage:
        with AgentSession(agent_id="my-agent") as session:
            result = run_my_agent()
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str | None = None,
        agent_version: str | None = None,
        conversation_id: str | None = None,
    ):
        self.agent_id       = agent_id
        self.agent_name     = agent_name
        self.agent_version  = agent_version
        self.conversation_id = conversation_id or new_uuid()
        self._span          = None
        self._ctx           = None

    def __enter__(self) -> AgentSession:
        self._span = _tracer.start_span(GenAIAttributes.SPAN_INVOKE_AGENT)
        self._span.set_attribute(GenAIAttributes.AGENT_ID, self.agent_id)
        if self.agent_name:
            self._span.set_attribute(GenAIAttributes.AGENT_NAME, self.agent_name)
        if self.agent_version:
            self._span.set_attribute(GenAIAttributes.AGENT_VERSION, self.agent_version)
        self._span.set_attribute(
            GenAIAttributes.CONVERSATION_ID, self.conversation_id
        )
        self._ctx = trace.use_span(self._span, end_on_exit=False)
        self._ctx.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._span.set_status(
                trace.Status(trace.StatusCode.ERROR, str(exc_val))
            )
        else:
            self._span.set_status(trace.Status(trace.StatusCode.OK))
        self._span.end()
        self._ctx.__exit__(exc_type, exc_val, exc_tb)
        return False   # Never suppress exceptions


def record_llm_call(
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    duration_ms: float | None = None,
    prompt: str | None = None,
    completion: str | None = None,
) -> None:
    """
    Manual instrumentation: record a single LLM call as an OTel span.
    Use this when no provider patch is available.
    """
    ...


def record_tool_call(
    tool_name: str,
    tool_input: dict | None = None,
    tool_output: dict | None = None,
    duration_ms: float | None = None,
    error: str | None = None,
) -> None:
    """
    Manual instrumentation: record a single tool call as an OTel span.
    Only captures input/output if capture.tool_inputs/outputs = true in config.
    """
    ...
```

---

### `ocw/sdk/transport.py`

```python
"""
Span transport layer. Determines whether spans are delivered in-process
(via OcwSpanExporter, when ocw serve is running in the same process)
or via HTTP POST to the local REST API (when ocw serve is a separate process).

The transport is initialised once when the first @watch() call is made.
Subsequent calls reuse the same transport.
"""
import logging
import httpx
from ocw.core.config import OcwConfig

logger = logging.getLogger(__name__)


class HttpTransport:
    """
    Posts spans to POST /api/v1/spans on the local ocw serve instance.
    Used by TypeScript SDK and as fallback when in-process exporter unavailable.

    Buffers up to 1000 spans if ocw serve is not reachable.
    Retries with exponential backoff (max 3 attempts, 2s base delay).
    Drops buffered spans on process exit with a log warning.
    """

    def __init__(self, config: OcwConfig):
        self.endpoint = (
            f"http://{config.api.host}:{config.api.port}/api/v1/spans"
        )
        self.secret  = config.security.ingest_secret
        self._buffer: list[dict] = []
        self._max_buffer = 1000

    def send(self, spans: list[dict]) -> bool:
        """
        POST spans to ocw serve.
        Returns True on success, False on failure (spans are buffered).
        """
        ...
```

---

### `ocw/sdk/integrations/base.py`

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class Integration(Protocol):
    """
    Formal interface for all framework and provider integrations.

    Convenience functions like patch_anthropic() instantiate and install
    the integration automatically. You can also install manually:

        integration = AnthropicIntegration()
        integration.install(tracer)

    ocw doctor uses `integration.installed` to list active integrations
    and detect conflicts (two integrations patching the same method).
    """
    name: str        # e.g. "anthropic", "langchain", "crewai"
    installed: bool

    def install(self, tracer) -> None:
        """Register all hooks. Idempotent — safe to call multiple times."""
        ...

    def uninstall(self) -> None:
        """Remove all hooks. Called on process shutdown."""
        ...
```

---

### Provider integrations

#### `ocw/sdk/integrations/anthropic.py`

Wraps `anthropic.resources.Messages.create` and `anthropic.resources.Messages.stream`.

Extracts from response:
- `response.usage.input_tokens` → `gen_ai.usage.input_tokens`
- `response.usage.output_tokens` → `gen_ai.usage.output_tokens`
- `response.usage.cache_read_input_tokens` → `gen_ai.usage.cache_read_tokens` (if present)
- `response.usage.cache_creation_input_tokens` → `gen_ai.usage.cache_creation_tokens` (if present)
- `kwargs.get("model")` → `gen_ai.request.model`
- Provider name: `"anthropic"`

```python
class AnthropicIntegration:
    name = "anthropic"
    installed = False

    def install(self, tracer) -> None: ...
    def uninstall(self) -> None: ...


def patch_anthropic() -> None:
    """Convenience function. Instantiates and installs AnthropicIntegration."""
    integration = AnthropicIntegration()
    integration.install(trace.get_tracer("ocw.sdk"))
```

#### `ocw/sdk/integrations/openai.py`

Wraps `openai.resources.chat.completions.Completions.create`.

Extracts: `response.usage.prompt_tokens`, `response.usage.completion_tokens`,
`kwargs.get("model")`. Provider: `"openai"`.

Also handles streaming (`stream=True`) by collecting token counts from the final
`usage` chunk if available.

```python
def patch_openai(base_url: str | None = None) -> None:
    """
    Wraps the OpenAI client.
    Also works for OpenAI-compatible providers (Groq, Together, Fireworks, xAI,
    Azure OpenAI) — pass the provider's base_url and set provider name from it.
    """
```

#### `ocw/sdk/integrations/gemini.py`

Wraps `google.generativeai.GenerativeModel.generate_content` and
`google.generativeai.GenerativeModel.generate_content_async`.

Extracts: `response.usage_metadata.prompt_token_count`,
`response.usage_metadata.candidates_token_count`. Provider: `"google"`.

```python
def patch_gemini() -> None: ...
```

#### `ocw/sdk/integrations/bedrock.py`

Wraps `boto3` client `invoke_model` and `invoke_agent` calls.
The AWS Bedrock response body is JSON — parse it to extract token counts.
Model ID comes from the `modelId` parameter. Provider: `"aws.bedrock"`.

```python
def patch_bedrock() -> None: ...
```

---

### Framework integrations

#### `ocw/sdk/integrations/langchain.py`

Patches `BaseLLM.generate` and `BaseTool.run` (both sync and async variants).
See Task 02 spec for the full implementation pattern.

```python
def patch_langchain() -> None: ...
```

#### `ocw/sdk/integrations/langgraph.py`

Patches LangGraph's `CompiledGraph.invoke` and `CompiledGraph.astream`.
Captures graph node execution as child spans.

```python
def patch_langgraph() -> None: ...
```

#### `ocw/sdk/integrations/crewai.py`

Patches `Task.execute` and `Agent.execute_task`.

```python
def patch_crewai() -> None: ...
```

#### `ocw/sdk/integrations/autogen.py`

Patches `ConversableAgent.generate_reply` and `ConversableAgent.initiate_chat`.

```python
def patch_autogen() -> None: ...
```

#### `ocw/sdk/integrations/llamaindex.py`

LlamaIndex has native OTel support. This module is a thin convenience wrapper
that configures LlamaIndex's built-in OTel instrumentation to point at `ocw serve`.

```python
def patch_llamaindex(config: OcwConfig | None = None) -> None:
    """
    Configure LlamaIndex's built-in OTel support to export to ocw serve.

    This does NOT monkey-patch LlamaIndex internals. It uses LlamaIndex's
    official instrumentation API. Much simpler and more reliable.

    Requires: pip install opentelemetry-instrumentation-llama-index
    """
    from opentelemetry.instrumentation.llama_index import LlamaIndexInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    if config is None:
        config = load_config()

    exporter = OTLPSpanExporter(
        endpoint=f"http://{config.api.host}:{config.api.port}/api/v1/spans",
        headers={"Authorization": f"Bearer {config.security.ingest_secret}"},
    )
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    LlamaIndexInstrumentor().instrument(tracer_provider=provider)
```

#### `ocw/sdk/integrations/openai_agents_sdk.py`

OpenAI Agents SDK has native OTel support. Same pattern as LlamaIndex.

```python
def patch_openai_agents(config: OcwConfig | None = None) -> None:
    """
    Configure OpenAI Agents SDK's built-in OTel support to export to ocw serve.
    Uses the SDK's official set_trace_processors() API.
    """
    from agents import set_trace_processors
    from agents.tracing.processors import BatchTraceProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    ...
```

#### `ocw/sdk/integrations/nemoclaw.py`

NemoClaw/OpenShell Gateway WebSocket observer. Connects to the OpenShell Gateway
at `ws://127.0.0.1:18789` as an observer client, receives sandbox events, and
translates them into OTel spans fed into the ingest pipeline.

```python
import asyncio
import json
import logging
import websockets

# NOTICE: NemoClaw is licensed under Apache License 2.0.
# This integration module acknowledges the upstream Apache 2.0 license.
# See https://github.com/NVIDIA/NemoClaw/blob/main/LICENSE

logger = logging.getLogger(__name__)

# Mapping from OpenShell event types to ocw alert-compatible span attributes
SANDBOX_EVENT_MAP = {
    "network_blocked":   "network_blocked",
    "fs_access_denied":  "fs_denied",
    "syscall_blocked":   "syscall_denied",
    "inference_reroute": "inference_rerouted",
}


class NemoClawGatewayObserver:
    """
    Observes a NemoClaw OpenShell sandbox by connecting to the
    OpenShell Gateway WebSocket as an observer client.

    All inference calls, blocked network requests, filesystem denials,
    and syscall blocks are translated into OTel spans and fed into the
    standard ocw ingest pipeline.

    Usage:
        observer = NemoClawGatewayObserver(ingest_pipeline)
        asyncio.run(observer.connect())  # runs until cancelled
    """

    def __init__(self, ingest_pipeline, gateway_url: str = "ws://127.0.0.1:18789"):
        self.pipeline    = ingest_pipeline
        self.gateway_url = gateway_url

    async def connect(self) -> None:
        """Connect and observe. Reconnects with backoff on disconnect."""
        ...

    def _translate_event(self, event: dict):
        """Convert an OpenShell gateway event to a NormalizedSpan."""
        ...


def watch_nemoclaw(
    gateway_url: str = "ws://127.0.0.1:18789",
    config: OcwConfig | None = None,
) -> NemoClawGatewayObserver:
    """
    Convenience function. Creates an observer instance.
    Call observer.connect() in an asyncio task to start observing.
    """
    ...
```

---

## Public module API (`ocw/sdk/__init__.py`)

```python
from ocw.sdk.agent import watch, AgentSession, record_llm_call, record_tool_call
from ocw.sdk.integrations.anthropic import patch_anthropic
from ocw.sdk.integrations.openai    import patch_openai
from ocw.sdk.integrations.gemini    import patch_gemini
from ocw.sdk.integrations.bedrock   import patch_bedrock
from ocw.sdk.integrations.langchain import patch_langchain
from ocw.sdk.integrations.langgraph import patch_langgraph
from ocw.sdk.integrations.crewai    import patch_crewai
from ocw.sdk.integrations.autogen   import patch_autogen
from ocw.sdk.integrations.llamaindex        import patch_llamaindex
from ocw.sdk.integrations.openai_agents_sdk import patch_openai_agents
from ocw.sdk.integrations.nemoclaw  import watch_nemoclaw

__all__ = [
    "watch", "AgentSession", "record_llm_call", "record_tool_call",
    "patch_anthropic", "patch_openai", "patch_gemini", "patch_bedrock",
    "patch_langchain", "patch_langgraph", "patch_crewai", "patch_autogen",
    "patch_llamaindex", "patch_openai_agents",
    "watch_nemoclaw",
]
```

---

## Tests to write

**`tests/agents/mock_llm.py`:**

```python
class MockLLMClient:
    """
    Pre-scripted responses. Zero API cost. Zero latency.
    Used by all mock agent scenario tests.

    Usage:
        client = MockLLMClient(
            script=["Hello!", "I'll send the email.", "Done."],
            token_counts=[(100, 20), (200, 50), (150, 30)],
        )
        response, in_tok, out_tok = client.complete("Say hello")
    """
    def __init__(self, script: list[str],
                 token_counts: list[tuple[int, int]] | None = None):
        ...

    def complete(self, prompt: str) -> tuple[str, int, int]:
        """Returns (response_text, input_tokens, output_tokens)."""
        ...
```

**`tests/agents/email_agent_normal.py`:**

```python
"""Normal session — baseline behavior, no anomalies."""
from ocw.sdk import watch, record_llm_call, record_tool_call

@watch(agent_id="test-email-agent")
def run(task: str) -> str:
    client = MockLLMClient(script=["Drafting email...", "Sending..."])
    response, in_tok, out_tok = client.complete(task)
    record_llm_call("claude-haiku-4-5", "anthropic", in_tok, out_tok)
    result = "sent"
    record_tool_call("send_email", output={"status": "sent"})
    return result
```

**`tests/agents/email_agent_drift.py`:** Agent with 10× normal token usage.
**`tests/agents/email_agent_loop.py`:** Agent that calls same tool 5 times in a row.
**`tests/agents/email_agent_budget_breach.py`:** Agent whose session cost exceeds limit.

**`tests/agents/test_mock_scenarios.py`:**

```python
def test_normal_session_creates_session_record()
def test_normal_session_records_llm_span()
def test_watch_without_provider_patch_creates_session_not_llm_spans()
    # IMPORTANT: verify this explicitly — common implementation mistake
    # @watch() alone must NOT create LLM call spans
def test_watch_alone_creates_session_span()
def test_record_llm_call_creates_llm_span()
def test_record_tool_call_creates_tool_span()
def test_exception_in_agent_marks_session_as_error()
def test_watch_is_safe_when_not_configured()
    # @watch() should not crash if ocw has not been onboarded
```
