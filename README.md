<div align="center">

<img src="https://opencla.watch/icon.svg" alt="OpenClawWatch" width="72" height="72">

# OpenClawWatch

**Local-first observability for autonomous AI agents.**

No cloud. No signup. No surprises.

[![CI](https://github.com/Metabuilder-Labs/openclawwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/Metabuilder-Labs/openclawwatch/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/openclawwatch?color=3d8eff&labelColor=0d1117)](https://pypi.org/project/openclawwatch/)
[![Python](https://img.shields.io/badge/python-3.10%2B-3d8eff?labelColor=0d1117)](https://pypi.org/project/openclawwatch/)
[![License: MIT](https://img.shields.io/badge/license-MIT-3d8eff?labelColor=0d1117)](LICENSE)
[![OTel](https://img.shields.io/badge/OTel-GenAI%20SemConv-3d8eff?labelColor=0d1117)](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

```
pip install openclawwatch
ocw onboard
```

</div>

---

## The problem

Your agent sends emails while you sleep. It writes files, submits forms, calls APIs, spends your money. You find out what happened in the morning — if you're lucky.

Most observability tools out there were built for LLM developers building chat products. None of them were built for **agents with real-world consequences**.

`ocw` is.

---

## What it does

```
ocw status
```

```
● $ ocw status                                       
  anthropic-tool-agent   completed   (0m 2s)

  Cost today:     $0.0018 / $10.0000 limit
  Tokens:         1.5k in / 151 out
  Tool calls:     2
  Active session: 65b7071c-2433-4fc2-a3d9-5b391c0bec66

  No active alerts

 litellm-multi-provider   completed   (0m 4s)

  Cost today:     $0.000199 / $10.0000 limit
  Tokens:         44 in / 68 out
  Tool calls:     0
  Active session: c9585dcf-6bfc-427b-9a27-c9db21f56db8

  send_email called (sensitive action: critical)
```

Or when everything is clean:

```
● my-email-agent  idle

  Cost today:     $0.0340 / $5.0000 limit
  Tokens:         12.4k in / 3.8k out
  Tool calls:     47
  Active session: sess-a1b2c3

  No active alerts
```

**Tracks cost in real time.** Every LLM call is priced as it happens — by agent, model, session, and tool. Budget alerts fire before you hit the limit, not after.

**Fires safety alerts the moment something happens.** `send_email`, `write_file`, `delete_record`, `submit_form` — configure any tool call as a sensitive action and get notified immediately via ntfy, Discord, Telegram, webhook, or all of the above.

**Detects behavioral drift.** Agents change silently — a prompt tweak, a model update, a dependency bump. `ocw` builds a statistical baseline from your agent's real behavior and alerts you when something deviates. No LLM required.

**Validates tool outputs.** Declare a JSON Schema for your tools or let `ocw` infer one automatically. Schema violations are caught the moment they occur — not ten steps later when your agent has already compounded the error.

**Runs entirely on your machine.** DuckDB. Local REST API. No cloud backend. No API key for `ocw` itself. Your telemetry data never leaves unless you explicitly configure it to.

---

## Quickstart

```bash
pip install openclawwatch
ocw onboard          # creates .ocw/config.toml, generates ingest secret
ocw doctor           # verify your setup
```

Instrument your agent:

```python
from ocw.sdk import watch
from ocw.sdk.integrations.anthropic import patch_anthropic

patch_anthropic()    # intercepts all Anthropic API calls automatically

@watch(agent_id="my-agent")
def run(task: str) -> str:
    # your agent code here — nothing else to change
    ...
```

**[Claude Code support out of the box](docs/claude-code-integration.md)** — one command to start monitoring your Claude Code sessions, costs, and tool usage.

**Try it with the included toy agent** (requires `ANTHROPIC_API_KEY`):

```bash
python tests/toy_agent/toy_agent.py    # makes one LLM call, creates a session
ocw status                              # see cost, tokens, session info
ocw traces                              # see the trace with span waterfall
ocw cost                                # cost breakdown by model
```

Watch it live:

https://github.com/user-attachments/assets/b94d13f6-1432-40d4-b093-6958d74f0e65

```bash
ocw status           # current state, cost, active alerts
ocw traces           # full span history with waterfall view
ocw cost --since 7d  # cost breakdown by agent, model, day
ocw alerts           # everything that fired while you were away
ocw budget           # view and set daily/session cost limits
ocw drift            # behavioral drift Z-scores vs baseline
ocw serve            # open http://127.0.0.1:7391/ for the web UI
```

## Web UI

`ocw serve` includes a local web dashboard at `http://127.0.0.1:7391/`.

https://github.com/user-attachments/assets/ff09caec-3487-4542-8628-d62b7d92591f

- **Status** — agent overview with cost, tokens, tool calls, and active alerts
- **Traces** — trace list with span waterfall visualization
- **Cost** — breakdown by agent, model, day, or tool
- **Alerts** — alert history with severity filtering
- **Budget** — view and edit daily/session cost limits per agent, with inherited defaults
- **Drift** — behavioral drift report with Z-score analysis

No signup, no cloud — runs entirely on your machine.

---

## Framework support

`ocw` is OTel-native. Any framework that emits OpenTelemetry spans works automatically. For everything else, one-line patches exist.

See the **[full framework support guide](docs/framework-support.md)** for provider patches, framework patches, zero-code OTLP integrations, and the TypeScript SDK.

| Integration | Type |
|---|---|
| [Claude Code](docs/claude-code-integration.md) | Built-in OTLP |
| [OpenClaw](docs/openclaw.md) | Built-in OTLP |
| [NemoClaw](docs/nemoclaw-integration.md) | WebSocket observer |
| Anthropic, OpenAI, Gemini, Bedrock, LiteLLM | [Python provider patches](docs/framework-support.md#python-provider-patches) |
| LangChain, LangGraph, CrewAI, AutoGen, LlamaIndex | [Python framework patches](docs/framework-support.md#python-framework-patches) |
| OpenAI Agents SDK, Google ADK, Haystack, Pydantic AI | [Zero-code OTLP](docs/framework-support.md#zero-code-via-otlp) |
| TypeScript / Node.js | [@openclawwatch/sdk](docs/framework-support.md#typescript--nodejs) |

---

## Alert channels

Configure where alerts go. Multiple channels work simultaneously.

```toml
# .ocw/config.toml

[[alerts.channels]]
type = "ntfy"
topic = "my-agent-alerts"   # push to your phone, free, no account required

[[alerts.channels]]
type = "discord"
webhook_url = "https://discord.com/api/webhooks/..."

[[alerts.channels]]
type = "webhook"
url = "https://your-endpoint.com/alerts"
```

Alert types: `sensitive_action` · `cost_budget_daily` · `cost_budget_session` · `retry_loop` · `token_anomaly` · `schema_violation` · `drift_detected` · `failure_rate` · `network_egress_blocked` · `filesystem_access_denied` · `syscall_denied` · `inference_rerouted`

---

## Export and integrate

```bash
# Forward spans to Grafana, Datadog, or any OTel backend
ocw export --format otlp

# Export traces for openevals / agentevals trajectory evaluation
ocw export --format openevals --output traces.json

# Raw data
ocw export --format json
ocw export --format csv
```

Prometheus metrics are available at `http://127.0.0.1:7391/metrics` when `ocw serve` is running.

---

## Configuration

```toml
# .ocw/config.toml — generated by ocw onboard

[defaults.budget]
daily_usd = 10.00       # applies to all agents unless overridden

[agents.my-email-agent]
description = "Personal email management agent"

  [agents.my-email-agent.budget]
  daily_usd   = 5.00    # overrides the default
  session_usd = 1.00

  [[agents.my-email-agent.sensitive_actions]]
  name     = "send_email"
  severity = "critical"

  [[agents.my-email-agent.sensitive_actions]]
  name     = "delete_file"
  severity = "critical"

  [agents.my-email-agent.drift]
  enabled           = true
  baseline_sessions = 10
  token_threshold   = 2.0   # Z-score

[capture]
prompts      = false   # off by default — your data stays yours
completions  = false
tool_outputs = false

[storage]
path           = "~/.ocw/telemetry.duckdb"
retention_days = 90
```

Budget limits merge per-field: each agent inherits default limits unless it explicitly overrides them. Set limits via CLI (`ocw budget --daily 10`), the API, or the web UI.

Run `ocw doctor` to verify your configuration at any time.

---

## CLI reference

```
ocw onboard          Guided setup wizard (creates config, generates ingest secret)
ocw onboard --claude-code   Configure Claude Code telemetry
ocw doctor           Health check — config, DB, security, channel validation
ocw status           Current agent state, cost, token counts, active alerts
ocw traces           Trace listing with span waterfall view
ocw cost             Cost breakdown by agent / model / day / tool
ocw alerts           Alert history with filtering by type and severity
ocw budget           View and set daily / session cost limits
ocw drift            Drift report: baseline vs latest session Z-scores
ocw tools            Tool call history with error rates
ocw export           Export to json / csv / otlp / openevals
ocw mcp              Start the MCP server (stdio transport for Claude Code)
ocw serve            Local REST API + Prometheus metrics endpoint
ocw stop             Stop the background daemon or ocw serve process
ocw uninstall        Remove all OCW data, config, and daemon
```

---

## Examples

The [`examples/`](examples/) directory contains runnable agents for every supported integration:

- **Single provider** — Anthropic, OpenAI, Gemini, Bedrock, OpenAI Agents SDK
- **Single framework** — LangChain, LangGraph, CrewAI, AutoGen, LlamaIndex
- **Multi-integration** — provider router, CrewAI + LangChain research team, RAG with fallback
- **Alerts and drift** — sensitive action alerts, budget breach, behavioral drift detection (no API keys needed)

```bash
python examples/single_provider/anthropic_agent.py   # tool-use agent
python examples/alerts_and_drift/drift_demo.py       # zero-cost drift detection demo
```

See [`examples/README.md`](examples/README.md) for the full list with required env vars and setup notes.

---

## Architecture

See **[docs/architecture.md](docs/architecture.md)** for the full architecture document.

---

## Contributing

```bash
git clone https://github.com/Metabuilder-Labs/openclawwatch
cd openclawwatch
pip install -e ".[dev,mcp]"   # editable install with dev tools + MCP support

pytest tests/unit/ tests/synthetic/ tests/agents/ tests/integration/
ruff check ocw/
mypy ocw/
```

To test the Claude Code integration locally after cloning:

```bash
pip install -e ".[dev,mcp]"
ocw onboard --claude-code
# Restart Claude Code
```

The editable install means changes to `ocw/` take effect immediately — no reinstall needed. Use `pip install -e ".[dev]"` if you don't need the MCP server.

292 tests. 2.5 seconds. All green.

See [AGENTS.md](AGENTS.md) for codebase conventions and how AI coding agents should work in this repo.

PRs welcome. If you're adding a framework integration, open an issue first so we can align on the approach.

---

## Roadmap

- [x] `ocw serve` background daemon (launchd / systemd)
- [x] Web UI for `ocw serve`
- [x] LiteLLM provider patch
- [x] `ocw stop` and `ocw uninstall` commands
- [x] Claude Code integration (`ocw onboard --claude-code`)
- [x] `ocw budget` CLI, API route, and web UI
- [x] `ocw drift` CLI with Z-score reporting
- [x] Full pipeline wiring (alerts, schema validation, drift detection in `ocw serve`)
- [x] MCP server (`ocw mcp`) — 13 tools for Claude Code, no `ocw serve` dependency
- [ ] `ocw watch` — live tail mode for spans
- [ ] `ocw replay` — replay captured sessions against new model versions
- [ ] Vercel AI SDK integration (TypeScript)
- [ ] Azure AI Agent Service integration
- [ ] TypeScript framework patches (LangChain JS, OpenAI Agents SDK)
- [ ] Mastra integration (TypeScript)
- [ ] Docker image
- [ ] GitHub Actions integration for CI drift/cost checks

---

<div align="center">

**[opencla.watch](https://opencla.watch)** · [PyPI](https://pypi.org/project/openclawwatch/) · [npm](https://www.npmjs.com/package/@openclawwatch/sdk)

MIT License · Built by [Metabuilder Labs](https://github.com/Metabuilder-Labs)

</div>
