"""Orchestrates one full scan cycle through engines."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from xora_chart.application import discovery, explainer, market_data, matcher, ranking
from xora_chart.application.live import last_price
from xora_chart.domain.enums import DecisionAction, OpportunityStatus
from xora_chart.domain.models import CycleResult, DiscoveredCoin, Opportunity
from xora_chart.engines.analysis import run_analysis
from xora_chart.engines.decision import run_decision
from xora_chart.engines.trade.engine import manage_open_positions, open_from_opportunity
from xora_chart.persistence.store import Store

log = logging.getLogger(__name__)


async def run_cycle(
    store: Store | None = None,
    *,
    histories: dict[str, list[Any]] | None = None,
    coins_override: list[dict[str, Any] | DiscoveredCoin] | None = None,
) -> CycleResult:
    """Run one 20-coin scan using REST history and WebSocket live evidence."""
    store = store or Store.instance()
    result = CycleResult()
    log.info("Cycle %s started (auto_trade=%s)", result.cycle_id, store.auto_trade_enabled())

    try:
        closed = manage_open_positions(store)
        result.positions_closed = len(closed)
    except Exception as e:
        log.warning("Position manage failed: %s", e)
        result.errors.append(f"manage: {e}")

    try:
        if coins_override is not None:
            coins = [
                c if isinstance(c, DiscoveredCoin) else DiscoveredCoin.model_validate(c)
                for c in coins_override
            ][:20]
        else:
            coins = (await discovery.run_discovery())[:20]
        result.symbols_scanned = [c.symbol for c in coins]
    except Exception as e:
        log.exception("Discovery failed")
        result.errors.append(f"discovery: {e}")
        result.finished_at = datetime.now(UTC)
        store.save_cycle(result)
        return result

    if not coins:
        result.errors.append("discovery: 0 coins (WebSocket prices not ready)")
        result.finished_at = datetime.now(UTC)
        store.save_cycle(result)
        return result

    try:
        windows = await market_data.fetch_windows(coins, histories=histories)
    except Exception as e:
        log.exception("Market data failed")
        result.errors.append(f"market_data: {e}")
        result.finished_at = datetime.now(UTC)
        store.save_cycle(result)
        return result

    if not windows:
        result.errors.append("history: no usable closed-candle windows")
        result.finished_at = datetime.now(UTC)
        store.save_cycle(result)
        return result

    opportunities: list[Opportunity] = []
    auto = store.auto_trade_enabled()

    for window in windows:
        try:
            matches = matcher.match_window(window)
            if not matches:
                continue

            best = matches[0]
            try:
                market_analysis = await run_analysis(window, best)
            except Exception as e:
                log.warning("analysis %s: %s", window.symbol, e)
                continue

            decision = run_decision(window, best, market_analysis)

            if decision.action == DecisionAction.REJECT:
                continue

            trade = decision.setup
            if trade is None:
                continue

            status = (
                OpportunityStatus.VALIDATED
                if decision.action == DecisionAction.APPROVE
                else OpportunityStatus.WAITING
            )

            try:
                chart_analysis = explainer.build_analysis(
                    window,
                    best,
                    trade,
                    validation_note=decision.reason,
                )
            except Exception as e:
                log.warning("explainer %s: %s", window.symbol, e)
                chart_analysis = {"summary": decision.reason or ""}

            live_px = last_price(window.symbol)
            opp = Opportunity(
                symbol=window.symbol,
                interval=window.interval,
                status=status,
                best_match=best,
                all_matches=matches,
                market_analysis=market_analysis,
                decision=decision,
                trade=trade,
                ai_validated=decision.action == DecisionAction.APPROVE,
                ai_rationale=decision.reason,
                analysis=chart_analysis,
                cycle_id=result.cycle_id,
                candle_count=len(window.candles),
                last_price=live_px if live_px is not None else (window.candles[-1].close if window.candles else None),
                candles=list(window.candles),
            )

            if auto and decision.action == DecisionAction.APPROVE:
                try:
                    pos = open_from_opportunity(opp, store=store)
                    opp.status = OpportunityStatus.TRADED
                    log.info("Auto-trade opened %s pos=%s", opp.symbol, pos.id[:8])
                except RuntimeError as e:
                    log.info("Auto-trade skipped %s: %s", opp.symbol, e)

            opportunities.append(opp)
        except Exception as e:
            log.warning("Symbol %s failed: %s", window.symbol, e)
            result.errors.append(f"{window.symbol}: {e}")

    ranked = ranking.rank_opportunities(opportunities)
    result.opportunities = ranked
    result.finished_at = datetime.now(UTC)

    store.save_cycle(result)
    store.save_opportunities(ranked)

    log.info(
        "Cycle %s done — scanned=%d history_windows=%d opportunities=%d closed=%d errors=%d",
        result.cycle_id,
        len(result.symbols_scanned),
        len(windows),
        len(ranked),
        result.positions_closed,
        len(result.errors),
    )
    return result
