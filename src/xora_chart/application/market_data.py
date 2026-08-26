from __future__ import annotations

import asyncio
import logging

from xora_chart.config import load_config
from xora_chart.domain.models import CandleWindow, DiscoveredCoin
from xora_chart.services import binance

log = logging.getLogger(__name__)


async def fetch_windows(coins: list[DiscoveredCoin]) -> list[CandleWindow]:
    cfg = load_config().get("market_data", {})
    interval = cfg.get("interval", "1m")
    limit = int(cfg.get("candle_limit", 100))

    async def one(symbol: str) -> CandleWindow | None:
        try:
            return await binance.fetch_klines(symbol, interval=interval, limit=limit)
        except Exception as e:
            log.warning("Failed klines for %s: %s", symbol, e)
            return None

    results = await asyncio.gather(*[one(c.symbol) for c in coins])
    return [w for w in results if w is not None]
