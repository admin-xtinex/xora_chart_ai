"""Trade Engine — execution only. Demo by default; live adapter later."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from xora_chart.config import load_config
from xora_chart.domain.enums import PositionStatus, Side, TradeMode
from xora_chart.domain.models import Opportunity, Position, TradeLevels
from xora_chart.persistence.store import Store

log = logging.getLogger(__name__)


def _mode() -> TradeMode:
    env = os.getenv("XORA_TRADE_MODE", "").lower()
    if env in ("demo", "live"):
        return TradeMode(env)
    cfg = load_config().get("trade", {})
    m = str(cfg.get("mode", "demo")).lower()
    return TradeMode.LIVE if m == "live" else TradeMode.DEMO


def _sizing(entry: float, stop: float, equity: float, risk_pct: float, leverage: int) -> tuple[float, float]:
    risk_amount = equity * (risk_pct / 100.0)
    stop_dist = abs(entry - stop)
    if stop_dist <= 0 or entry <= 0:
        return 0.0, 0.0
    qty = risk_amount / stop_dist
    notional = qty * entry
    margin = notional / max(leverage, 1)
    return round(qty, 6), round(margin, 4)


def _last_price(symbol: str) -> float | None:
    """Best available mark/last from WS hub, then ticker snapshot."""
    try:
        from xora_chart.services.binance_ws import BinanceWSHub

        hub = BinanceWSHub.instance()
        mark = hub.get_mark(symbol)
        if mark.get("markPrice"):
            return float(mark["markPrice"])
        w = hub.get_window(symbol, limit=5)
        if w and w.candles:
            return float(w.candles[-1].close)
        t = hub._tickers.get(symbol.upper())
        if t and (t.get("c") is not None):
            return float(t["c"])
    except Exception as e:
        log.debug("last_price %s: %s", symbol, e)
    return None


def open_position(
    *,
    symbol: str,
    setup: TradeLevels,
    opportunity_id: str | None = None,
    decision_reason: str | None = None,
    store: Store | None = None,
) -> Position:
    store = store or Store.instance()
    cfg = load_config().get("trade", {})
    mode = _mode()

    if mode == TradeMode.LIVE and not cfg.get("live_enabled", False):
        raise RuntimeError("Live trading disabled. Set trade.live_enabled=true and XORA_TRADE_MODE=live")

    equity = float(cfg.get("demo_equity", 10_000))
    risk_pct = float(cfg.get("risk_percent", 0.5))
    max_lev = int(cfg.get("max_leverage", 5))
    leverage = min(int(cfg.get("default_leverage", 3)), max_lev)

    open_pos = [p for p in store.list_positions() if p.status == PositionStatus.OPEN]
    max_pos = int(cfg.get("max_open_positions", 5))
    if len(open_pos) >= max_pos:
        raise RuntimeError(f"Max open positions reached ({max_pos})")

    if any(p.symbol == symbol and p.status == PositionStatus.OPEN for p in open_pos):
        raise RuntimeError(f"Already open on {symbol}")

    qty, margin = _sizing(setup.entry, setup.stop_loss, equity, risk_pct, leverage)
    if qty <= 0:
        raise RuntimeError("Invalid position size")

    pos = Position(
        symbol=symbol,
        side=setup.side,
        mode=mode,
        status=PositionStatus.OPEN,
        entry=setup.entry,
        stop_loss=setup.stop_loss,
        take_profit_1=setup.take_profit_1,
        take_profit_2=setup.take_profit_2,
        take_profit_3=setup.take_profit_3,
        quantity=qty,
        leverage=leverage,
        margin_used=margin,
        opportunity_id=opportunity_id,
        decision_reason=decision_reason,
        last_price=setup.entry,
    )

    if mode == TradeMode.LIVE:
        raise RuntimeError("Live adapter not implemented — use demo mode")

    store.save_position(pos)
    log.info("DEMO open %s %s qty=%s lev=%sx", pos.side.value, symbol, qty, leverage)
    return pos


def open_from_opportunity(opp: Opportunity, store: Store | None = None) -> Position:
    if not opp.decision or opp.decision.action.value != "APPROVE" or not opp.decision.setup:
        raise RuntimeError("Opportunity not APPROVE or missing setup")
    return open_position(
        symbol=opp.symbol,
        setup=opp.decision.setup,
        opportunity_id=opp.id,
        decision_reason=opp.decision.reason,
        store=store,
    )


def close_position(
    position_id: str,
    exit_price: float | None = None,
    reason: str = "manual",
    store: Store | None = None,
) -> Position:
    store = store or Store.instance()
    pos = store.get_position(position_id)
    if not pos:
        raise RuntimeError("Position not found")
    if pos.status != PositionStatus.OPEN:
        raise RuntimeError("Position not open")

    px = exit_price if exit_price is not None else (pos.last_price or pos.entry)
    if pos.side == Side.BUY:
        pnl = (px - pos.entry) * pos.quantity
    else:
        pnl = (pos.entry - px) * pos.quantity

    pos.status = PositionStatus.CLOSED
    pos.exit_price = px
    pos.exit_reason = reason
    pos.realized_pnl = round(pnl, 4)
    pos.closed_at = datetime.utcnow()
    store.save_position(pos)
    log.info("Closed %s reason=%s px=%s pnl=%s", pos.symbol, reason, px, pos.realized_pnl)
    return pos


def _hit(pos: Position, px: float) -> str | None:
    """Return exit reason if SL/TP touched at price px."""
    if pos.side == Side.BUY:
        if px <= pos.stop_loss:
            return "sl"
        if pos.take_profit_3 is not None and px >= pos.take_profit_3:
            return "tp3"
        if pos.take_profit_2 is not None and px >= pos.take_profit_2:
            return "tp2"
        if px >= pos.take_profit_1:
            return "tp1"
    else:
        if px >= pos.stop_loss:
            return "sl"
        if pos.take_profit_3 is not None and px <= pos.take_profit_3:
            return "tp3"
        if pos.take_profit_2 is not None and px <= pos.take_profit_2:
            return "tp2"
        if px <= pos.take_profit_1:
            return "tp1"
    return None


def manage_open_positions(store: Store | None = None) -> list[Position]:
    """Mark last price and auto-close demo positions that hit SL or TP."""
    store = store or Store.instance()
    closed: list[Position] = []
    for pos in list(store.list_positions()):
        if pos.status != PositionStatus.OPEN:
            continue
        px = _last_price(pos.symbol)
        if px is None:
            continue
        pos.last_price = px
        store.save_position(pos)
        reason = _hit(pos, px)
        if reason:
            try:
                closed.append(close_position(pos.id, exit_price=px, reason=reason, store=store))
            except RuntimeError as e:
                log.warning("auto-close failed %s: %s", pos.symbol, e)
    if closed:
        log.info("Managed positions: closed %d", len(closed))
    return closed


def list_positions(status: str | None = None, store: Store | None = None) -> list[Position]:
    store = store or Store.instance()
    items = store.list_positions()
    if status:
        items = [p for p in items if p.status.value == status]
    return items
