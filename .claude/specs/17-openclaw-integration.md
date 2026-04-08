# Task: Add OpenClaw integration (zero-code OTLP ingestion)

## Context

OpenClaw (the open-source personal AI assistant) already ships a built-in OTel exporter via its `diagnostics-otel` plugin. It emits standard OTLP/HTTP JSON traces with GenAI semantic conventions. This means we do NOT need a Python monkey-patch like we have for LangChain or LiteLLM. Instead, the integration is:

1. Accept OpenClaw's OTLP export at the standard path
2. Map OpenClaw-specific span attributes to OCW's internal model
3. Provide a setup guide

This is the highest-leverage integration for the project — OpenClaw has the largest and most active community of autonomous agent users.

## What OpenClaw emits

OpenClaw's `diagnostics-otel` plugin exports OTLP/HTTP JSON to a configurable endpoint. The span hierarchy looks like:

```
openclaw.request (root span — full request lifecycle)
├── openclaw.agent.turn (one per agent turn)
│   ├── tool.Read (file read)
│   ├── tool.exec (shell command)
│   ├── tool.Write (file write)
│   └── tool.web_search
└── openclaw.model.usage (standalone span with token/cost data)
```

Key attributes emitted:
- `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` — token counts
- `gen_ai.request.model` — model name (e.g. `claude-sonnet-4-20250514`)
- `gen_ai.system` or `gen_ai.provider.name` — provider
- Tool spans have `gen_ai.tool.name` or the tool name in the span name itself
- `service.name` — set to the OpenClaw service name (configurable)

**Important limitation:** OpenClaw cannot auto-instrument individual LLM SDK calls due to ESM/CJS module isolation. Token data comes from `model.usage` diagnostic events as standalone spans, NOT nested inside agent turn spans. OCW must handle this gracefully.

## What to build

### 1. Add standard OTLP/HTTP endpoint: `POST /v1/traces`

OpenClaw's `diagnostics-otel` plugin posts to the standard OTLP/HTTP path: `{endpoint}/v1/traces`. Our ingest endpoint is at `/api/v1/spans`. Add a route alias.

In `ocw/api/app.py`, add a new route that accepts `POST /v1/traces` and forwards to the same OTLP JSON parsing logic used by `/api/v1/spans`.

This should NOT be a redirect — it should call the same handler directly. The body format is identical (OTLP JSON with `resourceSpans`).

Also add `POST /v1/metrics` and `POST /v1/logs` as stub endpoints that return 200 OK — OpenClaw sends all three, and returning errors on metrics/logs would cause noisy warnings in OpenClaw's output. The stubs can silently discard the data for now.

### 2. OpenClaw attribute mapping in the ingest pipeline

The existing `_parse_span()` in `ocw/api/routes/spans.py` already extracts GenAI semconv attributes. But OpenClaw spans have some differences that need handling:

**Agent ID extraction:**
- OpenClaw doesn't set `gen_ai.agent.id` directly. Instead, extract it from `service.name` in the resource attributes (this is the OpenClaw service name configured by the user)
- If `gen_ai.agent.id` is already set, use that (other frameworks set it). Only fall back to `service.name` when `agent_id` would otherwise be null.

**Span name mapping:**
- `openclaw.agent.turn` should be recognized as an agent span type
- `openclaw.request` should be recognized as a root agent span
- Span names starting with `tool.` should have `tool_name` extracted from the span name (e.g. `tool.Read` → tool_name = `Read`, `tool.exec` → tool_name = `exec`)
- `openclaw.model.usage` should be treated as an LLM call span for token/cost tracking

**Token extraction from model.usage spans:**
- These standalone spans carry token counts in their attributes
- The ingest pipeline should process them the same as any LLM call span — extract tokens, calculate cost, attribute to the agent

Add this mapping logic to `_parse_span()` or as a pre-processing step in the ingest pipeline. Keep it generic — check for `openclaw.*` span name patterns, don't hardcode every possible span name.

### 3. Documentation: `docs/openclaw.md`

