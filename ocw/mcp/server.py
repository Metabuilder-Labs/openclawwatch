"""OCW MCP server — exposes observability data to Claude Code via stdio."""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("ocw")

# Module-level state initialised by init() or cmd_mcp.py
_ro_conn = None   # duckdb read-only connection
_config = None    # OcwConfig
_ro_db = None     # _ReadOnlyDB wrapping _ro_conn


def init(ro_conn, config) -> None:
    """Inject DB connection and config. Called by cmd_mcp.py and tests."""
    global _ro_conn, _config, _ro_db
    _ro_conn, _config = ro_conn, config
    _ro_db = _ReadOnlyDB(ro_conn) if ro_conn is not None else None


def _no_config() -> dict:
    return {"error": "No OCW config found. Run 'ocw onboard --claude-code' to set up."}


class _ReadOnlyDB:
    """Wraps a read-only duckdb connection to satisfy StorageBackend protocol methods."""
    def __init__(self, conn):
        self.conn = conn

    def get_cost_summary(self, filters):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_cost_summary(self, filters)

    def get_alerts(self, filters):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_alerts(self, filters)

    def get_traces(self, filters):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_traces(self, filters)

    def get_trace_spans(self, trace_id):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_trace_spans(self, trace_id)

    def get_tool_calls(self, agent_id, since, tool_name):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_tool_calls(self, agent_id, since, tool_name)

    def get_baseline(self, agent_id):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_baseline(self, agent_id)

    def get_completed_sessions(self, agent_id, limit):
        from ocw.core.db import DuckDBBackend
        return DuckDBBackend.get_completed_sessions(self, agent_id, limit)
