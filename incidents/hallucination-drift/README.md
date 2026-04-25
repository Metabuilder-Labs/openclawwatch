# My agent worked yesterday. Today it's possessed.

**Incident type:** Behavioral drift  
**Run it:** `pip install openclawwatch && ocw demo hallucination-drift`

## The horror story

Your coding agent has been running reliably for two weeks. Same prompts, same codebase, same everything. Then on Tuesday you notice the outputs are... different. Longer. More verbose. Using different variable naming conventions. Making tool calls you don't recognize in the logs.

You ask it directly: "Why did you change your approach?" It confidently explains its reasoning. The reasoning sounds plausible. You can't tell if it's drifted or if you're imagining it.

This is the worst kind of failure — no error, no crash, no alert. Just behavior that used to be one thing and is now something else. You have no baseline to compare against. You have no measurement. You have a feeling.

## What print() shows

```
[agent] Session 1... output looks reasonable
[agent] Session 2... output looks reasonable
[agent] Session 3... output looks reasonable
[agent] Session 4... output looks reasonable
[agent] Session 5... output looks reasonable
[agent] Session 6... output looks... different?
[agent] Hmm, that response was longer than usual.
[agent] But hey, it completed successfully. Moving on.
```

A feeling is not a measurement.

## What OCW reveals

```
$ ocw demo hallucination-drift

Alerts fired:
  ALERT drift_detected — demo-hallucination-drift

$ ocw drift
Agent: demo-hallucination-drift
Baseline: 5 sessions sampled

Dimension          Expected    Observed    Z-Score
─────────────────────────────────────────────────
input_tokens       1,000       50,000      ∞ (stddev=0)
output_tokens      200         10,000      ∞ (stddev=0)
tool_sequence      [search, summarize]  [fetch_url, parse_html, ...]  Jaccard=0.0

$ ocw alerts
drift_detected  WARNING  demo-hallucination-drift
  input_tokens: expected ~1000, observed 50000 (Z=inf)
  tool_sequence: Jaccard similarity 0.0 (threshold 0.4)
```

OCW builds a statistical baseline from your agent's first N sessions. When a new session deviates significantly — by Z-score on token counts, or Jaccard distance on tool sequences — it fires a `drift_detected` alert at session end.

## Try it yourself

```bash
pip install openclawwatch
ocw demo hallucination-drift
```

Then inspect:

```bash
ocw drift           # Z-scores and baseline stats
ocw alerts          # see the drift_detected alert
ocw traces          # compare sessions visually
```

## Enable drift detection

In `ocw.toml`:

```toml
[[agents]]
id = "my-agent"

[agents.drift]
enabled = true
baseline_sessions = 10   # sessions before baseline is computed
token_threshold = 2.0    # Z-score threshold for token anomalies
tool_sequence_diff = 0.4 # Jaccard distance threshold for tool sequences
```

## What OCW is

OCW is a local-first, zero-signup observability CLI for AI agents. It captures telemetry from your agent, stores it in a local DuckDB database, and gives you CLI commands to understand what actually happened.

**→ [github.com/Metabuilder-Labs/openclawwatch](https://github.com/Metabuilder-Labs/openclawwatch)**
