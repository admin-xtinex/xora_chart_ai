"""Run the engine stack on a single user-entered symbol."""

from __future__ import annotations

import asyncio
from typing import Any

from xora_chart.application import explainer, matcher
from xora_chart.application.live import last_price
from xora_chart.domain.enums import DecisionAction, OpportunityStatus
from xora_chart.domain.models import Opportunity
from xora_chart.engines.analysis import run_analysis
from xora_chart.engines.decision import run_decision
from xora_chart.persistence.store import Store
from xora_chart.services import binance
from xora_chart.services.binance_ws import BinanceWSHub


def _normalize(raw: str) -> str:
    s = raw.strip().upper().replace("/", "").replace("-", "").replace(" ", "")
    if not s:
        raise ValueError("Empty symbol")
    if not s.endswith("USDT"):
        s += "USDT"
    return s


async def analyze_symbol(
    raw: str,
    store: Store | None = None,
    history_rows: list[Any] | None = None,
) -> Opportunity:
    """Analyze one coin using REST history + WebSocket live state."""
    store = store or Store.instance()
    symbol = _normalize(raw)

    hub = BinanceWSHub.instance()
    hub.set_watchlist(list(hub._desired_symbols | {symbol}))
    await hub.ensure_started()

    if history_rows:
        window = binance.window_from_history(symbol, history_rows, interval="1m", limit=100)
    else:
        window = await binance.fetch_klines(symbol, interval="1m", limit=100)

    # Give the WS price sampler one short opportunity to publish this newly
    # requested symbol.  History analysis never depends on this wait.
    live_px = last_price(symbol)
    for _ in range(10):
        if live_px is not None:
            break
        await asyncio.sleep(0.2)
        live_px = last_price(symbol)

    matches = matcher.match_window(window)
    if not matches:
        # still return a skeleton so UI can show chart + analysis
        from xora_chart.domain.enums import Direction
        from xora_chart.domain.models import PatternMatch

        matches = [
            PatternMatch(
                pattern_key="none",
                pattern_name="No catalog match",
                direction=Direction.NEUTRAL,
                similarity=0.0,
            )
        ]

    best = matches[0]
    market_analysis = await run_analysis(window, best)
    decision = run_decision(window, best, market_analysis) if best.pattern_key != "none" else None

    trade = decision.setup if decision else None
    status = OpportunityStatus.CANDIDATE
    if decision:
        if decision.action == DecisionAction.APPROVE:
            status = OpportunityStatus.VALIDATED
        elif decision.action == DecisionAction.WAIT:
            status = OpportunityStatus.WAITING
        else:
            status = OpportunityStatus.REJECTED

    chart = {}
    if trade and best.pattern_key != "none":
        try:
            chart = explainer.build_analysis(window, best, trade, validation_note=decision.reason if decision else "")
        except Exception:
            chart = {}

    opp = Opportunity(
        symbol=symbol,
        interval=window.interval,
        status=status,
        best_match=best if best.pattern_key != "none" else None,
        all_matches=[m for m in matches if m.pattern_key != "none"],
        market_analysis=market_analysis,
        decision=decision,
        trade=trade,
        ai_validated=bool(decision and decision.action == DecisionAction.APPROVE),
        ai_rationale=decision.reason if decision else "No strong pattern match on this window",
        analysis=chart,
        candle_count=len(window.candles),
        last_price=live_px if live_px is not None else (window.candles[-1].close if window.candles else None),
        candles=list(window.candles),
    )
    store.update_opportunity(opp)
    return opp
