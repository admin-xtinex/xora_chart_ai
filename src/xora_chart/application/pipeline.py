"""Orchestrates one full scan cycle."""

from __future__ import annotations

import logging
from datetime import datetime

from xora_chart.application import discovery, explainer, market_data, matcher, ranking, trade_generator, validator
from xora_chart.domain.enums import OpportunityStatus
from xora_chart.domain.models import CycleResult, Opportunity
from xora_chart.persistence.store import Store

log = logging.getLogger(__name__)


async def run_cycle(store: Store | None = None) -> CycleResult:
    store = store or Store.instance()
    result = CycleResult()
    log.info("Cycle %s started", result.cycle_id)

    try:
        coins = await discovery.run_discovery()
        result.symbols_scanned = [c.symbol for c in coins]
    except Exception as e:
        log.exception("Discovery failed")
        result.errors.append(f"discovery: {e}")
        result.finished_at = datetime.utcnow()
        store.save_cycle(result)
        return result

    try:
        windows = await market_data.fetch_windows(coins)
    except Exception as e:
        log.exception("Market data failed")
        result.errors.append(f"market_data: {e}")
        result.finished_at = datetime.utcnow()
        store.save_cycle(result)
        return result

    opportunities: list[Opportunity] = []

    for window in windows:
        try:
            matches = matcher.match_window(window)
            if not matches:
                continue

            best = matches[0]
            accepted, rationale = await validator.validate(window, best)

            trade = trade_generator.generate_trade(window, best)
            if trade is None:
                continue

            analysis = explainer.build_analysis(window, best, trade, validation_note=rationale)

            opp = Opportunity(
                symbol=window.symbol,
                interval=window.interval,
                status=OpportunityStatus.VALIDATED if accepted else OpportunityStatus.REJECTED,
                best_match=best,
                all_matches=matches,
                trade=trade,
                ai_validated=accepted,
                ai_rationale=rationale,
                analysis=analysis,
                cycle_id=result.cycle_id,
                candle_count=len(window.candles),
                last_price=window.candles[-1].close if window.candles else None,
                candles=list(window.candles),
            )
            if accepted:
                opportunities.append(opp)
        except Exception as e:
            log.warning("Symbol %s failed: %s", window.symbol, e)
            result.errors.append(f"{window.symbol}: {e}")

    ranked = ranking.rank_opportunities(opportunities)
    result.opportunities = ranked
    result.finished_at = datetime.utcnow()

    store.save_cycle(result)
    store.save_opportunities(ranked)

    log.info(
        "Cycle %s done — scanned=%d opportunities=%d errors=%d",
        result.cycle_id,
        len(result.symbols_scanned),
        len(ranked),
        len(result.errors),
    )
    return result
