from __future__ import annotations

import platform
import secrets
import subprocess
import sys
from pathlib import Path

import click

from ocw.core.config import find_config_file
from ocw.utils.formatting import console


@click.command("onboard")
@click.option("--budget", type=float, default=None,
              help="Daily budget in USD per agent (0 = no limit)")
@click.option("--install-daemon", is_flag=True, default=False)
@click.option("--no-daemon", is_flag=True, default=False)
@click.option("--force", is_flag=True, help="Overwrite existing config")
@click.pass_context
def cmd_onboard(ctx: click.Context, budget: float | None,
                install_daemon: bool, no_daemon: bool, force: bool) -> None:
    """Interactive setup wizard for ocw."""
    existing = find_config_file()
    if existing and not force:
        console.print(f"[bold]Config already exists:[/bold] {existing}")
        console.print("Use [bold]--force[/bold] to overwrite.")
        return

    console.print()
    console.print("[bold]Setting up OpenClawWatch...[/bold]")
    console.print()

    if budget is None:
        budget = click.prompt(
            "Daily budget in USD (applies to all agents, 0 = no limit)",
            type=float, default=5.0,
        )

    ingest_secret = secrets.token_hex(32)

    want_daemon = False
    if install_daemon:
        want_daemon = True
    elif not no_daemon:
        want_daemon = click.confirm("Install background daemon?", default=False)

    config_path = Path(".ocw/config.toml")
    config_path.parent.mkdir(parents=True, exist_ok=True)

    budget_line = ""
    if budget and budget > 0:
        budget_line = f"daily_usd = {budget}"

    config_text = f"""\
# OpenClawWatch configuration
# Docs: https://github.com/Metabuilder-Labs/openclawwatch#configuration

[defaults.budget]
{budget_line}

[security]
ingest_secret = "{ingest_secret}"

[capture]
prompts = false
completions = false
tool_outputs = false

[storage]
path = "~/.ocw/telemetry.duckdb"
retention_days = 90

# Per-agent overrides (optional):
# [agents.my-agent]
# description = "My email agent"
#   [agents.my-agent.budget]
#   daily_usd = 5.00
#   session_usd = 1.00
#   [[agents.my-agent.sensitive_actions]]
#   name = "send_email"
#   severity = "critical"
"""
    config_path.write_text(config_text)

    daemon_msg = None
    if want_daemon:
        daemon_msg = _install_daemon()

    # Output
    console.print()
    console.print("[green]\u2713[/green] Config written to [bold].ocw/config.toml[/bold]")
    console.print(f"[green]\u2713[/green] Ingest secret generated: "
                  f"[dim]{ingest_secret[:8]}...[/dim]")
    if budget and budget > 0:
        console.print(f"[green]\u2713[/green] Default daily budget: "
                      f"[bold]${budget:.2f}[/bold] per agent")
    if daemon_msg:
        console.print(f"[green]\u2713[/green] {daemon_msg}")

    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print()
    console.print("  1. Instrument your agent:")
    console.print()
    console.print("[dim]     from ocw.sdk import watch[/dim]")
    console.print("[dim]     from ocw.sdk.integrations.anthropic import patch_anthropic[/dim]")
    console.print()
    console.print("[dim]     patch_anthropic()[/dim]")
    console.print()
    console.print('[dim]     @watch(agent_id="my-agent")[/dim]')
    console.print("[dim]     def run(task):[/dim]")
    console.print("[dim]         ...[/dim]")
    console.print()
    console.print("  2. Run your agent \u2014 spans are recorded automatically")
    console.print()
    console.print("  3. View telemetry:")
    console.print("[dim]     ocw status          [/dim]# agent overview")
    console.print("[dim]     ocw traces          [/dim]# span history")
    console.print("[dim]     ocw serve           [/dim]# web UI at http://127.0.0.1:7391/")
    console.print()

    if not want_daemon:
        console.print("  Run [bold]ocw serve[/bold] to start the web UI "
                      "and enable real-time alerts.")
        console.print()

    console.print(
        "  To configure per-agent budgets, sensitive actions, or drift detection:"
    )
    console.print(
        "  Edit [bold].ocw/config.toml[/bold] \u2014 see "
        "[dim]https://github.com/Metabuilder-Labs/openclawwatch#configuration[/dim]"
    )
    console.print()


def _install_daemon() -> str | None:
    """Install background daemon. Returns success message or None."""
    system = platform.system()
    try:
        if system == "Darwin":
            return _install_launchd()
        elif system == "Linux":
            return _install_systemd()
        else:
            console.print(f"[yellow]Background daemon not supported on {system}. "
                          "Run `ocw serve` manually.[/yellow]")
            return None
    except Exception as e:
        console.print(f"[yellow]Daemon installation failed: {e}[/yellow]")
        console.print("[dim]You can run `ocw serve` manually instead.[/dim]")
        return None


def _install_launchd() -> str | None:
    ocw_path = sys.executable.replace("/python", "/ocw").replace("/python3", "/ocw")
    plist_path = Path.home() / "Library/LaunchAgents/com.openclawwatch.serve.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_content = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclawwatch.serve</string>
    <key>ProgramArguments</key>
    <array>
        <string>{ocw_path}</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/ocw-serve.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/ocw-serve.out</string>
</dict>
</plist>"""
    plist_path.write_text(plist_content)
    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        console.print(f"[yellow]Daemon plist written to {plist_path} but "
                      f"launchctl load failed.[/yellow]")
        console.print("[dim]Try loading manually:[/dim]")
        console.print(f"  launchctl load {plist_path}")
        console.print("[dim]Or run the server directly:[/dim]")
        console.print("  ocw serve &")
        return None
    return f"Daemon installed at {plist_path}"


def _install_systemd() -> str | None:
    ocw_path = sys.executable.replace("/python", "/ocw").replace("/python3", "/ocw")
    service_path = Path.home() / ".config/systemd/user/openclawwatch.service"
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_content = f"""\
[Unit]
Description=OpenClawWatch observability server
After=network.target

[Service]
ExecStart={ocw_path} serve
Restart=on-failure

[Install]
WantedBy=default.target"""
    service_path.write_text(service_content)
    subprocess.run(
        ["systemctl", "--user", "enable", "--now", "openclawwatch"],
        check=True,
    )
    return f"Daemon installed at {service_path}"
