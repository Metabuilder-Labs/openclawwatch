# Your agent isn't flaky. You're blind.

**Incident type:** Retry loop  
**Run it:** `pip install openclawwatch && ocw demo retry-loop`

## The horror story

You deployed your agent last Tuesday. It worked fine in testing. By Wednesday afternoon, your users are complaining that it's "slow" and "keeps spinning." You add a print statement. You see "tool called" in your logs, over and over. You refresh. Still spinning. You restart the process. It fixes itself.

You blame the tool provider. Maybe their API was flaky. You move on.

Except it wasn't flaky. Your agent was stuck in a retry loop — calling the same failing tool six times in eight spans, burning tokens and time on each attempt. The tool was returning null (not an error), so your agent never detected a failure state. It just kept asking the same question to a wall.

## What print() shows

```
[agent] Starting task...
[tool] search_knowledge_base called
[tool] search_knowledge_base returned: null
[tool] search_knowledge_base called
[tool] search_knowledge_base returned: null
[tool] search_knowledge_base called
[tool] search_knowledge_base returned: null
[tool] search_knowledge_base called
[tool] search_knowledge_base returned: null
[agent] Retrying...
```

"Tool called. Tool returned." Technically correct. Completely useless.

## What OCW reveals

```
$ ocw demo retry-loop

Alerts fired:
  ALERT retry_loop — demo-retry-loop

$ ocw traces
TRACE  demo-retry-loop  6 spans  [retry_loop alert]
  gen_ai.invoke_agent
  gen_ai.tool.call  search_knowledge_base  ERROR  300ms
  gen_ai.tool.call  search_knowledge_base  ERROR  300ms
  gen_ai.tool.call  search_knowledge_base  ERROR  300ms
  gen_ai.tool.call  search_knowledge_base  ERROR  300ms
  gen_ai.tool.call  search_knowledge_base  ERROR  300ms

$ ocw alerts
retry_loop  demo-retry-loop  WARNING  search_knowledge_base called 4+ times in 6 spans
```

OCW detects when the same tool appears 4 or more times in the last 6 spans and fires a `retry_loop` alert. No configuration required — it's on by default.

## Try it yourself

```bash
pip install openclawwatch
ocw demo retry-loop
```

Then inspect the results:

```bash
ocw alerts          # see the retry_loop alert
ocw traces          # see the loop pattern in the span waterfall
ocw cost            # see what the loop cost you
```

## What OCW is

OCW is a local-first, zero-signup observability CLI for AI agents. It captures telemetry from your agent, stores it in a local DuckDB database, and gives you CLI commands to understand what actually happened.

**→ [github.com/Metabuilder-Labs/openclawwatch](https://github.com/Metabuilder-Labs/openclawwatch)**
