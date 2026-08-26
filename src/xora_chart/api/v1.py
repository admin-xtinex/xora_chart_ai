from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from xora_chart.application.pipeline import run_cycle
from xora_chart.catalog import get_pattern, list_patterns
from xora_chart.domain.models import CycleResult, Opportunity, Pattern
from xora_chart.persistence.store import Store

router = APIRouter(prefix="/api/v1", tags=["patterns"])


@router.get("/health")
def health() -> dict:
    store = Store.instance()
    latest = store.latest_cycle()
    return {
        "status": "ok",
        "service": "xora-chart-ai",
        "phase": 2,
        "latest_cycle_id": latest.cycle_id if latest else None,
        "opportunities_cached": len(store.list_opportunities()),
    }


# ── Educational pattern catalog (Phase 1) ────────────────────────────────────

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


# ── Live opportunities (Phase 2 pipeline) ────────────────────────────────────

@router.get("/opportunities", response_model=list[Opportunity])
def opportunities(limit: int = Query(20, ge=1, le=100)) -> list[Opportunity]:
    return Store.instance().list_opportunities(limit=limit)


@router.get("/opportunities/{opp_id}", response_model=Opportunity)
def opportunity_detail(opp_id: str) -> Opportunity:
    o = Store.instance().get_opportunity(opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return o


@router.get("/cycles", response_model=list[CycleResult])
def cycles(limit: int = Query(10, ge=1, le=50)) -> list[CycleResult]:
    return Store.instance().list_cycles(limit=limit)


@router.get("/cycles/latest", response_model=CycleResult | None)
def latest_cycle() -> CycleResult | None:
    return Store.instance().latest_cycle()


@router.post("/cycles/run", response_model=CycleResult)
async def trigger_cycle(background: BackgroundTasks) -> CycleResult:
    """Run one full scan cycle immediately (also used by the worker)."""
    return await run_cycle()
