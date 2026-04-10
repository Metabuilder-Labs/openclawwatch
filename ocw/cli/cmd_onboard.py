from __future__ import annotations

import json as json_mod
import platform
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import click

from ocw.core.config import find_config_file
from ocw.utils.formatting import console


@click.command("onboard")
@click.option("--claude-code", "claude_code", is_flag=True, default=False,
              help="Configure Claude Code telemetry to flow into ocw")
@click.option("--budget", type=float, default=None,
              help="Daily budget in USD per agent (0 = no limit)")
@click.option("--install-daemon", "install_daemon", is_flag=True, default=False,
              help="Install background daemon without prompting")
@click.option("--no-daemon", is_flag=True, default=False,
              help="Skip background daemon installation")
@click.option("--force", is_flag=True, help="Overwrite existing config")
@click.pass_context
def cmd_onboard(ctx: click.Context, claude_code: bool, budget: float | None,
                install_daemon: bool, no_daemon: bool, force: bool) -> None:
    """Interactive setup wizard for ocw."""
    if claude_code:
        _onboard_claude_code(ctx, budget, install_daemon, no_daemon, force)
        return
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
            "Daily budget in USD per agent (0 = no limit, default 5)",
            type=float, default=5.0, show_default=False,
        )

    ingest_secret = secrets.token_hex(32)

    # Always install daemon unless --no-daemon was passed
    want_daemon = not no_daemon

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


def _onboard_claude_code(
    ctx: click.Context,
    budget: float | None,
    install_daemon: bool,
    no_daemon: bool,
    force: bool,
) -> None:
    """Configure Claude Code to send telemetry to ocw."""
    from ocw.core.config import (
        AgentConfig, BudgetConfig, OcwConfig, SecurityConfig, load_config, write_config,
    )

    project_name = _derive_project_name()
    agent_id = f"claude-code-{project_name}"
    existing = find_config_file()

    if budget is None:
        budget = click.prompt(
            "Daily budget in USD (0 = no limit, default 5)",
            type=float, default=5.0, show_default=False,
        )

    if existing and not force:
        config = load_config(str(existing))
        if agent_id not in config.agents:
            config.agents[agent_id] = AgentConfig()
        if budget and budget > 0:
            config.agents[agent_id].budget.daily_usd = budget
        config_path = Path(existing)
        write_config(config, config_path)
        console.print(f"  ocw config updated: {config_path}")
    else:
        ingest_secret = secrets.token_hex(32)
        daily_usd = budget if budget and budget > 0 else None
        agents = {agent_id: AgentConfig(budget=BudgetConfig(daily_usd=daily_usd))}
        config = OcwConfig(
            version="1",
            agents=agents,
            security=SecurityConfig(ingest_secret=ingest_secret),
        )
        config_path = Path(".ocw/config.toml")
        write_config(config, config_path)
        console.print(f"  ocw config written to: {config_path}")

    # --- Global settings (~/.claude/settings.json) ---
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    global_settings_path = claude_dir / "settings.json"

    global_settings: dict = {}
    if global_settings_path.exists():
        try:
            global_settings = json_mod.loads(global_settings_path.read_text())
        except (json_mod.JSONDecodeError, OSError):
            global_settings = {}

    # Write global OTLP config only if not already present
    port = config.api.port
    secret = config.security.ingest_secret
    global_env: dict = global_settings.get("env", {})
    if "OTEL_EXPORTER_OTLP_ENDPOINT" not in global_env:
        global_env["CLAUDE_CODE_ENABLE_TELEMETRY"] = "1"
        global_env["OTEL_LOGS_EXPORTER"] = "otlp"
        global_env["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/json"
        global_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{port}"
        if secret:
            global_env["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Bearer {secret}"
        global_settings["env"] = global_env
        global_settings_path.write_text(json_mod.dumps(global_settings, indent=2) + "\n")

    # --- Project settings (<cwd>/.claude/settings.json) ---
    project_claude_dir = Path.cwd() / ".claude"
    project_claude_dir.mkdir(parents=True, exist_ok=True)
    project_settings_path = project_claude_dir / "settings.json"

    project_settings: dict = {}
    if project_settings_path.exists():
        try:
            project_settings = json_mod.loads(project_settings_path.read_text())
        except (json_mod.JSONDecodeError, OSError):
            project_settings = {}

    project_env: dict = project_settings.get("env", {})
    project_env["OTEL_RESOURCE_ATTRIBUTES"] = f"service.name={agent_id}"
    project_settings["env"] = project_env
    project_settings_path.write_text(json_mod.dumps(project_settings, indent=2) + "\n")

    # --- Shell env (~/.zshrc) ---
    # Writes host.docker.internal endpoint so harness sessions (Docker) pick up
    # the vars automatically via compose.yml passthrough — no manual setup needed.
    # Native Claude Code uses settings.json (127.0.0.1) written above instead.
    zshrc = Path.home() / ".zshrc"
    zshrc.touch(exist_ok=True)
    marker = "# ocw harness observability"
    zshrc_text = zshrc.read_text()
    if marker not in zshrc_text:
        zshrc.open("a").write(f"""
{marker}
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:{port}
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer {secret}"
""")

    want_daemon = install_daemon or (
        not no_daemon and click.confirm(
            "Install background daemon (keeps ocw serve alive)?", default=True
        )
    )
    if want_daemon:
        _install_daemon()

    console.print()
    console.print("[bold green]Claude Code observability configured.[/bold green]")
    console.print(f"  Global settings:     {global_settings_path}")
    console.print(f"  Project settings:    {project_settings_path}")
    console.print("  Shell env:           ~/.zshrc (harness-compatible endpoint)")
    console.print(f"  Agent ID:            {agent_id}")
    if budget and budget > 0:
        console.print(f"  Daily budget:        ${budget:.2f}")
    console.print(f"  OTLP endpoint:       http://127.0.0.1:{port} (native)")
    console.print(f"                       http://host.docker.internal:{port} (harness)")
    if secret:
        console.print(f"  Ingest secret:       {secret[:8]}...")
    console.print()
    if not want_daemon:
        console.print("[dim]Start the server:[/dim]  ocw serve")
    console.print("[dim]Restart Claude Code for settings to take effect.[/dim]")
    console.print(f"[dim]Then run:[/dim]  ocw status --agent {agent_id}")


def _derive_project_name() -> str:
    """
    Derive a meaningful project name for the agent ID.
    Priority: git remote origin repo name > current folder name.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Extract repo name from URL — handles both https and ssh forms
            # e.g. https://github.com/org/my-repo.git  -> my-repo
            #      git@github.com:org/my-repo.git       -> my-repo
            name = url.rstrip("/").split("/")[-1].split(":")[-1]
            name = name.removesuffix(".git").lower()
            if name:
                return name
    except Exception:
        pass
    return Path.cwd().name.lower()


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
    ocw_path = shutil.which("ocw") or sys.executable.replace("/python", "/ocw").replace("/python3", "/ocw")
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
    ocw_path = shutil.which("ocw") or sys.executable.replace("/python", "/ocw").replace("/python3", "/ocw")
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
