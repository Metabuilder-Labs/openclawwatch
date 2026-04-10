# OCW MCP Server Design

**Date:** 2026-04-11  
**Status:** Approved  
**Scope:** New `ocw mcp` command — stdio MCP server exposing OCW observability data to Claude Code

---

## Problem

OCW currently integrates with Claude Code only via CLI commands in each repo. This is one-way: Claude fires commands but gets no structured data back. A Model Context Protocol (MCP) server turns OCW into a two-way integration — Claude can proactively query agent status, cost, alerts, and drift without the user asking.

Two consumers:
1. **Claude self-monitoring** — Claude checks its own session state before/during expensive operations
2. **Human dashboard** — a user asks Claude to summarize all their agent sessions

---

## Architecture

### Approach chosen: Direct library mode (Option A)

A new `ocw mcp` CLI command starts a **stdio MCP server** that imports the OCW Python package directly and queries DuckDB. No dependency on `ocw serve` — works anywhere `openclawwatch` is installed.

Rejected alternatives:
- *Separate process calling REST API* — requires `ocw serve` to be running; breaks local-first guarantee
- *MCP over SSE in `ocw serve`* — same problem; server must be running first

### File layout

```
ocw/
  mcp/
    __init__.py
    server.py        # fastmcp server + all tool definitions (~200 lines)
  cli/
    cmd_mcp.py       # `ocw mcp` entry point
```

`cmd_mcp.py` is registered as a subcommand in `ocw/cli/main.py`, following the same pattern as `cmd_serve.py`.

### Dependency

`fastmcp` added to `pyproject.toml` as an optional dependency group:

```toml
[project.optional-dependencies]
mcp = ["fastmcp"]
```

Install: `pip install openclawwatch[mcp]`. Not included in the default install — keeps base footprint small.

### Bootstrap

On startup, the server:
1. Calls `find_config_file()` to discover `ocw.toml`
2. Loads `OcwConfig` from that path
3. Opens the DuckDB file in **read-only mode**: `duckdb.connect(str(Path(config.storage.path).expanduser()), read_only=True)`
4. Holds that read-only connection for the lifetime of the process

Does **not** use `DuckDBBackend` directly — that class opens a read-write connection and will block when `ocw serve` already holds the file lock. `bootstrap.py:75-77` confirms this collision happens in production. Read-only mode avoids it entirely.

Does **not** call `ensure_initialised()` — that bootstraps OTel/TracerProvider, which the MCP server doesn't need (not emitting spans).

**`acknowledge_alert` exception:** the one write operation opens a short-lived separate read-write connection, executes the UPDATE, and closes it immediately. This is safe because `ocw serve`'s write connection is idle while the UPDATE runs (DuckDB serialises writers).

### Claude Code registration

```bash
claude mcp add ocw -- ocw mcp
```

Or manually in `~/.claude.json`:
```json
{
  "mcpServers": {
    "ocw": {
      "command": "ocw",
      "args": ["mcp"]
    }
  }
}
```

---

## Tools

Twelve tools total — ten reads, two writes.

### Self-monitoring

| Tool | Parameters | Returns |
|---|---|---|
| `get_status` | `agent_id?: str` | session status, cost today, input/output tokens, tool call count, error count, active alert count |
| `get_budget_headroom` | `agent_id: str` | daily/session budget limits, current spend, remaining headroom |

### Multi-agent dashboard

| Tool | Parameters | Returns |
|---|---|---|
| `list_agents` | — | historical agent summary — all known agent IDs with `last_seen` time and lifetime cost (JOIN to spans table) |
| `list_active_sessions` | — | one row per currently running session across all agents — agent_id repeated if multiple sessions share the same project |
| `get_cost_summary` | `agent_id?: str`, `since?: str`, `group_by?: str = "day"` | cost rows grouped by day/agent/model, running total |
| `list_alerts` | `agent_id?: str`, `severity?: str`, `unread?: bool = False` | alert history — type, severity, title, detail, timestamps |
| `list_traces` | `agent_id?: str`, `since?: str`, `limit?: int = 20` | recent traces — cost, duration, span count, status |
| `get_trace` | `trace_id: str` | full span waterfall with parent/child relationships |
| `get_tool_stats` | `agent_id?: str`, `since?: str` | per-tool call counts and avg duration |
| `get_drift_report` | `agent_id?: str` | baseline stats vs latest session |

`list_active_sessions` is the primary dashboard tool. It shows one row per running session — if a project has 4 parallel Claude Code windows, you see 4 rows all with the same `agent_id`. `list_agents` is for historical lookups, not live status.

