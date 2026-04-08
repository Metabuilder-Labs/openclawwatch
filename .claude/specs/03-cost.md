# Task 03 — Cost Engine
**Depends on:** Task 00 (foundation), Task 01 (StorageBackend interface).
**Parallel with:** Tasks 02, 04–11.
**Estimated scope:** Small.

---

## What this task covers

- `pricing/models.toml` — the model pricing table
- `ocw/core/pricing.py` — pricing table loader
- `ocw/core/cost.py` — token-to-USD calculation and `CostEngine`
- `ocw cost` CLI command

---

## Deliverables

### `pricing/models.toml`

Community-maintained. Prices in USD per million tokens.
Include at minimum the models listed below. Structure must exactly match what
`pricing.py` expects.

```toml
# pricing/models.toml
# Prices in USD per million tokens.
# Submit a PR when provider prices change.

[anthropic.claude-opus-4-6]
input_per_mtok = 15.00
output_per_mtok = 75.00
cache_read_per_mtok = 1.50
cache_write_per_mtok = 18.75

[anthropic.claude-sonnet-4-6]
input_per_mtok = 3.00
output_per_mtok = 15.00
cache_read_per_mtok = 0.30
cache_write_per_mtok = 3.75

[anthropic.claude-haiku-4-5]
input_per_mtok = 0.80
output_per_mtok = 4.00
cache_read_per_mtok = 0.08
cache_write_per_mtok = 1.00

[openai.gpt-4o]
input_per_mtok = 2.50
output_per_mtok = 10.00

[openai.gpt-4o-mini]
input_per_mtok = 0.15
output_per_mtok = 0.60

[openai.o3]
input_per_mtok = 10.00
output_per_mtok = 40.00

[openai.o4-mini]
input_per_mtok = 1.10
output_per_mtok = 4.40

[google.gemini-2-5-pro]
input_per_mtok = 1.25
output_per_mtok = 10.00

[google.gemini-2-5-flash]
input_per_mtok = 0.15
output_per_mtok = 0.60

[aws.us-amazon-nova-pro-v1]
input_per_mtok = 0.80
output_per_mtok = 3.20

[aws.us-amazon-nova-lite-v1]
input_per_mtok = 0.06
output_per_mtok = 0.24

# OpenAI-compatible providers (Groq, Together, Fireworks, xAI, Azure OpenAI)
# use patch_openai() with a custom base_url — add their model names here
# as they are encountered.

[groq.llama-3-3-70b-versatile]
input_per_mtok = 0.59
output_per_mtok = 0.79

[xai.grok-3]
input_per_mtok = 3.00
output_per_mtok = 15.00

# HUD managed inference (inference.hud.ai)
[hud.claude-sonnet-4-5]
input_per_mtok = 3.00
output_per_mtok = 15.00
```

---

### `ocw/core/pricing.py`

```python
from __future__ import annotations
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


PRICING_FILE = Path(__file__).parent.parent.parent / "pricing" / "models.toml"

# Default rate used when a model is not in the pricing table.
# 0.50 per MTok input, 2.00 per MTok output — conservative mid-range estimate.
DEFAULT_INPUT_PER_MTOK  = 0.50
DEFAULT_OUTPUT_PER_MTOK = 2.00


@dataclass(frozen=True)
class ModelRates:
    input_per_mtok:       float
    output_per_mtok:      float
    cache_read_per_mtok:  float = 0.0
    cache_write_per_mtok: float = 0.0


@lru_cache(maxsize=1)
def load_pricing_table() -> dict[str, dict[str, ModelRates]]:
    """
    Load pricing/models.toml and return a nested dict:
      { provider: { model_name: ModelRates } }
    Cached after first load — restart process to pick up changes.
    """
    with open(PRICING_FILE, "rb") as f:
        raw = tomllib.load(f)
    result: dict[str, dict[str, ModelRates]] = {}
    for provider, models in raw.items():
        result[provider] = {}
        for model_name, rates in models.items():
            result[provider][model_name] = ModelRates(
                input_per_mtok       = rates.get("input_per_mtok", DEFAULT_INPUT_PER_MTOK),
                output_per_mtok      = rates.get("output_per_mtok", DEFAULT_OUTPUT_PER_MTOK),
                cache_read_per_mtok  = rates.get("cache_read_per_mtok", 0.0),
                cache_write_per_mtok = rates.get("cache_write_per_mtok", 0.0),
            )
    return result


def get_rates(provider: str, model: str) -> ModelRates | None:
    """Return ModelRates for the given provider/model, or None if not found."""
    table = load_pricing_table()
    return table.get(provider, {}).get(model)
```

---

