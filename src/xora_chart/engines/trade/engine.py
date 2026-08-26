"""Trade Engine — execution only. Demo by default; live adapter later."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from xora_chart.config import load_config
from xora_chart.domain.enums import PositionStatus, Side, TradeMode
from xora_chart.domain.models import Opportunity, Position, TradeDecision, TradeLevels
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

    # max open positions
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
    )

    if mode == TradeMode.LIVE:
        # Placeholder — wire signed Binance order API here later
        raise RuntimeError("Live adapter not implemented — use demo mode")

    store.save_position(pos)
    log.info("DEMO open %s %s qty=%s lev=%sx margin=%s", pos.side.value, symbol, qty, leverage, margin)
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


def close_position(position_id: str, exit_price: float | None = None, store: Store | None = None) -> Position:
    store = store or Store.instance()
    pos = store.get_position(position_id)
    if not pos:
        raise RuntimeError("Position not found")
    if pos.status != PositionStatus.OPEN:
        raise RuntimeError("Position not open")

    px = exit_price if exit_price is not None else pos.entry
    if pos.side == Side.BUY:
        pnl = (px - pos.entry) * pos.quantity
    else:
        pnl = (pos.entry - px) * pos.quantity

    pos.status = PositionStatus.CLOSED
    pos.exit_price = px
    pos.realized_pnl = round(pnl, 4)
    pos.closed_at = datetime.utcnow()
    store.save_position(pos)
    log.info("Closed %s pnl=%s", pos.symbol, pos.realized_pnl)
    return pos


def list_positions(status: str | None = None, store: Store | None = None) -> list[Position]:
    store = store or Store.instance()
    items = store.list_positions()
    if status:
        items = [p for p in items if p.status.value == status]
    return items
