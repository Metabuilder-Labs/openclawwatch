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
3. Opens `DuckDBBackend(config.storage.path)`
4. Holds one DB instance for the lifetime of the process

Does **not** call `ensure_initialised()` — that bootstraps OTel/TracerProvider, which the MCP server doesn't need (read-only, not emitting spans).

DuckDB supports concurrent readers, so this is safe even when `ocw serve` is also running against the same file.

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

Ten tools total — nine reads, one write.

### Self-monitoring

| Tool | Parameters | Returns |
|---|---|---|
| `get_status` | `agent_id?: str` | session status, cost today, input/output tokens, tool call count, error count, active alert count |
| `get_budget_headroom` | `agent_id: str` | daily/session budget limits, current spend, remaining headroom |

### Multi-agent dashboard

| Tool | Parameters | Returns |
|---|---|---|
| `list_agents` | — | all known agent IDs with status, cost today, active alert count |
| `get_cost_summary` | `agent_id?: str`, `since?: str`, `group_by?: str = "day"` | cost rows grouped by day/agent/model, running total |
| `list_alerts` | `agent_id?: str`, `severity?: str`, `unread?: bool = False` | alert history — type, severity, title, detail, timestamps |
| `list_traces` | `agent_id?: str`, `since?: str`, `limit?: int = 20` | recent traces — cost, duration, span count, status |
| `get_trace` | `trace_id: str` | full span waterfall with parent/child relationships |
| `get_tool_stats` | `agent_id?: str`, `since?: str` | per-tool call counts and avg duration |
| `get_drift_report` | `agent_id?: str` | baseline stats vs latest session |

### Write

| Tool | Parameters | Returns |
|---|---|---|
| `acknowledge_alert` | `alert_id: str` | confirmation dict or `{"error": ...}` |

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

The `StorageBackend` protocol does not expose an acknowledge method — this is consistent with other callers (e.g. `cmd_status.py`) that access `db.conn` directly for operations outside the protocol. The MCP server does the same:

```python
db.conn.execute(
    "UPDATE alerts SET acknowledged = true WHERE alert_id = $1",
    [alert_id],
)
```

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
