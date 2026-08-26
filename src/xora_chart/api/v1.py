"""Versioned REST API — shared by Web dashboard and future Android app."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from xora_chart.application.live import enrich_position, last_price
from xora_chart.application.pipeline import run_cycle
from xora_chart.application.symbol_scan import analyze_symbol
from xora_chart.catalog import get_pattern, list_patterns
from xora_chart.domain.enums import OpportunityStatus, PositionStatus
from xora_chart.domain.models import CycleResult, Opportunity, Pattern, Position
from xora_chart.engines.trade import close_position, list_positions, manage_open_positions
from xora_chart.engines.trade.engine import open_from_opportunity, open_position
from xora_chart.persistence.store import Store
from xora_chart.services.binance_ws import BinanceWSHub

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/health")
def health() -> dict:
    store = Store.instance()
    latest = store.latest_cycle()
    settings = store.get_settings()
    hub = BinanceWSHub.instance()
    return {
        "status": "ok",
        "service": "xora-chart-ai",
        "phase": 3,
        "engines": ["analysis", "decision", "trade"],
        "binance": "websocket+seed",
        "ws_tickers": hub.ticker_count(),
        "auto_trade": settings.get("auto_trade", False),
        "trade_mode": settings.get("trade_mode", "demo"),
        "latest_cycle_id": latest.cycle_id if latest else None,
        "latest_cycle_errors": (latest.errors[:5] if latest else []),
        "latest_opportunities": len(latest.opportunities) if latest else 0,
        "opportunities_cached": len(store.list_opportunities()),
        "positions_open": len([p for p in store.list_positions() if p.status == PositionStatus.OPEN]),
        "positions_closed_last_cycle": latest.positions_closed if latest else 0,
    }


class SettingsPatch(BaseModel):
    auto_trade: bool | None = None
    trade_mode: str | None = None


@router.get("/settings")
def get_settings() -> dict:
    return Store.instance().get_settings()


@router.patch("/settings")
def patch_settings(body: SettingsPatch) -> dict:
    return Store.instance().update_settings(body.model_dump(exclude_none=True))


@router.get("/patterns", response_model=list[Pattern])
def patterns(
    direction: str | None = Query(None),
    type: str | None = Query(None, alias="type"),
) -> list[Pattern]:
    return list_patterns(direction=direction, pattern_type=type)


@router.get("/patterns/{key}", response_model=Pattern)
def pattern_detail(key: str) -> Pattern:
    p = get_pattern(key)
    if not p:
        raise HTTPException(status_code=404, detail=f"Pattern '{key}' not found")
    return p


@router.get("/opportunities", response_model=list[Opportunity])
def opportunities(limit: int = Query(20, ge=1, le=100)) -> list[Opportunity]:
    return Store.instance().list_opportunities(limit=limit)


@router.get("/opportunities/{opp_id}", response_model=Opportunity)
def opportunity_detail(opp_id: str) -> Opportunity:
    o = Store.instance().get_opportunity(opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return o


class AnalyzeBody(BaseModel):
    symbol: str


@router.post("/analyze", response_model=Opportunity)
async def analyze(body: AnalyzeBody) -> Opportunity:
    try:
        return await analyze_symbol(body.symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analyze failed: {e}") from e


@router.get("/quote/{symbol}")
def quote(symbol: str) -> dict:
    px = last_price(symbol)
    if px is None:
        raise HTTPException(status_code=404, detail=f"No live price for {symbol}")
    return {"symbol": symbol.upper(), "price": px}


@router.get("/cycles", response_model=list[CycleResult])
def cycles(limit: int = Query(10, ge=1, le=50)) -> list[CycleResult]:
    return Store.instance().list_cycles(limit=limit)


@router.get("/cycles/latest", response_model=CycleResult | None)
def latest_cycle() -> CycleResult | None:
    return Store.instance().latest_cycle()


@router.post("/cycles/run", response_model=CycleResult)
async def trigger_cycle() -> CycleResult:
    return await run_cycle()


class OpenFromOpportunityBody(BaseModel):
    opportunity_id: str


class CloseBody(BaseModel):
    exit_price: float | None = Field(None, description="Optional mark price")
    reason: str = "manual"


@router.get("/positions")
def positions(status: str | None = Query(None, description="open | closed")) -> list[dict]:
    manage_open_positions()
    items = list_positions(status=status)
    return [enrich_position(p) for p in items]


@router.get("/positions/history/summary")
def positions_summary() -> dict:
    all_pos = [enrich_position(p) for p in Store.instance().list_positions()]
    closed = [p for p in all_pos if p.get("status") == "closed"]
    open_p = [p for p in all_pos if p.get("status") == "open"]
    realized = [p.get("realized_pnl") for p in closed if p.get("realized_pnl") is not None]
    live = [p.get("live_pnl") for p in open_p if p.get("live_pnl") is not None]
    wins = [p for p in realized if p > 0]
    losses = [p for p in realized if p < 0]
    total_pnl = sum(realized) if realized else 0.0
    return {
        "open_count": len(open_p),
        "closed_count": len(closed),
        "total_trades": len(all_pos),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(realized) * 100, 1) if realized else 0.0,
        "total_realized_pnl": round(total_pnl, 4),
        "open_unrealized_pnl": round(sum(live), 4) if live else 0.0,
        "avg_pnl": round(total_pnl / len(realized), 4) if realized else 0.0,
        "best_trade": max(realized) if realized else None,
        "worst_trade": min(realized) if realized else None,
    }


@router.post("/positions/manage")
def manage_positions() -> list[dict]:
    manage_open_positions()
    return [enrich_position(p) for p in list_positions(status="open")]


@router.get("/positions/{pos_id}")
def position_detail(pos_id: str) -> dict:
    p = Store.instance().get_position(pos_id)
    if not p:
        raise HTTPException(status_code=404, detail="Position not found")
    return enrich_position(p)


@router.post("/positions", response_model=Position)
def open_trade(body: OpenFromOpportunityBody) -> Position:
    store = Store.instance()
    opp = store.get_opportunity(body.opportunity_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    try:
        if opp.decision and opp.decision.setup and opp.decision.action.value in ("APPROVE", "WAIT"):
            pos = open_position(
                symbol=opp.symbol,
                setup=opp.decision.setup,
                opportunity_id=opp.id,
                decision_reason=opp.decision.reason,
            )
        else:
            pos = open_from_opportunity(opp)
        opp.status = OpportunityStatus.TRADED
        store.update_opportunity(opp)
        return pos
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/positions/{pos_id}/close", response_model=Position)
def close_trade(pos_id: str, body: CloseBody | None = None) -> Position:
    try:
        return close_position(
            pos_id,
            exit_price=body.exit_price if body else None,
            reason=(body.reason if body else "manual"),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
