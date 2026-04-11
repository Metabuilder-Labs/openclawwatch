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
    systemd_path = Path.home() / ".config/systemd/user/openclawwatch.service"

    # Try launchd first (macOS).
    # -w writes a Disabled entry to launchd's database so the daemon does not
    # auto-start on the next login (the plist file stays on disk so the user
    # can re-enable with `launchctl load <plist>` or by re-running ocw serve).
    if plist_path.exists():
        result = subprocess.run(
            ["launchctl", "unload", "-w", str(plist_path)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print("[green]ocw serve stopped.[/green] (launchd daemon unloaded)")
            return
        # If unload failed, the daemon may not have been loaded — fall through

    # Try systemd (Linux).
    # `disable --now` stops the unit immediately AND removes it from the
    # boot-time targets, so it does not auto-start on next login.
    # The service file stays on disk; `systemctl --user enable --now openclawwatch`
    # re-enables it.
    if systemd_path.exists():
        result = subprocess.run(
            ["systemctl", "--user", "disable", "--now", "openclawwatch"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print("[green]ocw serve stopped.[/green] (systemd service stopped)")
            return
        # Fall through to pgrep if systemctl is unavailable or the unit isn't loaded

    # Fallback: find and signal the process directly
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
