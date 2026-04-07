from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

import click

from ocw.utils.formatting import console


@click.command("stop")
@click.pass_context
def cmd_stop(ctx: click.Context) -> None:
    """Stop the ocw serve daemon or background process."""
    plist_path = Path.home() / "Library/LaunchAgents/com.openclawwatch.serve.plist"

    # Try launchd first
    if plist_path.exists():
        result = subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print("[green]ocw serve stopped.[/green] (launchd daemon unloaded)")
            return
        # If unload failed, the daemon may not have been loaded — fall through

    # Try finding ocw serve process
    pid = _find_serve_pid()
    if pid:
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]ocw serve stopped.[/green] (PID {pid})")
        return

    console.print("[dim]ocw serve is not running.[/dim]")


def _find_serve_pid() -> int | None:
    """Find the PID of a running 'ocw serve' process."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ocw.serve|ocw serve"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                pid = int(line.strip())
                # Don't return our own PID
                if pid != os.getpid():
                    return pid
    except (FileNotFoundError, ValueError):
        pass
    return None
