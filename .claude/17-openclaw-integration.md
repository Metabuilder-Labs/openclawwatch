# Task: Fix SDK DuckDB lock, LiteLLM pricing prefix, and Web UI logo

Three bugs to fix, all independent of each other.

---

## Bug 1: SDK DuckDB lock when `ocw serve` is running

### Problem
When `ocw serve` is running, the Python SDK (`@watch` decorator and `patch_*` integrations) fails to write spans because DuckDB only allows one connection. The SDK currently opens DuckDB directly via `bootstrap.py`. The error:

```
OCW bootstrap failed — spans will not be recorded: IO Error: Could not set lock on file
```

This means **the most common usage pattern is broken**: run `ocw serve` for the web UI, then run your agent — spans are silently dropped.

### Fix
The SDK bootstrap (`ocw/sdk/bootstrap.py`) needs the same HTTP fallback the CLI got via `ApiBackend`. When initializing:

1. Try to connect to `http://127.0.0.1:{port}/api/v1/spans` (check if `ocw serve` is running)
2. If the server is reachable, configure the `OcwSpanExporter` to POST spans via HTTP instead of writing to DuckDB
3. If the server is NOT reachable, open DuckDB directly (current behavior)

This way, when `ocw serve` is running, the SDK sends spans over HTTP to the server (which owns the DuckDB lock). When it's not running, the SDK writes directly.

### Implementation approach
- In `ocw/sdk/bootstrap.py`, before calling `build_tracer_provider()`, check if the API is up with a quick HTTP GET to `http://127.0.0.1:{port}/api/v1/status` (read port from config)
- If reachable, create an `OcwHttpExporter` that POSTs OTLP JSON to `/api/v1/spans` instead of using the in-process `OcwSpanExporter`
- The HTTP exporter should include the ingest secret as the `Authorization` header
- If the check fails (connection refused), fall back to the current DuckDB path
- Log which mode was selected: `"OCW: sending spans to ocw serve at http://..."` or `"OCW: writing spans to local DuckDB"`

### Files to change
- `ocw/sdk/bootstrap.py` — add server detection and HTTP exporter path
- New file: `ocw/sdk/http_exporter.py` — lightweight OTLP HTTP exporter
- `ocw/otel/exporter.py` — may need minor changes if the exporter interface needs adapting

### Tests
- Test that SDK detects running server and uses HTTP exporter
- Test that SDK falls back to DuckDB when server is not running
- Test that spans sent via HTTP exporter arrive in the ingest pipeline

---

## Bug 2: LiteLLM double provider prefix in model name

### Problem
LiteLLM passes model names like `openai/gpt-4o-mini`. The LiteLLM patch extracts the provider from the prefix AND sets it separately. But the model name stored in the span includes the prefix, and the pricing lookup also prepends the provider, resulting in:

```
No pricing data for openai/openai/gpt-4o-mini — using default rates.
```

The model is stored as `openai/gpt-4o-mini` when pricing expects just `gpt-4o-mini`.

### Fix
In `ocw/sdk/integrations/litellm.py`, when recording the `gen_ai.request.model` attribute:
- Store the **full** LiteLLM model string as `gen_ai.request.model` (e.g. `openai/gpt-4o-mini`) — this is correct for display
- In the cost engine (`ocw/core/cost.py`), when looking up pricing, strip the provider prefix if present before matching against `pricing/models.toml`

Alternatively, store just the model name without prefix (e.g. `gpt-4o-mini`) and keep the provider in `gen_ai.provider.name`. Check how other patches handle this — `patch_openai` stores just `gpt-4o-mini`, so LiteLLM should be consistent.

### Files to change
- `ocw/sdk/integrations/litellm.py` — strip provider prefix from model name before setting span attribute
- OR `ocw/core/cost.py` — strip prefix during pricing lookup
- Pick whichever approach is more consistent with existing patches

### Tests
- Verify `ocw cost` shows `gpt-4o-mini` not `openai/gpt-4o-mini` or `openai/openai/gpt-4o-mini`
- Verify pricing lookup finds the correct rates

---

## Bug 3: Web UI sidebar missing SVG logo

### Problem
The sidebar brand area shows text-only "OpenClawWatch" without the icon. The opencla.watch landing page has an SVG icon/logo that should appear in the web UI sidebar too.

### Fix
The logo SVG is hosted at `https://opencla.watch/icon.svg` and referenced in the repo README:
```html
<img src="https://opencla.watch/icon.svg" alt="OpenClawWatch" width="72" height="72">
```

1. Download the SVG from `https://opencla.watch/icon.svg` and embed it inline in `ocw/ui/index.html` (don't reference the external URL — the web UI runs on localhost and must work offline)
2. Replace the current `.sidebar-brand` div contents with: embedded SVG (24x24px) + "OpenClawWatch" text
3. Layout: flex row, 8px gap, vertically centered
4. The SVG should use `fill: var(--accent)` or `currentColor` so it inherits the accent color (`#3d8eff`)
5. Keep the existing font styling (Bricolage Grotesque, 700 weight, accent color)

### Files to change
- `ocw/ui/index.html` — sidebar brand area only

---

## Verification
- Run `ocw serve &`, then `python3 examples/single_provider/anthropic_agent.py` — spans should appear in the web UI (no DuckDB lock error)
- Run `python3 examples/single_provider/litellm_agent.py` then `ocw cost` — model names should show `gpt-4o-mini` and `claude-haiku-4-5` without double prefixes, and pricing should resolve correctly
- Web UI sidebar shows the opencla.watch SVG logo next to "OpenClawWatch" text
- All existing tests pass
- `ruff check ocw/` passes