# Task 07 — CLI Commands
**Depends on:** Task 00 (foundation), Task 01 (StorageBackend interface).
**Parallel with:** Tasks 02–06, 08–11.
**Estimated scope:** Medium. (Lots of commands but each is straightforward.)

---

## What this task covers

All Click CLI commands except `ocw cost` (Task 03), `ocw alerts` (Task 04), and
`ocw drift` (Task 05). Specifically:

- `ocw/cli/main.py` — root Click group, global options, `ctx.obj` wiring
- `ocw/cli/cmd_onboard.py` — guided setup wizard
- `ocw/cli/cmd_status.py`
- `ocw/cli/cmd_traces.py` — both `ocw traces` (list) and `ocw trace <id>` (detail)
- `ocw/cli/cmd_tools.py`
- `ocw/cli/cmd_export.py`
- `ocw/cli/cmd_serve.py`
- `ocw/cli/cmd_doctor.py`

---

## Deliverables

### `ocw/cli/main.py`

```python
import click
import json
from ocw.core.config import load_config
from ocw.core.db import open_db


@click.group()
@click.option("--config", "config_path", default=None, envvar="OCW_CONFIG",
              help="Config file path (default: auto-discover)")
@click.option("--json", "output_json", is_flag=True,
              help="Output machine-readable JSON")
@click.option("--no-color", is_flag=True)
@click.option("--db", "db_path", default=None, help="Database path override")
@click.option("--agent", default=None, help="Filter to specific agent_id")
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def cli(ctx, config_path, output_json, no_color, db_path, agent, verbose):
    """ocw — local-first observability for AI agents."""
    ctx.ensure_object(dict)
    config = load_config(config_path)
    if db_path:
        config.storage.path = db_path
    db = open_db(config.storage)
    ctx.obj["config"]      = config
    ctx.obj["db"]          = db
    ctx.obj["output_json"] = output_json
    ctx.obj["no_color"]    = no_color
    ctx.obj["agent"]       = agent
    ctx.obj["verbose"]     = verbose
    if no_color:
        from rich import reconfigure
        reconfigure(no_color=True)


# Register all subcommands
from ocw.cli.cmd_onboard import cmd_onboard
from ocw.cli.cmd_status  import cmd_status
from ocw.cli.cmd_traces  import cmd_traces, cmd_trace
from ocw.cli.cmd_cost    import cmd_cost
from ocw.cli.cmd_alerts  import cmd_alerts
from ocw.cli.cmd_drift   import cmd_drift
from ocw.cli.cmd_tools   import cmd_tools
from ocw.cli.cmd_export  import cmd_export
from ocw.cli.cmd_serve   import cmd_serve
from ocw.cli.cmd_doctor  import cmd_doctor

cli.add_command(cmd_onboard, name="onboard")
cli.add_command(cmd_status,  name="status")
cli.add_command(cmd_traces,  name="traces")
cli.add_command(cmd_trace,   name="trace")
cli.add_command(cmd_cost,    name="cost")
cli.add_command(cmd_alerts,  name="alerts")
cli.add_command(cmd_drift,   name="drift")
cli.add_command(cmd_tools,   name="tools")
cli.add_command(cmd_export,  name="export")
cli.add_command(cmd_serve,   name="serve")
cli.add_command(cmd_doctor,  name="doctor")
```

---

### `ocw/cli/cmd_onboard.py`

Interactive setup wizard. Uses `click.prompt()` — not Rich — for user input.

```
ocw onboard [--agent AGENT_ID] [--budget FLOAT]
            [--install-daemon | --no-daemon]
            [--force]
```

Steps:
1. Check if a config file already exists. If yes and `--force` not given, print location
   and exit with instructions to use `--force` to overwrite.
2. Prompt for agent ID (skip if `--agent` provided).
3. Prompt for daily budget in USD (skip if `--budget` provided; 0 = no limit).
4. Generate a random ingest secret (`secrets.token_hex(32)`).
5. Ask whether to install background daemon (skip if `--install-daemon` or `--no-daemon`).
   - If yes: call `_install_daemon()` — see daemon installation below.
   - If no: print note that `ocw serve` must be run manually for real-time alerts on
     background agents.
6. Write `ocw.toml` to `.ocw/config.toml` in current directory.
7. Print summary.

Daemon installation (`_install_daemon()`):
- **macOS**: write a launchd plist to `~/Library/LaunchAgents/com.openclawwatch.serve.plist`
  then run `launchctl load <plist_path>`.
- **Linux**: write a systemd user service file to
  `~/.config/systemd/user/openclawwatch.service` then run
  `systemctl --user enable --now openclawwatch`.
- **Other**: print "Background daemon not supported on this platform. Run `ocw serve`
  manually."
