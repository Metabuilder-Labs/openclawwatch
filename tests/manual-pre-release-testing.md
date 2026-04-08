# Pre-Release Testing

Run through this sequence to test a branch before merging and cutting a release. This uses a local editable install so changes take effect immediately without publishing to PyPI.

## Prerequisites

- `ANTHROPIC_API_KEY` set (for Anthropic examples)
- `OPENAI_API_KEY` set (for LiteLLM/OpenAI examples)
- Both should be in `~/openclawwatch/.env.local` and sourced before running

## Test sequence

```bash
# 1. Clean slate
ocw stop 2>/dev/null
kill $(pgrep -f "ocw serve") 2>/dev/null
rm -rf ~/.ocw
rm -rf .ocw

# 2. Check out the branch to test
cd ~/openclawwatch
git fetch origin
git checkout <branch-name>

# 3. Install locally (editable — uses local files, no pip publish needed)
pip3 install -e .
ocw --version

# 4. Onboard fresh
ocw onboard

# 5. Populate test data — simulated (free, no API keys)
python3 examples/alerts_and_drift/sensitive_actions_demo.py
python3 examples/alerts_and_drift/budget_breach_demo.py
python3 examples/alerts_and_drift/drift_demo.py

# 6. Populate test data — real API calls
source .env.local
python3 examples/single_provider/anthropic_agent.py
python3 examples/single_provider/litellm_agent.py

# 7. Verify CLI (direct DuckDB, no server)
ocw status
ocw traces
ocw cost --since 1h
ocw alerts
ocw drift

# 8. Start server
ocw serve &
sleep 2

# 9. Run one more example (tests SDK HTTP fallback while server holds DB lock)
python3 examples/single_provider/anthropic_agent.py

# 10. Verify web UI — Status
open http://127.0.0.1:7391/
# [ ] Multiple agent cards visible
# [ ] Each card shows cost, tokens, tool calls, duration
# [ ] "Last seen" time shown
# [ ] Cards are clickable (navigate to filtered traces)
# [ ] Sidebar: Open(white)Claw(blue)Watch(white) with SVG icon
# [ ] Sidebar footer: API docs + GitHub as proper nav links

# 11. Verify web UI — Traces
# [ ] Agent name is first column, no Trace ID column
# [ ] Type shows friendly names (LLM Call, Tool Call, Agent Run)
# [ ] Click chevron (→) visible in last column
# [ ] Click a trace — waterfall renders with correct nesting
# [ ] Span bars have hover glow effect
# [ ] Fast tool calls (0ms) still have visible bars
# [ ] "Click a span for details" hint appears
# [ ] Click a span — detail panel shows provider, model, tokens, cost
# [ ] Friendly span name as heading, raw name in dim text below

# 12. Verify web UI — Cost
# [ ] Summary row shows total cost, input tokens, output tokens
# [ ] Group-by selector works (day / agent / model / tool)
# [ ] Redundant columns hidden based on group-by selection
# [ ] Costs show real USD values (not $0.000000 — requires pricing fix)

# 13. Verify web UI — Alerts
# [ ] Alerts table populated from sensitive_actions and budget_breach demos
# [ ] Friendly type names (Sensitive Action, Daily Budget, etc.)
# [ ] Severity badges with correct colors (critical=red, warning=yellow, info=blue)
# [ ] ▸/▾ expand toggle on rows, click shows detail JSON

# 14. Verify web UI — Drift
# [ ] At least one agent shows baseline data
# [ ] Metric table shows baseline mean ± stddev, latest value, Z-score
# [ ] Pass badges are green, drift badges are red
# [ ] Threshold shown in header (2.0σ)

# 15. Verify CLI works while server is running (API fallback)
ocw status
ocw traces
ocw cost --since 1h

# 16. Clean up
ocw stop
kill $(pgrep -f "ocw serve") 2>/dev/null
```

## Quick test (skip web UI — just verify core)

For smaller changes that don't touch the UI:

```bash
ocw stop 2>/dev/null
kill $(pgrep -f "ocw serve") 2>/dev/null
rm -rf ~/.ocw .ocw
cd ~/openclawwatch
git checkout <branch-name>
pip3 install -e .
ocw onboard
source .env.local
python3 examples/single_provider/anthropic_agent.py
ocw status && ocw traces && ocw cost --since 1h
pytest tests/unit/ tests/synthetic/ tests/agents/ tests/integration/
ruff check ocw/
```

## What to look for

| Step | Pass criteria |
|------|--------------|
| 3 | Installs without errors, version shows expected value |
| 4 | Config created, ingest secret generated |
| 5 | Simulated demos run without errors, no API keys needed |
| 6 | Real examples run, no DuckDB lock errors |
| 7 | CLI shows data: cost > $0, tokens counted, traces visible, alerts fired, drift baseline built |
| 8 | Server starts, prints correct metrics URL (`:7391/metrics`) |
| 9 | No "Could not set lock on file" error — HTTP fallback works |
| 10 | Status page: multiple agents, correct data, clickable cards |
| 11 | Traces: friendly names, waterfall renders, span detail works |
| 12 | Cost: real USD values, group-by works, no redundant columns |
| 13 | Alerts: populated from demos, friendly names, expand works |
| 14 | Drift: baseline shown, Z-scores calculated, pass/drift badges correct |
| 15 | CLI queries work while server is running (no lock errors) |

## Switching back to main after testing

```bash
ocw stop 2>/dev/null
kill $(pgrep -f "ocw serve") 2>/dev/null
git checkout main
pip3 install -e .
```