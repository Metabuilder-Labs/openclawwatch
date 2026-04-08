# Task 02 — Ingest Pipeline
**Depends on:** Task 00 (foundation), Task 01 (database — StorageBackend interface).
**Parallel with:** Tasks 03–08 once this is complete.
**Estimated scope:** Medium.

---

## What this task covers

- Span sanitization (reject oversized/malformed spans before they hit the DB)
- Span normalization (OTLP wire format → `NormalizedSpan`)
- Post-ingest hooks (cost, alerts, schema validation are called from here)
- OTel TracerProvider and exporter wiring
- Custom `OcwSpanExporter` (writes spans to DuckDB in-process)
- `ocw/otel/exporters.py` — OTLP/HTTP, OTLP/gRPC, Prometheus setup

The ingest layer is the central hub. Everything flows through it: spans from the Python
SDK arrive via the `OcwSpanExporter`; spans from TypeScript arrive via the REST API and
are also routed through here.

---

## Deliverables

### `ocw/core/ingest.py`

```python
from __future__ import annotations
import json
from typing import TYPE_CHECKING

from ocw.core.models import NormalizedSpan, SessionRecord, SpanStatus, SpanKind
from ocw.core.config import OcwConfig, SecurityConfig
from ocw.otel.semconv import GenAIAttributes
from ocw.utils.ids import new_uuid, new_span_id
from ocw.utils.time_parse import utcnow

if TYPE_CHECKING:
    from ocw.core.db import StorageBackend
    from ocw.core.cost import CostEngine
    from ocw.core.alerts import AlertEngine
    from ocw.core.schema_validator import SchemaValidator


class SpanRejectedError(Exception):
    """Raised when a span fails sanitization. The span is not written to DB."""
    pass


class SpanSanitizer:
    """
    Validates spans before they are written to the database.
    Rejects — never silently truncates — spans that violate limits.
    """

    def __init__(self, config: SecurityConfig):
        self.config = config

    def validate(self, raw_attributes: dict, source: str = "unknown") -> None:
        """
        Raises SpanRejectedError if:
        - Any attribute value serialises to more than max_attribute_bytes bytes
        - The number of attributes exceeds max_attributes_per_span
        - The JSON nesting depth exceeds max_attribute_depth
        source is used only for the error message.
        """
        if len(raw_attributes) > self.config.max_attributes_per_span:
            raise SpanRejectedError(
                f"Span from {source} has {len(raw_attributes)} attributes "
                f"(max {self.config.max_attributes_per_span})"
            )
        for key, value in raw_attributes.items():
            serialised = json.dumps(value).encode()
            if len(serialised) > self.config.max_attribute_bytes:
                raise SpanRejectedError(
                    f"Attribute '{key}' in span from {source} is "
                    f"{len(serialised)} bytes (max {self.config.max_attribute_bytes})"
                )
        depth = _json_depth(raw_attributes)
        if depth > self.config.max_attribute_depth:
            raise SpanRejectedError(
                f"Span from {source} has attribute nesting depth {depth} "
                f"(max {self.config.max_attribute_depth})"
            )


def _json_depth(obj, current: int = 0) -> int:
    """Return the maximum nesting depth of a JSON-serialisable object."""
    if isinstance(obj, dict):
        if not obj:
            return current
        return max(_json_depth(v, current + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return current
        return max(_json_depth(item, current + 1) for item in obj)
    return current


class IngestPipeline:
    """
    Central ingest hub. All spans — whether from the Python SDK's OcwSpanExporter
    or from the REST API — flow through here.

    Post-ingest hooks run synchronously after the span is written to DB:
      1. CostEngine.process_span() — calculates and records cost
      2. AlertEngine.evaluate() — checks all alert rules
      3. SchemaValidator.validate() — checks tool outputs against schema
    """

    def __init__(
        self,
        db: StorageBackend,
        config: OcwConfig,
        cost_engine: CostEngine,
        alert_engine: AlertEngine,
        schema_validator: SchemaValidator,
    ):
        self.db = db
        self.config = config
        self.sanitizer = SpanSanitizer(config.security)
        self.cost_engine = cost_engine
        self.alert_engine = alert_engine
        self.schema_validator = schema_validator

    def process(self, span: NormalizedSpan) -> None:
        """
        Full ingest pipeline for one span:
        1. Sanitize attributes
        2. Resolve or create session (using conversation_id if present)
        3. Write span to DB
        4. Upsert session totals
        5. Run post-ingest hooks
        """
        # 1. Sanitize
        self.sanitizer.validate(span.attributes, source=span.agent_id or "unknown")

        # 2. Session resolution
        span = self._resolve_session(span)

        # 3. Write
        self.db.insert_span(span)

        # 4. Session upsert (update running totals)
        session = self._build_or_update_session(span)
        self.db.upsert_session(session)

        # 5. Post-ingest hooks
        self.cost_engine.process_span(span)
        self.alert_engine.evaluate(span)
        self.schema_validator.validate(span)

    def _resolve_session(self, span: NormalizedSpan) -> NormalizedSpan:
        """
        If the span has a conversation_id and a matching session exists,
        use that session_id. Otherwise create a new session_id.
        This is the session continuity mechanism.
        """
        ...

    def _build_or_update_session(self, span: NormalizedSpan) -> SessionRecord:
        """
        Fetch the current session record and update its running totals
        from this span's token counts, cost, error status, etc.
        """
        ...
```

