from __future__ import annotations

import click

from ocw.utils.formatting import console


@click.command("serve")
@click.option("--host", default=None, help="Bind host (default: from config)")
@click.option("--port", default=None, type=int, help="Bind port (default: from config)")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.pass_context
def cmd_serve(ctx: click.Context, host: str | None, port: int | None,
              reload: bool) -> None:
    """Start the ocw API server."""
    config = ctx.obj["config"]
    bind_host = host or config.api.host
    bind_port = port or config.api.port

    # Schedule retention cleanup
    from apscheduler.schedulers.background import BackgroundScheduler
    from ocw.core.retention import run_retention_cleanup

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_retention_cleanup,
        "cron",
        hour=0,
        minute=0,
        args=[ctx.obj["db"], config.storage],
    )
    scheduler.start()

    console.print(f"[bold]ocw serve[/bold] starting on http://{bind_host}:{bind_port}")
    console.print(f"  API docs:    http://{bind_host}:{bind_port}/docs")
    if config.export.prometheus.enabled:
        console.print(f"  Metrics:     http://{bind_host}:{bind_port}/metrics")
    console.print()

    import uvicorn
    from ocw.api.app import create_app
    from ocw.core.ingest import IngestPipeline
    from ocw.core.cost import CostEngine
    from ocw.core.alerts import AlertEngine
    from ocw.core.schema_validator import SchemaValidator
    from ocw.core.drift import DriftDetector

    db = ctx.obj["db"]
    cost_engine = CostEngine(db)
    alert_engine = AlertEngine(db, config)
    schema_validator = SchemaValidator(db, alert_engine, config)
    drift_detector = DriftDetector(db, alert_engine, config)
    pipeline = IngestPipeline(
        db, config,
        cost_engine=cost_engine,
        alert_engine=alert_engine,
        schema_validator=schema_validator,
        drift_detector=drift_detector,
    )
    app = create_app(config, db, pipeline)
    uvicorn.run(app, host=bind_host, port=bind_port, reload=reload)
