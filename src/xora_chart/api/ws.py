"""WebSocket-only application transport for the XORA dashboard.

No market/application data is fetched through REST. The browser sends small
RPC messages over one persistent WebSocket connection and receives JSON
responses on the same connection.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from xora_chart.application.live import enrich_position, last_price
from xora_chart.application.pipeline import run_cycle
from xora_chart.application.symbol_scan import analyze_symbol
from xora_chart.catalog import list_patterns
from xora_chart.domain.enums import PositionStatus
from xora_chart.engines.trade import close_position, list_positions, manage_open_positions
from xora_chart.engines.trade.engine import open_from_opportunity
from xora_chart.persistence.store import Store
from xora_chart.services.binance_ws import BinanceWSHub, MIN_CANDLES

router = APIRouter()


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(v) for v in value]
    if isinstance(value, dict):
        return {k: _dump(v) for k, v in value.items()}
    return value


def _health() -> dict[str, Any]:
    store = Store.instance()
    latest = store.latest_cycle()
    settings = store.get_settings()
    hub = BinanceWSHub.instance()
    try:
        from xora_chart.application.reference_matcher import reference_status

        ref = reference_status()
    except Exception as exc:
        ref = {"ready": False, "count": 0, "error": str(exc)}

    return {
        "status": "ok",
        "service": "xora-chart-ai",
        "transport": "websocket-only",
        "market_data": "binance-websocket-only",
        "rest_market_data": False,
        "ws_connected": hub.websocket_connected(),
        "ws_tickers": hub.ticker_count(),
        "ws_ready_symbols": hub.ready_symbol_count(),
        "ws_min_candles": MIN_CANDLES,
        "ws_last_message_age_seconds": hub.last_message_age_seconds(),
        "auto_trade": settings.get("auto_trade", False),
        "trade_mode": settings.get("trade_mode", "demo"),
        "latest_cycle_id": latest.cycle_id if latest else None,
        "latest_cycle_errors": latest.errors[:5] if latest else [],
        "latest_opportunities": len(latest.opportunities) if latest else 0,
        "opportunities_cached": len(store.list_opportunities()),
        "positions_open": len([p for p in store.list_positions() if p.status == PositionStatus.OPEN]),
        "reference_gate": True,
        "reference_images": int(ref.get("count", 0)),
        "reference_ready": bool(ref.get("ready", False)),
    }


def _positions_summary() -> dict[str, Any]:
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


async def _dispatch(action: str, payload: dict[str, Any]) -> Any:
    store = Store.instance()

    if action == "health":
        return _health()
    if action == "patterns.list":
        return list_patterns(direction=payload.get("direction"), pattern_type=payload.get("type"))
    if action == "opportunities.list":
        return store.list_opportunities(limit=min(int(payload.get("limit", 30)), 100))
    if action == "settings.get":
        return store.get_settings()
    if action == "settings.update":
        patch = {k: v for k, v in payload.items() if k in {"auto_trade", "trade_mode"}}
        return store.update_settings(patch)
    if action == "cycle.run":
        return await run_cycle()
    if action == "analyze":
        return await analyze_symbol(str(payload.get("symbol") or ""))
    if action == "quote":
        symbol = str(payload.get("symbol") or "").upper()
        px = last_price(symbol)
        if px is None:
            raise RuntimeError(f"No WebSocket price for {symbol}")
        return {"symbol": symbol, "price": px}
    if action == "positions.list":
        manage_open_positions()
        return [enrich_position(p) for p in list_positions(status=payload.get("status"))]
    if action == "positions.summary":
        return _positions_summary()
    if action == "positions.manage":
        manage_open_positions()
        return [enrich_position(p) for p in list_positions(status="open")]
    if action == "position.open":
        opp = store.get_opportunity(str(payload.get("opportunity_id") or ""))
        if not opp:
            raise RuntimeError("Opportunity not found")
        pos = open_from_opportunity(opp, store=store)
        opp.status = type(opp.status).TRADED
        store.update_opportunity(opp)
        return pos
    if action == "position.close":
        return close_position(
            str(payload.get("position_id") or ""),
            exit_price=payload.get("exit_price"),
            reason=str(payload.get("reason") or "manual"),
            store=store,
        )
    if action == "cycles.latest":
        return store.latest_cycle()

    raise RuntimeError(f"Unknown WebSocket action: {action}")


@router.websocket("/ws")
async def dashboard_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await websocket.send_json({"type": "ready", "data": _health()})
        while True:
            message = await websocket.receive_json()
            request_id = message.get("id")
            action = str(message.get("action") or "")
            payload = message.get("payload") or {}
            try:
                data = await _dispatch(action, payload)
                await websocket.send_json(
                    {"type": "response", "id": request_id, "ok": True, "data": _dump(data)}
                )
            except Exception as exc:
                await websocket.send_json(
                    {"type": "response", "id": request_id, "ok": False, "error": str(exc)}
                )
    except WebSocketDisconnect:
        return
