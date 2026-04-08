# Manual Release Testing

Run through this sequence after a new release is published to PyPI to verify the release works end-to-end.

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

# 2. Install latest
pip3 install --upgrade openclawwatch
ocw --version

# 3. Onboard
ocw onboard

# 4. Run an example (no server — tests direct DuckDB write)
cd ~/openclawwatch
source .env.local
python3 examples/single_provider/anthropic_agent.py

# 5. Verify CLI
ocw status       # should show agent with cost > $0, tokens, completed status
ocw traces       # should show traces with span waterfall
ocw cost --since 1h   # should show cost breakdown by model

# 6. Start server (tests web UI + HTTP exporter)
ocw serve &
sleep 2

# 7. Run another example (tests SDK HTTP fallback)
python3 examples/single_provider/litellm_agent.py

# 8. Verify web UI
open http://127.0.0.1:7391/
# Check: Status page shows agent cards
# Check: Traces page shows span waterfall
# Check: Sidebar has SVG logo + opencla.watch styling (deep navy + blue accent)

# 9. Verify both agents show up
ocw status       # should show both agents (or at least spans from both runs)
ocw traces       # should show traces from both runs
ocw cost --since 1h   # model names should be clean (gpt-4o-mini, not openai/gpt-4o-mini)

# 10. Clean up
ocw stop
kill $(pgrep -f "ocw serve") 2>/dev/null
```

## What to look for

| Step | Pass criteria |
|------|--------------|
| 2 | Version matches the release being tested |
| 3 | Config created at `.ocw/config.toml`, ingest secret generated |
| 4 | Agent runs without errors, no DuckDB lock warnings |
| 5 | `ocw status` shows non-zero cost and tokens; `ocw traces` shows spans |
| 6 | Server starts, prints correct metrics URL (`:7391/metrics`) |
| 7 | Agent runs without "Could not set lock on file" error (HTTP fallback works) |
| 8 | Web UI loads, shows data, sidebar has SVG logo |
| 9 | CLI queries work while server is running (API fallback); model names are clean |
| 10 | `ocw stop` stops the server cleanly |
