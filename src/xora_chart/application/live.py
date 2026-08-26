"""Live price / PnL / health for open trades and on-demand symbol analysis."""

from __future__ import annotations

from xora_chart.domain.enums import Side
from xora_chart.domain.models import Position
from xora_chart.services.binance_ws import BinanceWSHub


def last_price(symbol: str) -> float | None:
    hub = BinanceWSHub.instance()
    mark = hub.get_mark(symbol)
    if mark.get("markPrice"):
        try:
            return float(mark["markPrice"])
        except (TypeError, ValueError):
            pass
    w = hub.get_window(symbol, limit=5)
    if w and w.candles:
        return float(w.candles[-1].close)
    t = hub._tickers.get(symbol.upper())
    if t and t.get("c") is not None:
        try:
            return float(t["c"])
        except (TypeError, ValueError):
            return None
    return None


def candles_for(symbol: str, limit: int = 100) -> list[dict]:
    hub = BinanceWSHub.instance()
    w = hub.get_window(symbol, limit=limit)
    if not w:
        return []
    return [c.model_dump() for c in w.candles]


def unrealized_pnl(pos: Position, px: float | None) -> float | None:
    if px is None:
        return pos.realized_pnl
    if pos.side == Side.BUY:
        return round((px - pos.entry) * pos.quantity, 4)
    return round((pos.entry - px) * pos.quantity, 4)


def trade_health(pos: Position, px: float | None) -> dict:
    """Score 0–100 + HOLD / CLOSE / TIGHTEN recommendation."""
    if px is None:
        return {
            "status": "unknown",
            "score": 50,
            "action": "HOLD",
            "reason": "No live price yet",
            "progress_to_tp": None,
            "distance_to_sl_pct": None,
        }

    risk = abs(pos.entry - pos.stop_loss) or 1e-9
    if pos.side == Side.BUY:
        progress = (px - pos.entry) / risk  # 1.0 = 1R
        sl_room = (px - pos.stop_loss) / px * 100 if px else 0
        toward_tp = px >= pos.entry
        hit_sl_soon = px <= pos.stop_loss + risk * 0.15
        hit_tp_soon = px >= pos.take_profit_1 - risk * 0.15
    else:
        progress = (pos.entry - px) / risk
        sl_room = (pos.stop_loss - px) / px * 100 if px else 0
        toward_tp = px <= pos.entry
        hit_sl_soon = px >= pos.stop_loss - risk * 0.15
        hit_tp_soon = px <= pos.take_profit_1 + risk * 0.15

    if pos.side == Side.BUY:
        if px <= pos.stop_loss:
            return _pack("critical", 5, "CLOSE", "Price at/through stop — close now", progress, sl_room)
        if px >= pos.take_profit_1:
            return _pack("strong", 90, "CLOSE", "TP1 reached — take profit", progress, sl_room)
    else:
        if px >= pos.stop_loss:
            return _pack("critical", 5, "CLOSE", "Price at/through stop — close now", progress, sl_room)
        if px <= pos.take_profit_1:
            return _pack("strong", 90, "CLOSE", "TP1 reached — take profit", progress, sl_room)

    if hit_sl_soon and progress < 0:
        return _pack("weak", 25, "CLOSE", "Price hugging stop — cut risk", progress, sl_room)
    if hit_tp_soon and progress >= 0.85:
        return _pack("strong", 82, "CLOSE", "Near TP1 — consider taking profit", progress, sl_room)
    if progress >= 1.5:
        return _pack("strong", 80, "HOLD", "Trade working past 1.5R — hold toward next TP", progress, sl_room)
    if progress >= 0.4:
        return _pack("ok", 68, "HOLD", "In profit — hold unless structure breaks", progress, sl_room)
    if toward_tp and progress >= 0:
        return _pack("ok", 58, "HOLD", "Slightly in favor — hold", progress, sl_room)
    if progress > -0.4:
        return _pack("watch", 45, "HOLD", "Small drawdown — hold if structure intact", progress, sl_room)
    return _pack("weak", 30, "CLOSE", "Against the trade — consider exiting", progress, sl_room)


def _pack(status: str, score: int, action: str, reason: str, progress: float, sl_room: float) -> dict:
    return {
        "status": status,
        "score": score,
        "action": action,
        "reason": reason,
        "progress_to_tp": round(progress, 2),
        "distance_to_sl_pct": round(sl_room, 3),
    }


def enrich_position(pos: Position) -> dict:
    px = last_price(pos.symbol)
    pnl = unrealized_pnl(pos, px if pos.status.value == "open" else pos.exit_price)
    health = trade_health(pos, px)
    data = pos.model_dump()
    data["live_price"] = px
    data["live_pnl"] = pnl if pos.status.value == "open" else pos.realized_pnl
    data["health"] = health
    data["candles"] = candles_for(pos.symbol, limit=80)
    return data
