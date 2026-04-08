# Task 00 — Foundation
**Must be completed before all other tasks.**
**Estimated scope:** Small. Pure definitions — no logic, no I/O.

---

## What this task covers

Everything that other parallel tasks depend on. This is pure scaffolding:
- Repo structure and packaging
- All dataclass/model definitions
- OTel SemConv attribute constants
- Config loading
- Utility functions
- `AGENTS.md`

No business logic lives here. If a function does computation, it belongs in another task.

---

## Deliverables

### 1. `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ocw"
version = "0.1.0"
description = "Local-first OTel-native observability for AI agents"
requires-python = ">=3.10"
license = { text = "MIT" }
keywords = ["ai", "agents", "observability", "opentelemetry", "llm"]

dependencies = [
    "click>=8.1",
    "rich>=13.0",
    "tomli>=2.0; python_version < '3.11'",
    "tomli-w>=1.0",
    "duckdb>=0.10",
    "jsonschema>=4.0",
    "genson>=1.2",
    "opentelemetry-sdk>=1.25",
    "opentelemetry-exporter-otlp-proto-http>=1.25",
    "opentelemetry-exporter-otlp-proto-grpc>=1.25",
    "opentelemetry-exporter-prometheus>=0.46b0",
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "httpx>=0.27",
    "apscheduler>=3.10",
    "websockets>=12.0",
]

[project.optional-dependencies]
langchain = ["langchain>=0.2"]
crewai    = ["crewai>=0.28"]
autogen   = ["pyautogen>=0.2"]
dev       = ["pytest", "pytest-asyncio", "httpx", "ruff", "mypy"]

[project.scripts]
ocw = "ocw.cli.main:cli"

