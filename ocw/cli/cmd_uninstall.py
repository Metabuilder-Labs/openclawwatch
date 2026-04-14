from __future__ import annotations

import json
import re
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

    # 2. Deregister MCP server from Claude Code (Gap #13)
    if shutil.which("claude"):
        subprocess.run(
            ["claude", "mcp", "remove", "ocw", "--scope", "user"],
            capture_output=True, text=True,
        )
        console.print("  Removed ocw MCP server from Claude Code.")

    # 3. Unload and delete launchd plist
    plist_path = Path.home() / "Library/LaunchAgents/com.openclawwatch.serve.plist"
    if plist_path.exists():
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True, text=True,
        )
        plist_path.unlink()
        console.print(f"  Removed {plist_path}")

    # 4. Delete systemd service if present
    systemd_path = Path.home() / ".config/systemd/user/openclawwatch.service"
    if systemd_path.exists():
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "openclawwatch"],
            capture_output=True, text=True,
        )
        systemd_path.unlink()
        console.print(f"  Removed {systemd_path}")

    # 5. Delete ~/.ocw/
    ocw_dir = Path.home() / ".ocw"
    if ocw_dir.exists():
        shutil.rmtree(ocw_dir)
        console.print(f"  Removed {ocw_dir}")

    # 6. Delete local .ocw/ if present
    local_ocw = Path(".ocw")
    if local_ocw.exists():
        shutil.rmtree(local_ocw)
        console.print(f"  Removed {local_ocw}")

    # 7. Delete temp files
    for tmp_file in ["/tmp/ocw-serve.out", "/tmp/ocw-serve.err"]:
        p = Path(tmp_file)
        if p.exists():
            p.unlink()
            console.print(f"  Removed {tmp_file}")

    # 8. Remove OCW env vars from ~/.claude/settings.json (Gap #7)
    _GLOBAL_OCW_KEYS = {
        "CLAUDE_CODE_ENABLE_TELEMETRY",
        "OTEL_LOGS_EXPORTER",
        "OTEL_EXPORTER_OTLP_PROTOCOL",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
    }
    global_settings_path = Path.home() / ".claude" / "settings.json"
    if global_settings_path.exists():
        try:
            gs = json.loads(global_settings_path.read_text())
            env = gs.get("env", {})
            removed = [k for k in _GLOBAL_OCW_KEYS if k in env]
            for k in removed:
                del env[k]
            if removed:
                gs["env"] = env
                global_settings_path.write_text(json.dumps(gs, indent=2) + "\n")
                console.print(f"  Cleaned {len(removed)} OCW env vars from {global_settings_path}")
        except Exception as exc:
            console.print(f"  [yellow]Could not clean {global_settings_path}: {exc}[/yellow]")

    # 9. Remove OTEL_RESOURCE_ATTRIBUTES from project .claude/settings.json (Gap #7)
    project_settings_path = Path.cwd() / ".claude" / "settings.json"
    if project_settings_path.exists():
        try:
            ps = json.loads(project_settings_path.read_text())
            env = ps.get("env", {})
            if "OTEL_RESOURCE_ATTRIBUTES" in env:
                del env["OTEL_RESOURCE_ATTRIBUTES"]
                ps["env"] = env
                project_settings_path.write_text(json.dumps(ps, indent=2) + "\n")
                console.print(f"  Removed OTEL_RESOURCE_ATTRIBUTES from {project_settings_path}")
        except Exception as exc:
            console.print(f"  [yellow]Could not clean {project_settings_path}: {exc}[/yellow]")

    # 10. Remove # ocw harness observability block from ~/.zshrc (Gap #7)
    zshrc = Path.home() / ".zshrc"
    if zshrc.exists():
        try:
            text = zshrc.read_text()
            cleaned = re.sub(
                r"\n# ocw harness observability\nexport [^\n]+\nexport [^\n]+\nexport [^\n]+\nexport [^\n]+\nexport [^\n]+\n",
                "\n",
                text,
            )
            if cleaned != text:
                zshrc.write_text(cleaned)
                console.print(f"  Removed OCW env block from {zshrc}")
        except Exception as exc:
            console.print(f"  [yellow]Could not clean {zshrc}: {exc}[/yellow]")

    console.print()
    console.print("[green]OpenClawWatch data and config removed.[/green]")
    console.print("To remove the package itself, run: [bold]pip uninstall openclawwatch[/bold]")