- Log all daemon steps. If installation fails, print the error and continue (don't abort
  the whole onboard).

---

### `ocw/cli/cmd_status.py`

```
ocw status [--agent AGENT_ID] [--json]
```

For each agent (or filtered agent):
- Fetch the most recent active or recently-ended session
- Fetch today's cost total from DB
- Fetch active (unacknowledged) alerts
- Print status block

Exit code: 0 if no active alerts, 1 if any active alerts.

Human output:
```
● my-email-agent   active   (4m 23s)

  Cost today:     $0.034 / $5.00 limit
  Tokens:         12,447 in · 3,821 out
  Tool calls:     47  (2 failed)
  Active session: sess-a1b2c3

  ⚠  send_email called 3 times in last 10 min
  ✓  No retry loops detected
  ✓  Schema valid on all tool outputs
```

---

### `ocw/cli/cmd_traces.py`

```
ocw traces [--agent] [--since] [--limit] [--type] [--status] [--json]
ocw trace TRACE_ID [--json]
```

`ocw traces` lists traces using Rich table. Columns: TRACE ID | AGENT | TYPE | DUR | COST | STATUS

`ocw trace <id>` shows the full span waterfall for a single trace:
- Parent span at top, child spans indented
- Each span: name, duration, attributes (key: value format), any alerts that fired
- Box-drawing characters: `┌─`, `├─`, `└─`, `│`

---

### `ocw/cli/cmd_tools.py`

```
ocw tools [--agent] [--since] [--name TOOL_NAME] [--json]
```

Columns: TOOL | CALLS | ERRORS | AVG DUR | FLAGGED | LAST CALLED

---

### `ocw/cli/cmd_export.py`

```
ocw export [--agent] [--since]
           [--format json|csv|otlp|openevals]
           [--output PATH]
```

**`--format json`**: NDJSON, one span per line.

**`--format csv`**: CSV with header row. Columns: span_id, trace_id, agent_id, name,
start_time, duration_ms, cost_usd, input_tokens, output_tokens, status_code.

**`--format otlp`**: Send spans to the configured `export.otlp.endpoint` via OTLP/HTTP.
Requires `export.otlp.enabled = true` or `--endpoint` override flag.

**`--format openevals`**: Output JSON array of trace objects in OpenAI-style message list
format. Each trace becomes:
```json
{
  "trace_id": "...",
  "agent_id": "...",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "", "tool_calls": [...]},
    {"role": "tool", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```
This format is directly consumable by openevals and agentevals trajectory evaluators.

---

### `ocw/cli/cmd_serve.py`

```
ocw serve [--host HOST] [--port PORT] [--reload]
```

Starts the FastAPI + uvicorn server (Task 08) and the Prometheus metrics endpoint.
Blocks until Ctrl+C. Prints startup URLs.

Also schedules the retention cleanup job via apscheduler (run daily at midnight).

---

### `ocw/cli/cmd_doctor.py`

```
ocw doctor [--json]
```

Runs all health checks and prints results. Exit code:
- 0: all clean
- 1: warnings only
- 2: one or more errors

Checks to implement (in order):

| Check | Pass condition | Level |
|---|---|---|
| Config file found and valid | File exists and parses without error | ERROR if missing |
| DuckDB file writable | Can open connection successfully | ERROR |
| Ingest secret set | `security.ingest_secret` is non-empty | WARNING |
| Prometheus configured | `export.prometheus.enabled = true` | INFO |
| Schema validation vs capture | If any agent has output_schema, capture.tool_outputs must be true | WARNING |
| Drift configured but inactive | Configured but fewer than baseline_sessions completed | WARNING |
| Webhook URL security | Non-local, non-HTTPS webhook URLs | WARNING |
| Webhook domain allowlist | URL not in `security.webhook_allowed_domains` (if list is set) | ERROR |
| Integrations installed | List any installed Integration instances (via `Integration.installed`) | INFO |

---

## Global exit code rule

```python
# In every command that queries for active alerts:
active_alerts = [a for a in alerts if not a.acknowledged and not a.suppressed]
ctx.exit(1 if active_alerts else 0)
```

---

## Tests to write

**`tests/integration/test_cli.py`** using `click.testing.CliRunner`:

```python
def test_status_exits_0_when_no_alerts()
def test_status_exits_1_when_active_alerts()
def test_traces_json_output_is_valid_json()
def test_trace_id_shows_span_waterfall()
def test_export_openevals_format_is_message_list()
def test_doctor_exits_0_when_config_is_clean()
def test_doctor_exits_1_when_warnings_present()
def test_doctor_exits_2_when_errors_present()
def test_doctor_warns_on_schema_without_capture()
def test_since_flag_parses_all_formats()
```

Use an `InMemoryBackend` fixture and test config for all integration tests.