Both `list_active_sessions` and `list_agents` use the read-only `db.conn` directly (`SELECT * FROM sessions WHERE status = 'active'` and `SELECT agents.*, SUM(spans.cost_usd) FROM agents LEFT JOIN spans ...`) — these queries are not in the `StorageBackend` protocol.

### Write

| Tool | Parameters | Returns |
|---|---|---|
| `acknowledge_alert` | `alert_id: str` | confirmation dict or `{"error": ...}` |
| `setup_project` | `agent_id?: str` | writes `.claude/settings.json` in cwd with `OTEL_RESOURCE_ATTRIBUTES=service.name=<agent_id>`, adds agent entry to OCW config. Returns `{"agent_id": ..., "settings_path": ..., "warning"?: ...}` |

`setup_project` derives the agent ID automatically from the git remote URL or folder name (same logic as `ocw onboard --claude-code`), or accepts an explicit `agent_id` override. It only configures the **client side** (which `service.name` this project reports). It does not start `ocw serve` — if no daemon is running, telemetry won't flow. The tool warns if the global OTLP endpoint is not yet configured in `~/.claude/settings.json`.

**cwd assumption:** writes to `Path.cwd() / ".claude" / "settings.json"`. Claude Code spawns MCP server subprocesses from the project's working directory, so `Path.cwd()` is the project root. This is the correct behaviour in all normal usage. An optional `project_path: str` parameter overrides `cwd` for edge cases (e.g. running from a subdirectory).

`since` parameters accept human-readable strings (`"24h"`, `"7d"`, `"2026-04-01"`) parsed by the existing `parse_since()` utility in `ocw/utils/time_parse.py`.

---

## Data Flow

```
Claude Code
  → stdio
  → fastmcp server (ocw/mcp/server.py)
  → DuckDBBackend.get_*()  (or db.conn for acknowledge)
  → DuckDB file (~/.config/ocw/ocw.duckdb or configured path)
  → serialized dict
  → fastmcp
  → stdio
  → Claude Code
```

---

## Error Handling

Three cases — MCP servers must never crash on tool errors:

1. **No config at startup** — server starts successfully. Every tool returns `{"error": "No OCW config found. Run 'ocw onboard' to set up."}`.

2. **DB query error** — caught per-tool, returned as `{"error": "<message>"}`. Other tools remain functional.

3. **`acknowledge_alert` on unknown ID** — returns `{"error": "Alert <id> not found"}`. No silent no-ops.

### `acknowledge_alert` write path

The `StorageBackend` protocol does not expose an acknowledge method. The MCP server opens a short-lived read-write connection for this one operation, consistent with the pattern used in `cmd_status.py`:

```python
db_path = Path(config.storage.path).expanduser()
with duckdb.connect(str(db_path)) as write_conn:
    result = write_conn.execute(
        "SELECT alert_id FROM alerts WHERE alert_id = $1", [alert_id]
    ).fetchone()
    if result is None:
        return {"error": f"Alert {alert_id} not found"}
    write_conn.execute(
        "UPDATE alerts SET acknowledged = true WHERE alert_id = $1",
        [alert_id],
    )
```

This connection is opened and closed within the tool call, minimising the window during which both the MCP server and `ocw serve` hold write connections simultaneously.

---

## Testing

**New file:** `tests/unit/test_mcp_server.py`

**Approach:** Instantiate `InMemoryBackend`, call each tool handler function directly (bypassing the MCP protocol). Assert returned dict shape and values. Follows the same pattern as existing CLI integration tests.

**Coverage:**
- Each read tool returns expected shape with populated data
- Each read tool with no data returns empty collections (not errors)
- `acknowledge_alert` with valid ID sets `acknowledged = True`
- `acknowledge_alert` with unknown ID returns `{"error": ...}`
- No-config path: tool handlers return the error sentinel

**Note on `acknowledge_alert` test:** This tool uses `db.conn` directly (same pattern as `cmd_status.py`). If `InMemoryBackend` exposes `conn` (it's a DuckDB in-memory instance), use it directly. If not, open a real `DuckDBBackend(":memory:")` for just that test case.

**CI:** Test file runs in `tests/unit/` — already in the CI matrix. The CI workflow install step adds `pip install -e ".[dev,mcp]"` to pull in `fastmcp` for tests.

---

## Out of Scope

- Budget writes (Claude setting its own limits) — human decision, excluded by design
- Alert suppression — Claude can only acknowledge, not suppress
- Any REST API changes — MCP server is additive, nothing existing is modified
- TypeScript SDK changes — out of scope
