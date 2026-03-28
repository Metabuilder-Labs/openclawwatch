from __future__ import annotations

import platform
import secrets
import subprocess
import sys
from pathlib import Path

import click

from ocw.core.config import (
    AgentConfig,
    BudgetConfig,
    OcwConfig,
    SecurityConfig,
    find_config_file,
    write_config,
)
from ocw.utils.formatting import console


@click.command("onboard")
@click.option("--agent", "agent_id", default=None, help="Agent ID to configure")
@click.option("--budget", type=float, default=None, help="Daily budget in USD (0 = no limit)")
@click.option("--install-daemon", is_flag=True, default=False)
@click.option("--no-daemon", is_flag=True, default=False)
@click.option("--force", is_flag=True, help="Overwrite existing config")
@click.pass_context
def cmd_onboard(ctx: click.Context, agent_id: str | None, budget: float | None,
                install_daemon: bool, no_daemon: bool, force: bool) -> None:
    """Interactive setup wizard for ocw."""
    existing = find_config_file()
    if existing and not force:
        console.print(f"[bold]Config already exists:[/bold] {existing}")
        console.print("Use [bold]--force[/bold] to overwrite.")
        return

    if agent_id is None:
        agent_id = click.prompt("Agent ID", default="my-agent")

    if budget is None:
        budget = click.prompt("Daily budget in USD (0 = no limit)", type=float, default=5.0)

    ingest_secret = secrets.token_hex(32)

    want_daemon = False
    if install_daemon:
        want_daemon = True
    elif not no_daemon:
        want_daemon = click.confirm("Install background daemon?", default=False)

    agents = {}
    if budget and budget > 0:
        agents[agent_id] = AgentConfig(budget=BudgetConfig(daily_usd=budget))
    else:
        agents[agent_id] = AgentConfig()

    config = OcwConfig(
        version="1",
        agents=agents,
        security=SecurityConfig(ingest_secret=ingest_secret),
    )

    config_path = Path(".ocw/config.toml")
    write_config(config, config_path)

    if want_daemon:
        _install_daemon()

    console.print()
    console.print("[bold green]Setup complete.[/bold green]")
    console.print(f"  Config written to: {config_path}")
    console.print(f"  Agent ID:          {agent_id}")
    console.print(f"  Ingest secret:     {ingest_secret[:8]}...")
    if budget and budget > 0:
        console.print(f"  Daily budget:      ${budget:.2f}")
    if not want_daemon:
        console.print()
        console.print("[dim]Run [bold]ocw serve[/bold] manually for real-time alerts "
                      "on background agents.[/dim]")


def _install_daemon() -> None:
    system = platform.system()
    try:
        if system == "Darwin":
            _install_launchd()
        elif system == "Linux":
            _install_systemd()
        else:
            console.print(f"[yellow]Background daemon not supported on {system}. "
                          "Run `ocw serve` manually.[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Daemon installation failed: {e}[/yellow]")
        console.print("[dim]You can run `ocw serve` manually instead.[/dim]")


def _install_launchd() -> None:
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
    subprocess.run(["launchctl", "load", str(plist_path)], check=True)
    console.print(f"[green]Daemon installed:[/green] {plist_path}")


def _install_systemd() -> None:
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
    console.print(f"[green]Daemon installed:[/green] {service_path}")
