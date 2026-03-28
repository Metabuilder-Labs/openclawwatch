"""Storage retention cleanup. Deletes spans older than config.retention_days."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from ocw.utils.time_parse import utcnow

if TYPE_CHECKING:
    from ocw.core.config import StorageConfig
    from ocw.core.db import StorageBackend


def run_retention_cleanup(db: StorageBackend, config: StorageConfig) -> int:
    """
    Delete spans older than config.retention_days.
    Returns the number of spans deleted.
    Called by the apscheduler background job in ocw serve.
    """
    cutoff = utcnow() - timedelta(days=config.retention_days)
    return db.delete_spans_before(cutoff)