### `ocw/core/cost.py`

```python
from __future__ import annotations
import logging
from ocw.core.models import NormalizedSpan
from ocw.core.pricing import get_rates, ModelRates, DEFAULT_INPUT_PER_MTOK, DEFAULT_OUTPUT_PER_MTOK

logger = logging.getLogger(__name__)


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """
    Calculate USD cost for a single LLM call.

    Returns cost rounded to 8 decimal places.
    Falls back to default rates if the provider/model is not in the pricing table.
    Logs a warning on fallback so developers know to add the model.
    Zero tokens → zero cost (no warning).
    """
    if input_tokens == 0 and output_tokens == 0:
        return 0.0

    rates = get_rates(provider, model)
    if rates is None:
        logger.warning(
            "No pricing data for %s/%s — using default rates. "
            "Add to pricing/models.toml to get accurate costs.",
            provider, model,
        )
        rates = ModelRates(
            input_per_mtok=DEFAULT_INPUT_PER_MTOK,
            output_per_mtok=DEFAULT_OUTPUT_PER_MTOK,
        )

    cost = (
        (input_tokens       / 1_000_000) * rates.input_per_mtok +
        (output_tokens      / 1_000_000) * rates.output_per_mtok +
        (cache_read_tokens  / 1_000_000) * rates.cache_read_per_mtok +
        (cache_write_tokens / 1_000_000) * rates.cache_write_per_mtok
    )
    return round(cost, 8)


class CostEngine:
    """
    Post-ingest hook. Called by IngestPipeline after each span is written.
    Calculates cost and updates span.cost_usd + session.total_cost_usd in DB.
    """

    def __init__(self, db):
        self.db = db

    def process_span(self, span: NormalizedSpan) -> None:
        """
        If the span has token counts and a provider/model, calculate cost,
        update span.cost_usd in DB, update session.total_cost_usd in DB.
        No-op if tokens are missing or zero.
        """
        ...
```

---

### `ocw/cli/cmd_cost.py`

```python
import click
import json
from rich.table import Table
from ocw.core.models import CostFilters
from ocw.utils.formatting import console, make_table, format_cost, format_tokens
from ocw.utils.time_parse import parse_since


@click.command("cost")
@click.option("--agent", default=None, help="Filter to specific agent_id")
@click.option("--since", default="7d", help="Time window (e.g. 1h, 7d, 2026-03-01)")
@click.option("--group-by", "group_by",
              type=click.Choice(["agent", "model", "day", "tool"]),
              default="day")
@click.option("--json", "output_json", is_flag=True)
@click.pass_context
def cmd_cost(ctx, agent, since, group_by, output_json):
    """Show cost breakdown by agent, model, day, or tool."""
    db = ctx.obj["db"]
    filters = CostFilters(
        agent_id=agent,
        since=parse_since(since),
        group_by=group_by,
    )
    rows = db.get_cost_summary(filters)
    total = sum(r.cost_usd for r in rows)

    if output_json:
        click.echo(json.dumps({
            "rows": [vars(r) for r in rows],
            "total_cost_usd": total,
        }, default=str))
        return

    # Human-readable Rich table
    # Columns depend on group_by:
    #   day:   DATE | AGENT | MODEL | TOKENS IN | TOKENS OUT | COST
    #   agent: AGENT | MODEL | TOKENS IN | TOKENS OUT | COST
    #   model: MODEL | CALLS | TOKENS IN | TOKENS OUT | COST
    #   tool:  TOOL | CALLS | COST
    # Include a TOTAL row at the bottom.
    ...
```

Exit code: 0 if no alerts present, 1 if any active alerts exist (allows CI budget checks).

---

## Tests to write

**`tests/unit/test_cost.py`:**

```python
def test_calculate_cost_known_model()
    # anthropic/claude-haiku-4-5, 1000 input, 200 output
    # Expected: (1000/1M * 0.80) + (200/1M * 4.00) = 0.0008 + 0.0008 = 0.0016
def test_calculate_cost_with_cache_tokens()
def test_calculate_cost_unknown_model_uses_default()
def test_calculate_cost_zero_tokens_returns_zero_no_warning()
def test_calculate_cost_rounds_to_8_decimal_places()
def test_pricing_table_loads_without_error()
def test_all_models_in_pricing_table_have_required_fields()
    # input_per_mtok and output_per_mtok must exist for every model
```

**`tests/synthetic/test_cost_tracking.py`:**

```python
def test_cost_engine_updates_span_cost_in_db()
def test_cost_engine_updates_session_total_cost()
def test_cost_engine_accumulates_across_multiple_spans()
def test_cost_engine_no_op_when_tokens_missing()
```
