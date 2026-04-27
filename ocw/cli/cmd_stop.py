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

    stopped_via: list[str] = []

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
            stopped_via.append("launchd daemon unloaded")

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
            stopped_via.append("systemd service stopped")

    # Always sweep for orphan foreground `ocw serve` processes started via
    # `ocw serve &` — launchd/systemd unload doesn't affect those, and they
    # keep holding the port. Loop until pgrep stops finding matches so
    # multiple stragglers all get reaped.
    while True:
        pid = _find_serve_pid()
        if not pid:
            break
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            break
        stopped_via.append(f"PID {pid}")

    if stopped_via:
        console.print(
            f"[green]ocw serve stopped.[/green] ({', '.join(stopped_via)})"
        )
    else:
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
