# CLI Reference

All commands support `--json` for machine-readable output. Commands that query alerts use exit code 1 if active (unacknowledged, unsuppressed) alerts exist.

## Global options

```
--config PATH    Override config file path
--db PATH        Override database path
--agent ID       Filter to a specific agent
--json           Output in JSON format
--no-color       Disable color output
-v, --verbose    Verbose output
```

## Commands

### `ocw onboard`

Guided setup wizard. Creates config file, generates ingest secret, optionally installs background daemon.

```bash
ocw onboard                  # interactive setup
ocw onboard --claude-code    # configure Claude Code telemetry
ocw onboard --no-daemon      # skip daemon installation
ocw onboard --budget 5.00    # set daily budget during setup
ocw onboard --force          # overwrite existing config
```

### `ocw doctor`

Health check — validates config, database connectivity, ingest secret, and alert channel reachability.

```bash
ocw doctor
```

Exit codes: 0 = healthy, 1 = warnings, 2 = errors.

### `ocw status`

Current agent state: session info, cost, token counts, active alerts.

```bash
ocw status
ocw status --agent my-agent
```

### `ocw traces`

Trace listing with span waterfall view.

```bash
ocw traces
ocw traces --since 1h
ocw trace <trace-id>         # full span waterfall for a single trace
```

### `ocw cost`

Cost breakdown by agent, model, day, or tool.

```bash
ocw cost
ocw cost --since 7d
ocw cost --group-by model    # group by model
ocw cost --group-by day      # group by day
ocw cost --group-by agent    # group by agent
ocw cost --group-by tool     # group by tool
```

### `ocw alerts`

Alert history with severity and type filtering.

```bash
ocw alerts
ocw alerts --severity critical
ocw alerts --type sensitive_action
ocw alerts --since 1h
ocw alerts --unread           # only unacknowledged alerts
```

### `ocw budget`

View and set daily/session cost limits.

```bash
ocw budget                                    # view all budgets
ocw budget --agent my-agent --daily 5.00      # set daily limit
ocw budget --agent my-agent --session 1.00    # set session limit
```

### `ocw drift`

Behavioral drift report: baseline vs latest session Z-scores.

```bash
ocw drift
ocw drift --agent my-agent
```

Exit code 1 if any agent has drifted (useful for CI gating).

### `ocw tools`

Tool call summary: call counts, average duration, error rates.

```bash
ocw tools
ocw tools --since 1h
```

### `ocw export`

Export spans in multiple formats.

```bash
ocw export --format json
ocw export --format csv --output spans.csv
ocw export --format otlp
ocw export --format openevals --output traces.json
```

### `ocw mcp`

Start the MCP server (stdio transport for Claude Code). Registered automatically by `ocw onboard --claude-code`.

```bash
ocw mcp
```

### `ocw serve`

Start the local REST API server with web UI and Prometheus metrics.

```bash
ocw serve                    # foreground
ocw serve &                  # background
ocw serve --host 0.0.0.0    # bind to all interfaces
ocw serve --port 8080        # custom port
ocw serve --reload           # auto-reload for development
```

Web UI: `http://127.0.0.1:7391/`
API docs: `http://127.0.0.1:7391/docs`
Metrics: `http://127.0.0.1:7391/metrics`

### `ocw stop`

Stop the background daemon or `ocw serve` process.

```bash
ocw stop
```

### `ocw uninstall`

Remove all OCW data, config, daemon, MCP registration, and env vars.

```bash
ocw uninstall          # interactive confirmation
ocw uninstall --yes    # skip confirmation
```
