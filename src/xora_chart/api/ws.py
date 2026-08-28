"""WebSocket application transport for the XORA dashboard.

Application commands remain WebSocket RPC. Historical Binance Futures klines may
arrive from REST (backend or browser); live prices/order-book state come from
Binance WebSockets. Operational HTTP liveness/readiness lives in ``api.ops``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from xora_chart.application import discovery
from xora_chart.application.cycle_runtime import cycle_status, run_cycle
from xora_chart.application.live import enrich_position, last_price
from xora_chart.application.status import health_snapshot, positions_summary
from xora_chart.application.symbol_scan import analyze_symbol
from xora_chart.catalog import list_patterns
from xora_chart.domain.enums import OpportunityStatus
from xora_chart.engines.trade import close_position, list_positions, manage_open_positions
from xora_chart.engines.trade.engine import open_from_opportunity
from xora_chart.persistence.store import Store

router = APIRouter()


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(v) for v in value]
    if isinstance(value, dict):
        return {k: _dump(v) for k, v in value.items()}
    return value


def _normalize_symbol(raw: Any) -> str:
    compact = str(raw or "").strip().upper()
    for token in ("/", "-", " "):
        compact = compact.replace(token, "")
    if not compact:
        raise RuntimeError("Enter a coin symbol")
    return compact if compact.endswith("USDT") else f"{compact}USDT"


def _safe_limit(raw: Any, *, default: int, maximum: int) -> int:
    try:
        return max(1, min(int(raw), maximum))
    except (TypeError, ValueError):
        return default


def _match_confidence(opp: Any) -> float:
    match = getattr(opp, "best_match", None)
    if not match:
        return -1.0
    reference = float(getattr(match, "reference_similarity", 0.0) or 0.0)
    similarity = float(getattr(match, "similarity", 0.0) or 0.0)
    return reference if reference > 0 else similarity


async def _dispatch(action: str, payload: dict[str, Any]) -> Any:
    store = Store.instance()

    if action == "health":
        return health_snapshot()
    if action == "patterns.list":
        return list_patterns(direction=payload.get("direction"), pattern_type=payload.get("type"))
    if action == "opportunities.list":
        limit = _safe_limit(payload.get("limit", 30), default=30, maximum=100)
        items = store.list_opportunities(limit=limit)
        return sorted(items, key=_match_confidence, reverse=True)
    if action == "settings.get":
        return store.get_settings()
    if action == "settings.update":
        patch: dict[str, Any] = {}
        if "auto_trade" in payload:
            patch["auto_trade"] = bool(payload["auto_trade"])
        if "trade_mode" in payload:
            mode = str(payload.get("trade_mode") or "demo").lower()
            if mode != "demo":
                raise RuntimeError("Live trading is not available in XORA Chart AI yet; demo mode is enforced")
            patch["trade_mode"] = "demo"
        return store.update_settings(patch)
    if action == "cycle.plan":
        coins = (await discovery.run_discovery())[:20]
        return {"coins": coins, "count": len(coins), "status": cycle_status()}
    if action == "cycle.status":
        return cycle_status()
    if action == "cycles.latest":
        return store.latest_cycle()
    if action == "cycles.list":
        return store.list_cycles(limit=_safe_limit(payload.get("limit", 20), default=20, maximum=50))
    if action == "cycle.run":
        return await run_cycle(
            histories=payload.get("histories") or None,
            coins_override=payload.get("coins") or None,
        )
    if action == "analyze":
        return await analyze_symbol(
            _normalize_symbol(payload.get("symbol")),
            history_rows=payload.get("history") or None,
        )
    if action == "quote":
        symbol = _normalize_symbol(payload.get("symbol"))
        px = last_price(symbol)
        if px is None:
            raise RuntimeError(f"No WebSocket price for {symbol}")
        return {"symbol": symbol, "price": px}
    if action == "positions.list":
        manage_open_positions()
        status = str(payload.get("status") or "").lower() or None
        if status not in (None, "open", "closed"):
            raise RuntimeError("Position status must be open or closed")
        return [enrich_position(p) for p in list_positions(status=status)]
    if action == "positions.summary":
        return positions_summary()
    if action == "positions.manage":
        manage_open_positions()
        return [enrich_position(p) for p in list_positions(status="open")]
    if action == "position.open":
        opp = store.get_opportunity(str(payload.get("opportunity_id") or ""))
        if not opp:
            raise RuntimeError("Opportunity not found")
        pos = open_from_opportunity(opp, store=store)
        opp.status = OpportunityStatus.TRADED
        store.update_opportunity(opp)
        return pos
    if action == "position.close":
        return close_position(
            str(payload.get("position_id") or ""),
            exit_price=payload.get("exit_price"),
            reason=str(payload.get("reason") or "manual"),
            store=store,
        )

    raise RuntimeError(f"Unknown WebSocket action: {action}")


@router.websocket("/ws")
async def dashboard_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await websocket.send_json({"type": "ready", "data": health_snapshot()})
        while True:
            message = await websocket.receive_json()
            request_id = message.get("id")
            action = str(message.get("action") or "")
            payload = message.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}
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