Create a setup guide at `docs/openclaw.md`:

```markdown
# Using OpenClawWatch with OpenClaw

OpenClaw has built-in OpenTelemetry support. Point it at `ocw serve`
and all your agent telemetry flows in automatically — no SDK code required.

## Setup

1. Start ocw serve:
   ```
   ocw onboard
   ocw serve &
   ```

2. Add to your `openclaw.json`:
   ```json
   {
     "diagnostics": {
       "enabled": true,
       "otel": {
         "enabled": true,
         "endpoint": "http://127.0.0.1:7391",
         "serviceName": "my-openclaw-agent",
         "traces": true,
         "metrics": true,
         "captureContent": false
       }
     },
     "plugins": {
       "allow": ["diagnostics-otel"],
       "entries": {
         "diagnostics-otel": {
           "enabled": true
         }
       }
     }
   }
   ```

3. Restart your OpenClaw gateway. Traces appear immediately:
   ```
   ocw status
   ocw traces
   ocw cost --since 1h
   ```

## What gets captured

- Every agent turn with full tool call history
- Token usage and cost per model call
- Tool executions (file reads, shell commands, web searches, file writes)
- Session continuity across multi-turn conversations

## Sensitive action alerts

Configure alerts for OpenClaw tool calls in `.ocw/config.toml`:
   ```toml
   [agents.my-openclaw-agent]
     [[agents.my-openclaw-agent.sensitive_actions]]
     name = "Write"
     severity = "warning"

     [[agents.my-openclaw-agent.sensitive_actions]]
     name = "exec"
     severity = "critical"
   ```

This fires alerts when your OpenClaw agent writes files or executes
shell commands.
```

### 4. Update README.md

- Move OpenClaw to the **top** of the "Framework support" section
- Add a "Zero-code via OTLP" callout specifically mentioning OpenClaw with a link to `docs/openclaw.md`
- Update the comparison table if OpenClaw integration is mentioned

### 5. Add OpenClaw to the examples

Create `examples/openclaw/README.md` — not a Python script (since the integration is config-only), but a step-by-step guide with:
- The `openclaw.json` config snippet
- The `.ocw/config.toml` snippet with sensitive actions for OpenClaw tools
- Commands to verify it's working
- Screenshots or expected output from `ocw traces` showing OpenClaw spans

### 6. Tests

Add tests in `tests/unit/test_openclaw_ingest.py`:

- Test that `POST /v1/traces` with OTLP JSON is accepted and ingested (same format as `/api/v1/spans`)
- Test that `POST /v1/metrics` and `POST /v1/logs` return 200 OK (stub)
- Test that `openclaw.agent.turn` spans are recognized as agent spans
- Test that `tool.*` span names extract the correct `tool_name`
- Test that `openclaw.model.usage` spans extract token counts correctly
- Test that `service.name` falls back as `agent_id` when `gen_ai.agent.id` is not set
- Test with a realistic OpenClaw OTLP payload (construct one based on the span hierarchy documented above)

---

## What NOT to do

- Do NOT write a Python monkey-patch for OpenClaw — it's a Node.js/TypeScript application
- Do NOT require any OpenClaw plugin installation beyond the built-in `diagnostics-otel`
- Do NOT add OpenClaw as a dependency to `pyproject.toml`
- Do NOT break the existing `/api/v1/spans` endpoint — the new `/v1/traces` route is additive

---

## Verification

- `POST /v1/traces` with OTLP JSON returns 200 and spans appear in `ocw traces`
- `POST /v1/metrics` and `POST /v1/logs` return 200 (stubs, no crash)
- OpenClaw span names (`openclaw.agent.turn`, `tool.Read`, etc.) are parsed correctly
- Token counts from `openclaw.model.usage` spans flow through to `ocw cost`
- `service.name` is used as `agent_id` when no explicit `gen_ai.agent.id` is set
- All existing tests pass
- `ruff check ocw/` passes
- `docs/openclaw.md` renders correctly