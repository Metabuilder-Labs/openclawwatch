"""
Auto-bootstrap: lazily initialise the OCW TracerProvider + IngestPipeline
the first time @watch() or a provider patch creates a span.

This ensures that SDK users don't need to manually wire up the pipeline.
"""
from __future__ import annotations

import atexit
import logging
import threading


logger = logging.getLogger("ocw.sdk")

_lock = threading.Lock()
_initialised = False
_provider = None


def ensure_initialised() -> None:
    """
    Idempotent bootstrap. Safe to call multiple times / from multiple threads.
    Sets up: config -> DuckDB -> IngestPipeline -> OcwSpanExporter -> TracerProvider.
    """
    global _initialised, _provider
    if _initialised:
        return

    with _lock:
        if _initialised:
            return

        try:
            from ocw.core.config import load_config
            from ocw.core.db import open_db
            from ocw.core.ingest import IngestPipeline
            from ocw.core.cost import CostEngine
            from ocw.otel.provider import build_tracer_provider

            config = load_config()
            db = open_db(config.storage)
            cost_engine = CostEngine(db)
            pipeline = IngestPipeline(db, config, cost_engine=cost_engine)
            _provider = build_tracer_provider(config, pipeline)
            _initialised = True

            # Ensure spans are flushed on exit
            atexit.register(_shutdown)

            logger.debug("OCW tracing initialised (db=%s)", config.storage.path)

        except Exception as exc:
            logger.warning("OCW bootstrap failed — spans will not be recorded: %s", exc)
            _initialised = True  # Don't retry on every call


def _shutdown() -> None:
    """Flush pending spans on interpreter exit."""
    if _provider is not None:
        try:
            _provider.force_flush(timeout_millis=5000)
            _provider.shutdown()
        except Exception:
            pass