[tool.pytest.ini_options]
testpaths = ["tests/unit", "tests/synthetic", "tests/agents", "tests/integration"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict = true
```

---

### 2. Package skeleton

Create the following empty `__init__.py` files to establish the package structure:

```
ocw/__init__.py
ocw/cli/__init__.py
ocw/core/__init__.py
ocw/otel/__init__.py
ocw/api/__init__.py
ocw/api/routes/__init__.py
ocw/sdk/__init__.py
ocw/sdk/integrations/__init__.py
ocw/utils/__init__.py
```

`ocw/__init__.py` should expose the version:
```python
__version__ = "0.1.0"
```

---

### 3. `ocw/core/models.py`

All domain dataclasses. No imports from other `ocw.*` modules — only stdlib and third-party.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING  = "warning"
    INFO     = "info"


class AlertType(str, Enum):
    COST_BUDGET_DAILY        = "cost_budget_daily"
    COST_BUDGET_SESSION      = "cost_budget_session"
    SENSITIVE_ACTION         = "sensitive_action"
    RETRY_LOOP               = "retry_loop"
    TOKEN_ANOMALY            = "token_anomaly"
    SESSION_DURATION         = "session_duration"
    SCHEMA_VIOLATION         = "schema_violation"
    DRIFT_DETECTED           = "drift_detected"
    FAILURE_RATE             = "failure_rate"
    NETWORK_EGRESS_BLOCKED   = "network_egress_blocked"
    FILESYSTEM_ACCESS_DENIED = "filesystem_access_denied"
    SYSCALL_DENIED           = "syscall_denied"
    INFERENCE_REROUTED       = "inference_rerouted"


class SpanStatus(str, Enum):
    OK    = "ok"
    ERROR = "error"
    UNSET = "unset"


class SpanKind(str, Enum):
    INTERNAL  = "internal"
    CLIENT    = "client"
    SERVER    = "server"
    PRODUCER  = "producer"
    CONSUMER  = "consumer"


@dataclass
class NormalizedSpan:
    span_id:        str
    trace_id:       str
    name:           str
    kind:           SpanKind
    status_code:    SpanStatus
    start_time:     datetime
    parent_span_id: str | None     = None
    session_id:     str | None     = None
    agent_id:       str | None     = None
    end_time:       datetime | None = None
    duration_ms:    float | None   = None
    status_message: str | None     = None
    attributes:     dict[str, Any] = field(default_factory=dict)
    events:         list[dict]     = field(default_factory=list)
    # Extracted indexed fields
    provider:       str | None     = None
    model:          str | None     = None
    tool_name:      str | None     = None
    input_tokens:   int | None     = None
    output_tokens:  int | None     = None
    cache_tokens:   int | None     = None
    cost_usd:       float | None   = None
    request_type:   str | None     = None
    conversation_id: str | None    = None


@dataclass
class SessionRecord:
    session_id:      str
    agent_id:        str
    started_at:      datetime
    conversation_id: str | None   = None
    ended_at:        datetime | None = None
    status:          str          = "active"
    total_cost_usd:  float | None = None
    input_tokens:    int          = 0
    output_tokens:   int          = 0
    cache_tokens:    int          = 0
    tool_call_count: int          = 0
    error_count:     int          = 0

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None


@dataclass
class AgentRecord:
    agent_id:   str
    first_seen: datetime
    last_seen:  datetime
    name:       str | None    = None
    version:    str | None    = None
    provider:   str | None    = None


@dataclass
class Alert:
    alert_id:   str
    fired_at:   datetime
    type:       AlertType
    severity:   Severity
    title:      str
    detail:     dict[str, Any]
    agent_id:   str | None = None
    session_id: str | None = None
    span_id:    str | None = None
    acknowledged: bool     = False
    suppressed:   bool     = False


@dataclass
class DriftBaseline:
    agent_id:               str
    sessions_sampled:       int
    computed_at:            datetime
    avg_input_tokens:       float | None = None
    stddev_input_tokens:    float | None = None
    avg_output_tokens:      float | None = None
    stddev_output_tokens:   float | None = None
    avg_session_duration_s: float | None = None
    stddev_session_duration: float | None = None
    avg_tool_call_count:    float | None = None
    stddev_tool_call_count: float | None = None
    common_tool_sequences:  list | None  = None
    output_schema_inferred: dict | None  = None


@dataclass
class DriftViolation:
    dimension: str
    z_score:   float | None   = None
    expected:  str | None     = None
    observed:  str | None     = None
    detail:    str | None     = None


@dataclass
class DriftResult:
    violations: list[DriftViolation]
    drifted:    bool


@dataclass
class SchemaValidationResult:
    validation_id: str
    span_id:       str
    validated_at:  datetime
    passed:        bool
    errors:        list[str]  = field(default_factory=list)
    agent_id:      str | None = None


@dataclass
class TraceRecord:
    trace_id:   str
    agent_id:   str | None
    name:       str
    start_time: datetime
    duration_ms: float | None = None
    cost_usd:   float | None  = None
    status_code: str          = "ok"
    span_count:  int          = 0


@dataclass
class CostRow:
    group:        str
    agent_id:     str | None  = None
    model:        str | None  = None
    input_tokens: int         = 0
    output_tokens: int        = 0
    cost_usd:     float       = 0.0


# ── Filter dataclasses used by StorageBackend ──────────────────────────────

@dataclass
class TraceFilters:
    agent_id:   str | None   = None
    since:      datetime | None = None
    until:      datetime | None = None
    span_name:  str | None   = None
    status:     str | None   = None
    limit:      int          = 50
    offset:     int          = 0


@dataclass
class CostFilters:
    agent_id:  str | None   = None
    since:     datetime | None = None
    until:     datetime | None = None
    group_by:  str          = "day"   # agent | model | day | tool


@dataclass
class AlertFilters:
    agent_id:  str | None   = None
    since:     datetime | None = None
    severity:  Severity | None = None
    type:      AlertType | None = None
    unread:    bool          = False
    limit:     int           = 100
```

---

### 4. `ocw/otel/semconv.py`

Pure constants — no imports from the rest of `ocw`.

```python
"""
OpenTelemetry GenAI Semantic Conventions attribute names.
Based on OTel GenAI SemConv v1.37+.
"""


class GenAIAttributes:
    # Agent identity
    AGENT_ID      = "gen_ai.agent.id"
    AGENT_NAME    = "gen_ai.agent.name"
    AGENT_VERSION = "gen_ai.agent.version"

    # Provider (anthropic | openai | aws.bedrock | google | hud | ...)
    PROVIDER_NAME = "gen_ai.provider.name"

    # LLM request
    REQUEST_MODEL = "gen_ai.request.model"
    REQUEST_TYPE  = "gen_ai.request.type"

    # Token usage
    INPUT_TOKENS        = "gen_ai.usage.input_tokens"
    OUTPUT_TOKENS       = "gen_ai.usage.output_tokens"
    CACHE_READ_TOKENS   = "gen_ai.usage.cache_read_tokens"
    CACHE_CREATE_TOKENS = "gen_ai.usage.cache_creation_tokens"

    # Tool calls
    TOOL_NAME        = "gen_ai.tool.name"
    TOOL_DESCRIPTION = "gen_ai.tool.description"
    TOOL_INPUT       = "gen_ai.tool.input"
    TOOL_OUTPUT      = "gen_ai.tool.output"

    # Conversation / session continuity
    CONVERSATION_ID = "gen_ai.conversation.id"

    # Prompt / completion capture (off by default)
    PROMPT_CONTENT     = "gen_ai.prompt.content"
    COMPLETION_CONTENT = "gen_ai.completion.content"

    # Standard span names
    SPAN_INVOKE_AGENT = "invoke_agent"
    SPAN_CREATE_AGENT = "create_agent"
    SPAN_TOOL_CALL    = "gen_ai.tool.call"
    SPAN_LLM_CALL     = "gen_ai.llm.call"


class OcwAttributes:
    """ocw-specific span attributes (non-standard extensions)."""
    COST_USD         = "ocw.cost_usd"
    ALERT_TYPE       = "ocw.alert.type"
    ALERT_SEVERITY   = "ocw.alert.severity"
    # NemoClaw / OpenShell sandbox events
    SANDBOX_EVENT    = "ocw.sandbox.event"
    EGRESS_HOST      = "ocw.sandbox.egress_host"
    EGRESS_PORT      = "ocw.sandbox.egress_port"
    FILESYSTEM_PATH  = "ocw.sandbox.filesystem_path"
    SYSCALL_NAME     = "ocw.sandbox.syscall_name"
```

---

### 5. `ocw/core/config.py`

Config loading, validation, and the full `OcwConfig` dataclass hierarchy.

```python
from __future__ import annotations
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w


# ── Nested config dataclasses ──────────────────────────────────────────────

@dataclass
class SensitiveAction:
    name:     str
    severity: str = "warning"   # critical | warning | info


@dataclass
class BudgetConfig:
    daily_usd:   float | None = None
    session_usd: float | None = None


@dataclass
class DriftConfig:
    enabled:            bool  = True
    baseline_sessions:  int   = 10
    token_threshold:    float = 2.0
    tool_sequence_diff: float = 0.4


@dataclass
class AgentConfig:
    description:      str                  = ""
    budget:           BudgetConfig         = field(default_factory=BudgetConfig)
    sensitive_actions: list[SensitiveAction] = field(default_factory=list)
    output_schema:    str | None           = None
    drift:            DriftConfig          = field(default_factory=DriftConfig)


@dataclass
class StorageConfig:
    path:           str = "~/.ocw/telemetry.duckdb"
    retention_days: int = 90


@dataclass
class OtlpConfig:
    enabled:  bool        = False
    endpoint: str         = "http://localhost:4318"
    protocol: str         = "http"   # http | grpc
    headers:  dict        = field(default_factory=dict)
    insecure: bool        = True


@dataclass
class PrometheusConfig:
    enabled: bool = True
    port:    int  = 9464
    path:    str  = "/metrics"


@dataclass
class ExportConfig:
    otlp:       OtlpConfig       = field(default_factory=OtlpConfig)
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)


@dataclass
class AlertChannelConfig:
    type: str
    # stdout / file
    path: str | None = None
    # ntfy
    topic:        str | None = None
    server:       str        = "https://ntfy.sh"
    token:        str        = ""
    # webhook
    url:     str | None = None
    method:  str        = "POST"
    headers: dict       = field(default_factory=dict)
    # discord
    webhook_url: str | None = None
    # telegram
    bot_token: str | None = None
    chat_id:   str | None = None
    # shared
    min_severity: str = "info"


@dataclass
class AlertsConfig:
    cooldown_seconds:        int  = 60
    include_captured_content: bool = False
    channels: list[AlertChannelConfig] = field(default_factory=lambda: [
        AlertChannelConfig(type="stdout"),
    ])


@dataclass
class SecurityConfig:
    ingest_secret:          str = ""
    max_attribute_bytes:    int = 65536
    max_attributes_per_span: int = 256
    max_attribute_depth:    int = 10
    webhook_allowed_domains: list[str] = field(default_factory=list)


@dataclass
class ApiAuthConfig:
    enabled: bool = False
    api_key: str  = ""


@dataclass
class ApiConfig:
    enabled: bool         = True
    host:    str          = "127.0.0.1"
    port:    int          = 7391
    auth:    ApiAuthConfig = field(default_factory=ApiAuthConfig)


@dataclass
class CaptureConfig:
    prompts:      bool = False
    completions:  bool = False
    tool_inputs:  bool = False
    tool_outputs: bool = False


@dataclass
class OcwConfig:
    version:  str
    agents:   dict[str, AgentConfig]  = field(default_factory=dict)
    storage:  StorageConfig           = field(default_factory=StorageConfig)
    export:   ExportConfig            = field(default_factory=ExportConfig)
    alerts:   AlertsConfig            = field(default_factory=AlertsConfig)
    security: SecurityConfig          = field(default_factory=SecurityConfig)
    api:      ApiConfig               = field(default_factory=ApiConfig)
    capture:  CaptureConfig           = field(default_factory=CaptureConfig)


# ── File discovery ─────────────────────────────────────────────────────────

SEARCH_PATHS = [
    Path("ocw.toml"),
    Path(".ocw/config.toml"),
    Path.home() / ".config" / "ocw" / "config.toml",
]


def find_config_file(override: str | None = None) -> Path | None:
    if override:
        p = Path(override)
        if p.exists():
            return p
        raise FileNotFoundError(f"Config file not found: {override}")
    for path in SEARCH_PATHS:
        if path.exists():
            return path
    return None


def load_config(path: str | None = None) -> OcwConfig:
    """
    Load config from file, merge with defaults, return OcwConfig.

    IMPORTANT: tomllib requires binary mode "rb" — not text mode "r".
    Using "r" raises TypeError at runtime.
    """
    config_path = find_config_file(path)
    if config_path is None:
        # Return all-defaults config if no file found
        return OcwConfig(version="1")

    with open(config_path, "rb") as f:   # "rb" is REQUIRED
        raw = tomllib.load(f)

    return _parse(raw)


def write_config(config: OcwConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(_serialise(config), f)


def _parse(raw: dict) -> OcwConfig:
    """Convert raw TOML dict to OcwConfig, applying defaults for missing keys."""
    # Implementation: walk raw dict, construct nested dataclasses
    # Each sub-key falls back to dataclass field defaults if absent
    raise NotImplementedError("implement _parse()")


def _serialise(config: OcwConfig) -> dict:
    """Convert OcwConfig back to a plain dict suitable for tomli_w."""
    raise NotImplementedError("implement _serialise()")
```

Implement `_parse()` and `_serialise()`. No external libraries beyond tomllib/tomli — just
plain dict walking and dataclass construction.

---

### 6. `ocw/utils/time_parse.py`

Parse the `--since` flag values used on every CLI command.

Supported formats:
- `30m` → 30 minutes ago
- `1h`, `12h` → N hours ago
- `1d`, `7d` → N days ago
- `2026-03-01` → start of that date (UTC)
- `2026-03-01T10:00:00Z` → exact ISO datetime

```python
from datetime import datetime, timedelta, timezone
import re


def parse_since(value: str) -> datetime:
    """
    Parse a --since value and return the corresponding UTC datetime.
    Raises ValueError with a descriptive message for unrecognised formats.
    """
    ...


def utcnow() -> datetime:
    """Return current UTC time, timezone-aware."""
    return datetime.now(tz=timezone.utc)
```

Write unit tests for all formats in `tests/unit/test_time_parse.py`. Include edge cases:
invalid strings, boundary values, exact ISO round-trip.

---

### 7. `ocw/utils/ids.py`

```python
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


def new_trace_id() -> str:
    """Generate a 32-char hex trace ID (OTel format)."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:0]  # 32 hex chars


def new_span_id() -> str:
    """Generate a 16-char hex span ID (OTel format)."""
    return uuid.uuid4().hex[:16]
```

---

### 8. `ocw/utils/formatting.py`

Rich output helpers used by CLI commands. Do not put business logic here — only
presentation formatting.

```python
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()
err_console = Console(stderr=True)


def severity_colour(severity: str) -> str:
    return {"critical": "red", "warning": "yellow", "info": "blue"}.get(severity, "white")


def status_icon(status: str) -> str:
    return {"ok": "✓", "error": "✗", "active": "●", "idle": "○"}.get(status, "?")


def format_cost(usd: float) -> str:
    if usd < 0.001:
        return f"${usd:.6f}"
    return f"${usd:.4f}"


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def make_table(*headers: str, box_style=box.SIMPLE) -> Table:
    """Create a pre-styled Rich table."""
    t = Table(box=box_style, show_header=True, header_style="bold dim")
    for h in headers:
        t.add_column(h)
    return t
```

---

### 9. `tests/factories.py`

The span factory used by all synthetic and mock-agent tests. Must be complete before
any other test file is written.

```python
"""
Span factory for tests. Never construct NormalizedSpan directly in tests —
use these factory functions. This ensures consistent defaults and readable tests.
"""
from __future__ import annotations
from datetime import datetime, timezone
from ocw.core.models import (
    NormalizedSpan, SessionRecord, AgentRecord,
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
    start_time: datetime | None = None,
    conversation_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    session_id: str | None = None,
    extra_attributes: dict | None = None,
) -> NormalizedSpan:
    """Create a NormalizedSpan representing a single LLM call."""
    ...


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
    ...


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
    ...


def make_session_with_spans(
    agent_id: str = "test-agent",
    span_count: int = 5,
    model: str = "claude-haiku-4-5",
    input_tokens_per_span: int = 1000,
    output_tokens_per_span: int = 200,
) -> tuple[SessionRecord, list[NormalizedSpan]]:
    """Create a session and a matching list of spans sharing a conversation_id."""
    ...
```

Implement all four factory functions fully. They must produce valid, internally consistent
objects (e.g. `session.input_tokens` == sum of span `input_tokens` when spans are provided).

---

## Dependencies this task provides for other tasks

Once this task is complete, all other tasks can import:

```python
from ocw.core.models import NormalizedSpan, SessionRecord, Alert, ...
from ocw.core.config import OcwConfig, load_config
from ocw.otel.semconv import GenAIAttributes, OcwAttributes
from ocw.utils.time_parse import parse_since, utcnow
from ocw.utils.ids import new_uuid, new_span_id, new_trace_id
from ocw.utils.formatting import console, make_table, format_cost
from tests.factories import make_llm_span, make_session
```

Do not start any other task until these imports resolve without errors.

---

## Tests to write (in `tests/unit/`)

- `test_time_parse.py` — all `parse_since()` formats, valid and invalid
- `test_models.py` — `SessionRecord.duration_seconds` property, enum values
- `test_formatting.py` — `format_cost()`, `format_tokens()`, `severity_colour()`
- `test_config.py` — `load_config()` with various TOML inputs, binary mode requirement
