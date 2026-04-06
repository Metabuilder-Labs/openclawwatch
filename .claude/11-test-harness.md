# Task 11 — Test Infrastructure
**Depends on:** Task 00 (foundation — `tests/factories.py`).
**Parallel with:** All other tasks.
**Estimated scope:** Small. Infrastructure only — not writing feature tests.

---

## What this task covers

The shared test infrastructure that all other test tasks depend on. This task should be
started immediately after Task 00, in parallel with all other feature tasks.

---

## Deliverables

### `tests/conftest.py`

```python
import pytest
from ocw.core.db import InMemoryBackend
from ocw.core.config import OcwConfig, StorageConfig, SecurityConfig, CaptureConfig


@pytest.fixture
def db():
    """Fresh in-memory DuckDB backend for each test."""
    backend = InMemoryBackend()
    yield backend
    backend.close()


@pytest.fixture
def config():
    """Minimal OcwConfig suitable for tests."""
    return OcwConfig(
        version="1",
        storage=StorageConfig(path=":memory:"),
        security=SecurityConfig(
            ingest_secret="test-secret-do-not-use",
            max_attribute_bytes=65536,
            max_attributes_per_span=256,
            max_attribute_depth=10,
        ),
        capture=CaptureConfig(
            prompts=True,
            completions=True,
            tool_inputs=True,
            tool_outputs=True,
        ),
    )


@pytest.fixture
def config_no_capture(config):
    """Config with all capture options off."""
    config.capture.prompts      = False
    config.capture.completions  = False
    config.capture.tool_inputs  = False
    config.capture.tool_outputs = False
    return config


class StubCostEngine:
    """No-op CostEngine for tests that don't need cost calculation."""
    def process_span(self, span): pass


class StubAlertEngine:
    """Records fired alerts for assertion in tests."""
    def __init__(self):
        self.fired: list = []
    def evaluate(self, span): pass
    def evaluate_session_end(self, session): pass
    def fire(self, alert_type, span_or_session, detail, severity=None):
        self.fired.append({"type": alert_type, "detail": detail})


class StubSchemaValidator:
    """No-op SchemaValidator for tests that don't need schema validation."""
    def validate(self, span): pass


@pytest.fixture
def stub_cost_engine():
    return StubCostEngine()


@pytest.fixture
def stub_alert_engine():
    return StubAlertEngine()


@pytest.fixture
def stub_schema_validator():
    return StubSchemaValidator()
```

---

### `tests/e2e/conftest.py`

```python
import os
import pytest


def pytest_collection_modifyitems(items):
    """
    Auto-skip all e2e tests unless the required API key env var is set.
    Keeps CI clean — e2e tests are only run when explicitly configured.
    """
    api_key = os.environ.get("OCW_ANTHROPIC_API_KEY")
    if not api_key:
        skip_marker = pytest.mark.skip(
            reason="OCW_ANTHROPIC_API_KEY not set — skipping e2e tests"
        )
        for item in items:
            item.add_marker(skip_marker)
```

---

### `tests/e2e/README.md`

```markdown
# End-to-end tests

These tests make real LLM API calls. They are skipped automatically unless
the required environment variable is set.

## Setup

```bash
export OCW_ANTHROPIC_API_KEY="sk-ant-..."
```

## Running

```bash
pytest tests/e2e/
```

## Cost control

All e2e tests use claude-haiku-4-5 only.
Max 100 input tokens and 50 output tokens per call.
Total expected cost: < $0.01 per full run.
```

---

### `tests/e2e/test_provider_tagging.py`

```python
"""
Real LLM tests. Auto-skipped without OCW_ANTHROPIC_API_KEY.
Verifies provider tagging and token count accuracy.
"""
import pytest
import os
from ocw.sdk.integrations.anthropic import patch_anthropic
from ocw.sdk import watch


@pytest.mark.asyncio
async def test_anthropic_provider_tag_set():
    """
    gen_ai.provider.name must equal "anthropic" after a real Anthropic API call.
    """
    ...


@pytest.mark.asyncio
async def test_anthropic_token_counts_match_api():
    """
    Recorded input_tokens and output_tokens must match what the API reports
    in response.usage.
    """
    ...
```

---

### `pyproject.toml` additions

Add these sections to the root `pyproject.toml` (created in Task 00):

```toml
# Per-layer test configuration — each layer can be run independently

[tool.pytest.ini_options]
# Default testpaths — does NOT include e2e
testpaths = ["tests/unit", "tests/synthetic", "tests/agents", "tests/integration"]
asyncio_mode = "auto"

# To run e2e separately:
# pytest tests/e2e/  (requires OCW_ANTHROPIC_API_KEY env var)
```

---

### `Makefile` (optional but recommended)

```makefile
.PHONY: test test-unit test-synthetic test-agents test-integration test-e2e lint typecheck

test:
	pytest tests/unit/ tests/synthetic/ tests/agents/ tests/integration/

test-unit:
	pytest tests/unit/

test-synthetic:
	pytest tests/synthetic/

test-agents:
	pytest tests/agents/

test-integration:
	pytest tests/integration/

test-e2e:
	pytest tests/e2e/

lint:
	ruff check ocw/

typecheck:
	mypy ocw/

all: lint typecheck test
```