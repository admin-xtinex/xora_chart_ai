from __future__ import annotations

import asyncio
import logging
from typing import Any

from xora_chart.config import load_config
from xora_chart.domain.models import CandleWindow, DiscoveredCoin
from xora_chart.services import binance

log = logging.getLogger(__name__)


async def fetch_windows(
    coins: list[DiscoveredCoin],
    histories: dict[str, list[Any]] | None = None,
) -> list[CandleWindow]:
    """Load closed historical windows for the scan.

    Browser-supplied Binance Futures REST rows take priority.  Missing symbols use
    the backend REST path, which itself has a persisted WebSocket recovery window.
    """
    cfg = load_config().get("market_data", {})
    interval = cfg.get("interval", "1m")
    limit = int(cfg.get("candle_limit", 100))
    minimum = int(cfg.get("minimum_history_candles", cfg.get("minimum_ws_candles", 20)))
    concurrency = max(1, int(cfg.get("history_concurrency", 5)))

    if not coins:
        log.warning("No coins to fetch windows for")
        return []

    history_map = {str(k).upper(): v for k, v in (histories or {}).items()}
    semaphore = asyncio.Semaphore(concurrency)

    async def one(symbol: str) -> CandleWindow | None:
        try:
            async with semaphore:
                rows = history_map.get(symbol.upper())
                if rows:
                    w = binance.window_from_history(symbol, rows, interval=interval, limit=limit)
                else:
                    w = await binance.fetch_klines(symbol, interval=interval, limit=limit)
            if w and len(w.candles) >= minimum:
                return w
            log.warning("%s: only %d historical candles", symbol, len(w.candles) if w else 0)
            return None
        except Exception as e:
            log.warning("Failed historical klines for %s: %s", symbol, e)
            return None

    results = await asyncio.gather(*[one(c.symbol) for c in coins])
    windows = [w for w in results if w is not None and len(w.candles) >= minimum]
    log.info("Loaded %d/%d historical candle windows", len(windows), len(coins))
    return windows
