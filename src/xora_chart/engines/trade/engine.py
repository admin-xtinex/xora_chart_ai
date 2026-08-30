"""Trade Engine — execution only. Demo by default; live adapter later."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from xora_chart.config import load_config
from xora_chart.domain.enums import DecisionAction, PositionStatus, Side, TradeMode
from xora_chart.domain.models import Opportunity, Position, TradeLevels, TradeEvent, XORATrade
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

    # Create and store XORATrade object
    xora_trade = XORATrade(
        id=f"trade_{pos.id}",  # Simple ID linking trade to position
        opportunity_id=opportunity_id or "",
        position_id=pos.id,
        symbol=pos.symbol,
        side=pos.side,
        pattern="",  # Will be updated if we have opportunity data
        timeframe="",  # Will be updated if we have opportunity data
        detected_at=datetime.utcnow(),
        source_cohort="",  # Will be updated if we have opportunity data
        pattern_match_percent=0.0,  # Will be updated if we have opportunity data
        market_evidence_score=0.0,  # Will be updated if we have opportunity data
        decision_action=DecisionAction.WAIT,  # Will be updated if we have opportunity data
        decision_rationale=decision_reason or "",
        entry_price=pos.entry,
        stop_loss_price=pos.stop_loss,
        take_profit_prices=[
            price for price in [pos.take_profit_1, pos.take_profit_2, pos.take_profit_3] if price is not None
        ],
        risk_reward=0.0,  # Will be calculated if we have opportunity data
        executed_at=datetime.utcnow(),
        actual_entry_price=pos.entry,
        quantity=pos.quantity,
        leverage=pos.leverage,
        status=pos.status,
    )

    # Update with opportunity data if available
    if opportunity_id:
        opp = store.get_opportunity(opportunity_id)
        if opp:
            xora_trade.pattern = opp.best_match.model if hasattr(opp.best_match, 'model') else ""
            xora_trade.timeframe = opp.interval
            xora_trade.detected_at = opp.detection_timestamp
            xora_trade.source_cohort = opp.source_cohort or ""
            xora_trade.pattern_match_percent = opp.pattern_match_percent
            xora_trade.market_evidence_score = opp.market_evidence_score
            xora_trade.decision_action = opp.decision.action if opp.decision else DecisionAction.WAIT
            xora_trade.decision_rationale = opp.decision.reason if opp.decision else ""
            # Calculate risk/reward
            if opp.decision.setup:
                risk = abs(opp.decision.setup.entry - opp.decision.setup.stop_loss)
                reward = abs(opp.decision.setup.take_profit_1 - opp.decision.setup.entry) if opp.decision.setup.take_profit_1 else 0
                xora_trade.risk_reward = reward / risk if risk > 0 else 0.0

    store.save_trade(xora_trade)

    # Create and store initial trade events
    if opportunity_id:
        opp = store.get_opportunity(opportunity_id)
        if opp:
            # DETECTED event
            detected_event = TradeEvent(
                id=f"event_{pos.id}_detected",
                opportunity_id=opportunity_id,
                position_id=pos.id,
                timestamp=opp.detection_timestamp,
                event_type="DETECTED",
                description=f"Opportunity detected for {pos.symbol}",
                data={
                    "symbol": pos.symbol,
                    "pattern": opp.best_match.model if hasattr(opp.best_match, 'model') else "",
                    "pattern_match_percent": opp.pattern_match_percent,
                    "market_evidence_score": opp.market_evidence_score
                }
            )
            store.save_event(detected_event)

            # EVENT for each confirmation
            if opp.decision and opp.decision.confirmations:
                for i, conf in enumerate(opp.decision.confirmations):
                    conf_event = TradeEvent(
                        id=f"event_{pos.id}_conf_{i}",
                        opportunity_id=opportunity_id,
                        position_id=pos.id,
                        timestamp=datetime.utcnow(),
                        event_type="CONFIRMATION",
                        description=f"Confirmation: {conf.name}",
                        data={
                            "name": conf.name,
                            "met": conf.met,
                            "required": conf.required,
                            "note": conf.note
                        }
                    )
                    store.save_event(conf_event)

            # DECISION event
            if opp.decision:
                decision_event = TradeEvent(
                    id=f"event_{pos.id}_decision",
                    opportunity_id=opportunity_id,
                    position_id=pos.id,
                    timestamp=datetime.utcnow(),
                    event_type=opp.decision.action.value,
                    description=f"Decision: {opp.decision.action.value}",
                    data={
                        "action": opp.decision.action.value,
                        "reason": opp.decision.reason,
                        "setup": opp.decision.setup.model_dump() if opp.decision.setup else None
                    }
                )
                store.save_event(decision_event)

    # ENTRY event
    entry_event = TradeEvent(
        id=f"event_{pos.id}_entry",
        opportunity_id=opportunity_id or "",
        position_id=pos.id,
        timestamp=datetime.utcnow(),
        event_type="ENTRY",
        description=f"Position opened for {pos.symbol} at {pos.entry}",
        data={
            "symbol": pos.symbol,
            "entry_price": pos.entry,
            "quantity": pos.quantity,
            "leverage": pos.leverage
        }
    )
    store.save_event(entry_event)

    log.info("DEMO open %s %s qty=%s lev=%sx", pos.side.value, symbol, qty, leverage)
    return pos


def open_from_opportunity(opp: Opportunity, store: Store | None = None) -> Position:
    """Only execution entry point for an analyzed opportunity.

    APPROVE alone is intentionally insufficient: the best match must retain
    explicit evidence that it was verified against an uploaded reference chart.
    This is defense-in-depth in case a future API/decision change regresses.
    """
    if not opp.decision or opp.decision.action.value != "APPROVE" or not opp.decision.setup:
        raise RuntimeError("Opportunity not APPROVE or missing setup")
    match = opp.best_match
    if not match or not match.reference_verified or not match.matched_example:
        raise RuntimeError("Trade blocked: uploaded reference-chart verification is required")
    return open_position(
        symbol=opp.symbol,
        setup=opp.decision.setup,
        opportunity_id=opp.id,
        decision_reason=(
            f"{opp.decision.reason} · reference={match.matched_example} "
            f"({match.reference_similarity:.1f}%)"
        ),
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
