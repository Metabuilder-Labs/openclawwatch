# Pre-Release Testing

Run through this sequence to test a branch before merging and cutting a release. This uses a local editable install so changes take effect immediately without publishing to PyPI.

## Prerequisites

- `ANTHROPIC_API_KEY` set (for Anthropic examples)
- `OPENAI_API_KEY` set (for LiteLLM/OpenAI examples)
- Both should be in `~/openclawwatch/.env.local` and sourced before running

## Test sequence

```bash
# 1. Clean slate
ocw uninstall --yes 2>/dev/null
rm -rf ~/.ocw ~/.config/ocw .ocw

# 2. Check out the branch to test
cd ~/openclawwatch
git fetch origin
git checkout <branch-name>

# 3. Install locally (editable — uses local files, no pip publish needed)
pip3 install -e ".[dev,mcp]"
ocw --version

# 4. Run automated tests first
pytest tests/unit/ tests/synthetic/ tests/agents/ tests/integration/
ruff check ocw/

# 5. Onboard fresh
# Note: daemon auto-installs by default (use --no-daemon to skip).
ocw onboard

# 6. Stop daemon before manual testing (daemon auto-started by onboard)
ocw stop

# 7. Populate test data — simulated (free, no API keys)
python3 examples/alerts_and_drift/sensitive_actions_demo.py
python3 examples/alerts_and_drift/budget_breach_demo.py
python3 examples/alerts_and_drift/drift_demo.py

# 8. Populate test data — real API calls
source .env.local
python3 examples/single_provider/anthropic_agent.py
python3 examples/single_provider/litellm_agent.py

# 9. Verify CLI (direct DuckDB, no server)
ocw status        # agents visible with cost > $0, tokens counted
ocw traces        # spans from all runs
ocw cost --since 1h   # real USD values, not $0.000000
ocw alerts        # alerts from sensitive_actions and budget_breach demos
ocw drift         # baseline built from drift_demo sessions
ocw budget        # budget table with configured limits

# 10. Start server
# Note: must stop daemon first (step 6) or this will fail with "Address already in use"
ocw serve &
sleep 2

# 11. Run one more example (tests SDK HTTP fallback while server holds DB lock)
python3 examples/single_provider/anthropic_agent.py

# 12. Verify web UI — Status
open http://127.0.0.1:7391/
# [ ] Multiple agent cards visible
# [ ] Each card shows cost, tokens, tool calls, duration
# [ ] "Last seen" time shown
# [ ] Cards are clickable (navigate to filtered traces)
# [ ] Sidebar: Open(white)Claw(blue)Watch(white) with SVG icon
# [ ] Sidebar footer: API docs + GitHub as proper nav links

# 13. Verify web UI — Traces
# [ ] Agent name is first column, no Trace ID column
# [ ] Type shows friendly names (LLM Call, Tool Call, Agent Run)
# [ ] Click chevron (→) visible in last column
# [ ] Click a trace — waterfall renders with correct nesting
# [ ] Span bars have hover glow effect
# [ ] Fast tool calls (0ms) still have visible bars
# [ ] "Click a span for details" hint appears
# [ ] Click a span — detail panel shows provider, model, tokens, cost
# [ ] Friendly span name as heading, raw name in dim text below

# 14. Verify web UI — Cost
# [ ] Summary row shows total cost, input tokens, output tokens
# [ ] Group-by selector works (day / agent / model / tool)
# [ ] Redundant columns hidden based on group-by selection
# [ ] Costs show real USD values (not $0.000000)

# 15. Verify web UI — Alerts
# [ ] Alerts table populated from sensitive_actions and budget_breach demos
# [ ] Friendly type names (Sensitive Action, Daily Budget, etc.)
# [ ] Severity badges with correct colors (critical=red, warning=yellow, info=blue)
# [ ] ▸/▾ expand toggle on rows, click shows detail JSON

# 16. Verify web UI — Drift
# [ ] At least one agent shows baseline data
# [ ] Metric table shows baseline mean ± stddev, latest value, Z-score
# [ ] Pass badges are green, drift badges are red
# [ ] Threshold shown in header (2.0σ)

# 17. Verify CLI works while server is running (API fallback)
ocw status
ocw traces
ocw cost --since 1h

# 18. Clean up
ocw stop
```

## Claude Code integration (if applicable)

```bash
# Test after step 5:
ocw onboard --claude-code
# Should: write config to ~/.config/ocw/config.toml (global, not project-local),
#         write settings to ~/.claude/settings.json,
#         register MCP server if claude CLI available,
#         auto-install daemon

# Verify no crash on re-run (secret resync)
ocw onboard --claude-code --budget 5

# Verify MCP server starts
ocw mcp --help
```

## Quick test (skip web UI — just verify core)

For smaller changes that don't touch the UI:

```bash
ocw uninstall --yes 2>/dev/null
rm -rf ~/.ocw ~/.config/ocw .ocw
cd ~/openclawwatch
git checkout <branch-name>
pip3 install -e ".[dev,mcp]"
ocw onboard --no-daemon
source .env.local
python3 examples/single_provider/anthropic_agent.py
ocw status && ocw traces && ocw cost --since 1h
# Verify: cost > $0, tokens counted, traces visible
pytest tests/unit/ tests/synthetic/ tests/agents/ tests/integration/
ruff check ocw/
```

## What to look for

| Step | Pass criteria |
|------|--------------|
| 3 | Installs without errors, version shows expected value |
| 4 | All tests pass, no lint errors |
| 5 | Config created, ingest secret generated, daemon installed |
| 7 | Simulated demos run without errors, no API keys needed |
| 8 | Real examples run, no DuckDB lock errors |
| 9 | CLI shows data: cost > $0, tokens counted, traces visible, alerts fired, drift baseline built |
| 10 | Server starts on `:7391`, prints correct metrics URL |
| 11 | No "Could not set lock on file" error — HTTP fallback works |
| 12-16 | Web UI views render correctly with real data |
| 17 | CLI queries work while server is running (no lock errors) |

## Switching back to main after testing

```bash
ocw stop
ocw uninstall --yes 2>/dev/null
git checkout main
pip3 install -e ".[dev,mcp]"
```
