"""GET /api/v1/alerts — alert history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ocw.api.deps import require_api_key
from ocw.core.models import AlertFilters, AlertType, Severity
from ocw.utils.time_parse import parse_since

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/alerts")
async def get_alerts(
    request: Request,
    agent_id: str | None = None,
    since: str | None = None,
    severity: str | None = None,
    type: str | None = None,
    unread: bool = False,
) -> dict:
    db = request.app.state.db
    try:
        sev = Severity(severity) if severity else None
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid severity: {severity!r}")
    try:
        typ = AlertType(type) if type else None
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid type: {type!r}")
    filters = AlertFilters(
        agent_id=agent_id,
        since=parse_since(since) if since else None,
        severity=sev,
        type=typ,
        unread=unread,
    )
    alerts = db.get_alerts(filters)
    return {
        "alerts": [
            {
                "alert_id": a.alert_id,
                "fired_at": a.fired_at.isoformat(),
                "type": a.type.value,
                "severity": a.severity.value,
                "title": a.title,
                "detail": a.detail,
                "agent_id": a.agent_id,
                "session_id": a.session_id,
                "span_id": a.span_id,
                "acknowledged": a.acknowledged,
                "suppressed": a.suppressed,
            }
            for a in alerts
        ],
        "count": len(alerts),
    }
