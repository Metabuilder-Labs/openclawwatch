from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import click

from ocw.utils.formatting import console


@click.command("uninstall")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def cmd_uninstall(ctx: click.Context, yes: bool) -> None:
    """Remove all OCW data, config, and daemon."""
    if not yes:
        confirmed = click.confirm(
            "This will delete all OCW data including telemetry history. Continue?",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Cancelled.[/dim]")
            return

    # 1. Stop ocw serve if running
    from ocw.cli.cmd_stop import cmd_stop
    ctx.invoke(cmd_stop)

    # 2. Unload and delete launchd plist
    plist_path = Path.home() / "Library/LaunchAgents/com.openclawwatch.serve.plist"
    if plist_path.exists():
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True, text=True,
        )
        plist_path.unlink()
        console.print(f"  Removed {plist_path}")

    # 3. Delete systemd service if present
    systemd_path = Path.home() / ".config/systemd/user/openclawwatch.service"
    if systemd_path.exists():
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "openclawwatch"],
            capture_output=True, text=True,
        )
        systemd_path.unlink()
        console.print(f"  Removed {systemd_path}")

    # 4. Delete ~/.ocw/
    ocw_dir = Path.home() / ".ocw"
    if ocw_dir.exists():
        shutil.rmtree(ocw_dir)
        console.print(f"  Removed {ocw_dir}")

    # 5. Delete local .ocw/ if present
    local_ocw = Path(".ocw")
    if local_ocw.exists():
        shutil.rmtree(local_ocw)
        console.print(f"  Removed {local_ocw}")

    # 6. Delete temp files
    for tmp_file in ["/tmp/ocw-serve.out", "/tmp/ocw-serve.err"]:
        p = Path(tmp_file)
        if p.exists():
            p.unlink()
            console.print(f"  Removed {tmp_file}")

    console.print()
    console.print("[green]OpenClawWatch data and config removed.[/green]")
    console.print("To remove the package itself, run: [bold]pip uninstall openclawwatch[/bold]")
