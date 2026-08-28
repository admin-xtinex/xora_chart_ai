"""Lightweight HTTP endpoints for load balancers and deployment verification."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from xora_chart.application.status import health_snapshot

router = APIRouter(tags=["operations"])


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    """Process liveness. A degraded market feed does not make the API process dead."""
    data = health_snapshot()
    return {
        "status": "ok",
        "service": data["service"],
        "version": data["version"],
        "ready": data["ready"],
    }


@router.get("/readyz", include_in_schema=False)
def readyz():
    """Production readiness: live market feed plus the mandatory reference library."""
    data = health_snapshot()
    status_code = 200 if data["ready"] else 503
    return JSONResponse(content=data, status_code=status_code)
