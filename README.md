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

**Works out of the box with** **Claude Code**, **OpenClaw**, **NemoClaw** and [more](docs/framework-support.md). One command to start monitoring — no custom instrumentation required.

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

OTel-native — any framework that emits OpenTelemetry spans works automatically. One-line patches for everything else. Python, TypeScript, and zero-code OTLP integrations.

See the **[full framework support guide](docs/framework-support.md)** for provider patches, framework patches, zero-code OTLP integrations, and the TypeScript SDK.

---

## Alerts

13 alert types — sensitive actions, budget breaches, retry loops, behavioral drift, schema violations, NemoClaw sandbox events — dispatched to 6 channel types (ntfy, Discord, Telegram, webhook, file, stdout) with cooldown and content stripping.

See the **[full alerts guide](docs/alerts.md)** for alert types, channel configuration, cooldown, and content stripping.

---

## Export and integrate

Export spans as JSON, CSV, OTLP, or OpenEvals format. Prometheus metrics at `:7391/metrics`. Forward to Grafana, Datadog, or any OTel backend.

See the **[full export guide](docs/export.md)** for all formats, filtering options, and the REST API.

---

## Configuration

TOML config at `.ocw/config.toml` (generated by `ocw onboard`). Per-agent budgets, sensitive actions, drift thresholds, capture settings, alert channels, and storage options.

See the **[full configuration reference](docs/configuration.md)** for all options and examples.

---

## CLI reference

16 commands: `onboard`, `doctor`, `status`, `traces`, `cost`, `alerts`, `budget`, `drift`, `tools`, `demo`, `export`, `mcp`, `serve`, `stop`, `uninstall`. All support `--json` for machine-readable output.

See the **[full CLI reference](docs/cli-reference.md)** for all commands, flags, and examples.

---

## Examples

Runnable agents for every supported integration — single provider, single framework, multi-integration, and alerts/drift demos (no API keys needed).

See the **[full examples guide](docs/examples.md)** for the complete list with env vars and setup notes.

---

## Agent Incident Library

Reproducible AI agent failures you can run in 30 seconds. No API keys, no config, no setup.

```bash
ocw demo                     # list all scenarios
ocw demo retry-loop          # run one
ocw demo retry-loop --json   # machine-readable output
```

| Scenario | What goes wrong | What OCW catches |
|---|---|---|
| [`retry-loop`](incidents/retry-loop/README.md) | Agent retries a failing tool in a loop, burning time and tokens | `retry_loop` + `failure_rate` alerts fire automatically |
| [`surprise-cost`](incidents/surprise-cost/README.md) | Model silently escalates from Haiku to Opus mid-chain | Per-model cost breakdown shows the $3+ you didn't expect |
| [`hallucination-drift`](incidents/hallucination-drift/README.md) | Agent behavior shifts — different tokens, different tools | `drift_detected` alert fires with Z-scores at session end |

Each scenario runs against an in-memory backend and produces a side-by-side comparison: what `print()` shows vs. what OCW reveals.

---

## Architecture

DuckDB storage, OTel-native ingest pipeline, post-ingest hooks for cost, alerts, and schema validation. Python SDK, TypeScript SDK, and HTTP all converge at one pipeline.

See the **[full architecture document](docs/architecture.md)** for data flow, package structure, and design principles.

---

## Roadmap

See the **[full roadmap](docs/roadmap.md)** for completed and planned features.

---

<div align="center">

**[opencla.watch](https://opencla.watch)** · [PyPI](https://pypi.org/project/openclawwatch/) · [npm](https://www.npmjs.com/package/@openclawwatch/sdk)

MIT License · Built by [Metabuilder Labs](https://github.com/Metabuilder-Labs)

</div>
