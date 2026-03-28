# Task 06 — Schema Validation
**Depends on:** Task 00 (foundation), Task 01 (StorageBackend interface).
**Parallel with:** Tasks 02–05, 07–11.
**Estimated scope:** Small.

---

## What this task covers

- `ocw/core/schema_validator.py`

Schema validation checks whether tool call outputs match a declared or inferred JSON Schema.
Only fires when `capture.tool_outputs = true` in config — if outputs are not captured,
there is nothing to validate.

---

## Deliverables

### `ocw/core/schema_validator.py`

```python
from __future__ import annotations
import json
import logging
from typing import TYPE_CHECKING

import jsonschema
from genson import SchemaBuilder

from ocw.core.models import SchemaValidationResult, AlertType, Severity
from ocw.otel.semconv import GenAIAttributes
from ocw.utils.ids import new_uuid
from ocw.utils.time_parse import utcnow

if TYPE_CHECKING:
    from ocw.core.db import StorageBackend
    from ocw.core.models import NormalizedSpan, SessionRecord
    from ocw.core.alerts import AlertEngine
    from ocw.core.config import OcwConfig

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Post-ingest hook. Called by IngestPipeline after each span.

    Only runs when ALL of these are true:
    1. span.name == "gen_ai.tool.call"
    2. span has gen_ai.tool.output in its attributes (capture.tool_outputs = true)
    3. The agent has an output_schema configured, OR an inferred schema has been built

    If output_schema is a file path in config, load the JSON Schema from that file.
    If no schema is declared, use inferred schema from drift_baselines table.
    If neither exists yet, silently skip.
    """

    def __init__(self, db: StorageBackend, alert_engine: AlertEngine, config: OcwConfig):
        self.db = db
        self.alert_engine = alert_engine
        self.config = config
        self._schema_cache: dict[str, dict] = {}

    def validate(self, span: NormalizedSpan) -> None:
        """
        Validate tool output against schema if applicable.
        Persists a SchemaValidationResult to DB regardless of pass/fail.
        Fires SCHEMA_VIOLATION alert on failure.
        """
        if span.name != GenAIAttributes.SPAN_TOOL_CALL:
            return

        tool_output = span.attributes.get(GenAIAttributes.TOOL_OUTPUT)
        if tool_output is None:
            return   # capture.tool_outputs is off — silent skip

        schema = self._get_schema(span.agent_id)
        if schema is None:
            return   # no schema available yet

        errors = list(jsonschema.Draft7Validator(schema).iter_errors(tool_output))

        result = SchemaValidationResult(
            validation_id=new_uuid(),
            span_id=span.span_id,
            agent_id=span.agent_id,
            validated_at=utcnow(),
            passed=len(errors) == 0,
            errors=[e.message for e in errors],
        )
        self.db.insert_validation(result)

        if not result.passed:
            self.alert_engine.fire(
                alert_type=AlertType.SCHEMA_VIOLATION,
                span_or_session=span,
                detail={"errors": result.errors, "tool_name": span.tool_name},
                severity=Severity.WARNING,
            )

    def _get_schema(self, agent_id: str | None) -> dict | None:
        """
        Return the JSON Schema for this agent, or None if unavailable.
        Priority: 1) declared schema file in config, 2) inferred schema in baseline.
        Caches loaded schemas in-memory.
        """
        ...

    def infer_schema_from_sessions(self, sessions: list[SessionRecord]) -> dict | None:
        """
        Use genson to infer a JSON Schema from tool outputs observed in past sessions.
        Returns None if no tool outputs were found in the provided sessions.
        Only called when output_schema is not declared in config.
        """
        builder = SchemaBuilder()
        found_any = False
        for session in sessions:
            spans = self.db.get_trace_spans(session.session_id)
            for span in spans:
                output = span.attributes.get(GenAIAttributes.TOOL_OUTPUT)
                if output is not None:
                    builder.add_object(output)
                    found_any = True
        return builder.to_schema() if found_any else None
```

---

## Tests to write

**`tests/synthetic/test_schema_validation.py`:**

```python
def test_schema_valid_output_passes()
def test_schema_invalid_output_fires_alert()
def test_schema_invalid_output_persists_validation_result()
def test_schema_skipped_when_tool_output_not_captured()
def test_schema_skipped_when_no_schema_available()
def test_schema_skipped_for_non_tool_spans()
def test_infer_schema_from_sessions_produces_valid_schema()
def test_infer_schema_returns_none_when_no_outputs()
```