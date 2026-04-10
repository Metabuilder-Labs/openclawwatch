"""ocw mcp — start the stdio MCP server."""
from __future__ import annotations

from pathlib import Path

import click
import duckdb

from ocw.core.config import find_config_file, load_config


@click.command("mcp")
@click.pass_context
def cmd_mcp(ctx: click.Context) -> None:
    """Start the OCW MCP server (stdio transport for Claude Code)."""
    from ocw.mcp.server import mcp, init

    config_path = find_config_file()
    if config_path is not None:
        config = load_config(str(config_path))
        db_path = str(Path(config.storage.path).expanduser())
        ro_conn = duckdb.connect(db_path, read_only=True)
        init(ro_conn, config)
    # If no config: init is not called; tools return the no-config sentinel.

    mcp.run()