### `ocw/otel/provider.py`

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.resources import Resource
from opentelemetry import trace
from ocw.core.config import OcwConfig


class OcwSpanExporter(SpanExporter):
    """
    Custom OTel SpanExporter that feeds spans into the IngestPipeline.
    Used when the Python SDK instruments code in-process.

    On export(), for each span:
      1. Convert OTel ReadableSpan → NormalizedSpan
      2. Call ingest_pipeline.process(span)
    """

    def __init__(self, ingest_pipeline):
        self.pipeline = ingest_pipeline

    def export(self, spans) -> SpanExportResult:
        for otel_span in spans:
            try:
                normalised = _convert_otel_span(otel_span)
                self.pipeline.process(normalised)
            except Exception as exc:
                # Never let export errors crash the agent
                import logging
                logging.getLogger("ocw").warning(f"Span export failed: {exc}")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def _convert_otel_span(otel_span) -> NormalizedSpan:
    """
    Convert an opentelemetry-sdk ReadableSpan to NormalizedSpan.
    Extract all indexed attributes (provider, model, tool_name, tokens, etc.)
    from the span's attribute dict using GenAIAttributes constants.
    """
    ...


def build_tracer_provider(config: OcwConfig, ingest_pipeline) -> TracerProvider:
    """
    Build and configure the global TracerProvider.
    Attaches OcwSpanExporter (always) and OTLP exporters (if configured).
    Sets as the global tracer provider.
    """
    exporters = [OcwSpanExporter(ingest_pipeline)]

    if config.export.otlp.enabled:
        exporters.append(_build_otlp_exporter(config.export.otlp))

    resource = Resource.create({
        "service.name": "openclawwatch",
        "service.version": __import__("ocw").__version__,
    })
    provider = TracerProvider(resource=resource)
    for exporter in exporters:
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    return provider


def _build_otlp_exporter(otlp_config):
    """Build OTLP/HTTP or OTLP/gRPC exporter based on config.protocol."""
    ...
```

### `ocw/otel/exporters.py`

```python
def build_prometheus_exporter(config):
    """
    Start the Prometheus metrics endpoint on config.port.
    Returns the exporter instance.
    """
    ...
```

---

## OTLP ingest from REST API

The REST API (`POST /api/v1/spans`) receives spans in OTLP JSON format. After auth
validation it calls `ingest_pipeline.process(span)` for each span in the batch.

The ingest pipeline does not know or care whether a span came from the in-process exporter
or from the REST API. Both paths converge at `IngestPipeline.process()`.

---

## Attribute extraction rules

When converting an OTel span (from either path) to `NormalizedSpan`, extract:

| NormalizedSpan field | OTel attribute key |
|---|---|
| `provider` | `gen_ai.provider.name` |
| `model` | `gen_ai.request.model` |
| `tool_name` | `gen_ai.tool.name` |
| `input_tokens` | `gen_ai.usage.input_tokens` |
| `output_tokens` | `gen_ai.usage.output_tokens` |
| `cache_tokens` | `gen_ai.usage.cache_read_tokens` |
| `conversation_id` | `gen_ai.conversation.id` |
| `request_type` | `gen_ai.request.type` |

If `capture.prompts = false`: do not store `gen_ai.prompt.content` in `attributes`.
If `capture.tool_outputs = false`: do not store `gen_ai.tool.output` in `attributes`.
Strip these from the attributes dict before writing to DB regardless of whether they
were present in the original span.

---

## Tests to write

**`tests/synthetic/test_ingest.py`:**

```python
def test_sanitizer_rejects_oversized_attribute()
def test_sanitizer_rejects_too_many_attributes()
def test_sanitizer_rejects_deeply_nested_attributes()
def test_sanitizer_passes_valid_span()
def test_conversation_id_resolves_to_existing_session()
    # Insert session with conv_id="conv-1" first
    # Ingest span with conv_id="conv-1"
    # Assert span.session_id == original session_id
def test_new_conversation_id_creates_new_session()
def test_prompt_content_stripped_when_capture_off()
def test_tool_output_stripped_when_capture_off()
def test_session_totals_updated_after_span()
    # After inserting 3 spans with 100 input tokens each,
    # session.input_tokens should be 300
def test_span_rejected_error_does_not_crash_agent()
    # SpanRejectedError must be caught and logged, not propagated
```

Use `InMemoryBackend` and stub implementations of `CostEngine`, `AlertEngine`,
`SchemaValidator` (they can be no-ops for ingest tests).
