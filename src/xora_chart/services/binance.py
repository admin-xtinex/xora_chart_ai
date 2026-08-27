"""Hybrid Binance Futures market data.

Historical closed candles come from REST.  Live prices/order-book/funding state
come from WebSockets.  A persisted WebSocket candle cache is retained only as a
backend recovery path when Binance REST is unavailable from the server location.
"""

from __future__ import annotations

import logging
from typing import Any

from xora_chart.domain.models import CandleWindow
from xora_chart.services import binance_ws
from xora_chart.services.binance_rest import (
    BinanceHistoryError,
    fetch_klines as fetch_klines_rest,
    window_from_rows,
)

log = logging.getLogger(__name__)

discover_coins = binance_ws.discover_coins
fetch_order_book = binance_ws.fetch_order_book
fetch_premium_index = binance_ws.fetch_premium_index
fetch_open_interest = binance_ws.fetch_open_interest


async def fetch_klines(symbol: str, interval: str = "1m", limit: int = 100) -> CandleWindow:
    """REST history first; persisted WS history only if the backend REST route is blocked."""
    try:
        return await fetch_klines_rest(symbol, interval=interval, limit=limit)
    except BinanceHistoryError as exc:
        hub = await binance_ws.ensure_hub()
        window = hub.get_window(symbol, interval=interval, limit=limit)
        if window:
            log.warning(
                "REST history unavailable for %s (%s); using persisted WebSocket recovery window",
                symbol.upper(),
                exc,
            )
            return window
        raise


def window_from_history(
    symbol: str,
    rows: list[Any],
    interval: str = "1m",
    limit: int = 100,
) -> CandleWindow:
    """Build the canonical historical window from browser-supplied Binance REST rows."""
    return window_from_rows(symbol, interval, rows, limit=limit)
