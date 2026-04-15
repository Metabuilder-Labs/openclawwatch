# Manual Release Testing

Run through this sequence after a new release is published to PyPI to verify the release works end-to-end.

## Prerequisites

- `ANTHROPIC_API_KEY` set (for Anthropic examples)
- `OPENAI_API_KEY` set (for LiteLLM/OpenAI examples)
- Both should be in `~/openclawwatch/.env.local` and sourced before running

## Test sequence

```bash
# 1. Clean slate
ocw uninstall --yes 2>/dev/null
rm -rf ~/.ocw ~/.config/ocw .ocw

# 2. Install latest
pip3 install --upgrade openclawwatch
ocw --version

# 3. Onboard
# Note: daemon auto-installs by default (use --no-daemon to skip).
# Budget prompt appears — enter a value or press enter for default.
ocw onboard

# 4. Stop daemon before manual testing (daemon auto-started by onboard)
ocw stop

# 5. Run an example (no server — tests direct DuckDB write)
cd ~/openclawwatch
source .env.local
python3 examples/single_provider/anthropic_agent.py

# 6. Verify CLI (direct DuckDB, no server)
ocw status       # should show agent with cost > $0, tokens, completed status
ocw traces       # should show traces with span waterfall
ocw cost --since 1h   # should show cost breakdown by model (not $0.000000)
ocw budget       # should show budget table with configured limits
ocw alerts       # should show alert history (may be empty)

# 7. Start server (tests web UI + HTTP exporter)
ocw serve &
sleep 2

# 8. Run another example (tests SDK HTTP fallback)
python3 examples/single_provider/litellm_agent.py

# 9. Verify web UI
open http://127.0.0.1:7391/
# Check: Status page shows agent cards with cost, tokens
# Check: Traces page shows span waterfall
# Check: Cost page shows non-zero USD values
# Check: Sidebar has SVG logo + opencla.watch styling (deep navy + blue accent)

# 10. Verify both agents show up
ocw status       # should show both agents
ocw traces       # should show traces from both runs
ocw cost --since 1h   # model names should be clean (gpt-4o-mini, not openai/gpt-4o-mini)

# 11. Clean up
ocw stop
```

## Claude Code integration (if applicable)

```bash
# After step 3 above, also test:
ocw onboard --claude-code
# Should: not prompt for daemon, write config to ~/.config/ocw/config.toml,
#         write settings to ~/.claude/settings.json,
#         register MCP server with Claude Code (if claude CLI is installed)

# Verify settings written
cat ~/.claude/settings.json | python3 -m json.tool
# Should contain OTEL_LOGS_EXPORTER, OTEL_EXPORTER_OTLP_ENDPOINT, etc.

# Re-run to test secret resync (should not crash)
ocw onboard --claude-code --budget 5
```

## What to look for

| Step | Pass criteria |
|------|--------------|
| 2 | Version matches the release being tested |
| 3 | Config created at `.ocw/config.toml`, ingest secret generated, daemon installed |
| 5 | Agent runs without errors, no DuckDB lock warnings |
| 6 | `ocw status` shows non-zero cost and tokens; `ocw cost` shows real USD values (not $0.000000) |
| 7 | Server starts on `:7391`, prints correct metrics URL |
| 8 | Agent runs without "Could not set lock on file" error (HTTP fallback works) |
| 9 | Web UI loads, shows data, sidebar has SVG logo |
| 10 | CLI queries work while server is running (API fallback); model names are clean |
| 11 | `ocw stop` stops the server cleanly |
