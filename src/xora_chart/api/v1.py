from fastapi import APIRouter, HTTPException, Query

from xora_chart.catalog import get_pattern, list_patterns
from xora_chart.domain.models import Pattern

router = APIRouter(prefix="/api/v1", tags=["patterns"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "xora-chart-ai", "phase": 1}


@router.get("/patterns", response_model=list[Pattern])
def patterns(
    direction: str | None = Query(None, description="bullish | bearish"),
    type: str | None = Query(None, alias="type", description="continuation | reversal"),
) -> list[Pattern]:
    return list_patterns(direction=direction, pattern_type=type)


@router.get("/patterns/{key}", response_model=Pattern)
def pattern_detail(key: str) -> Pattern:
    p = get_pattern(key)
    if not p:
        raise HTTPException(status_code=404, detail=f"Pattern '{key}' not found")
    return p
