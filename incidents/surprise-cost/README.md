# Why did my agent just spend $47 on a hello world?

**Incident type:** Surprise cost / model escalation  
**Run it:** `pip install openclawwatch && ocw demo surprise-cost`

## The horror story

Your document analysis agent is supposed to use Claude Haiku — cheap, fast, good enough for extraction. You set it up, test it on a small document, it costs $0.003. Ship it.

A week later your billing alert fires. $47 for a single session. You stare at your code. You check the model parameter. It says `claude-haiku-4-5`. Everything looks fine.

Except your agent chains through multiple steps, and somewhere in that chain — maybe a LangChain callback, maybe a fallback handler, maybe just a configuration override — it silently escalated to Opus for "complex" sub-tasks. Each Haiku call is $0.003. Each Opus call is $1.35. You had 35 of them.

You never saw it happen. Your print statements said "response received."

## What print() shows

```
[agent] Starting document analysis...
[llm] Response received (200 OK)
[llm] Response received (200 OK)
[llm] Response received (200 OK)
[llm] Response received (200 OK)
[llm] Response received (200 OK)
[llm] Response received (200 OK)
[llm] Response received (200 OK)
[llm] Response received (200 OK)
[agent] Task complete.
```

Eight successful responses. No errors. No indication that 3 of those calls just cost 100x what you expected.

## What OCW reveals

```
$ ocw demo surprise-cost

$ ocw cost --by model
Model                  Calls    Cost (USD)
claude-haiku-4-5           2       $0.0140
claude-sonnet-4-6          3       $0.1875
claude-opus-4-6            3       $2.2125
──────────────────────────────────────────
Total                      8       $2.4140

$ ocw cost
Date          Agent                  Cost
2026-04-25    demo-surprise-cost    $2.41
```

OCW tracks cost per call, per model, per agent. The escalation is visible the moment it happens.

## Try it yourself

```bash
pip install openclawwatch
ocw demo surprise-cost
```

Then inspect:

```bash
ocw cost --by model   # per-model spend breakdown
ocw cost              # daily cost summary
ocw traces            # see which calls used which model
```

## Prevent it

Set a session budget in `ocw.toml`:

```toml
[[agents]]
id = "my-agent"

[agents.budget]
session_usd = 1.00   # fires COST_BUDGET_SESSION alert if exceeded
daily_usd = 5.00     # fires COST_BUDGET_DAILY alert if exceeded
```

## What OCW is

OCW is a local-first, zero-signup observability CLI for AI agents. It captures telemetry from your agent, stores it in a local DuckDB database, and gives you CLI commands to understand what actually happened.

**→ [github.com/Metabuilder-Labs/openclawwatch](https://github.com/Metabuilder-Labs/openclawwatch)**
