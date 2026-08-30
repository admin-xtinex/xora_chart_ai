"""Binance USD-M Futures historical candles over REST.

XORA deliberately separates transport responsibilities:
- REST: historical, closed kline bootstrap only.
- WebSocket: live prices, order book and realtime market state.

The backend REST request is useful in local/self-hosted environments.  Production
GCP can receive HTTP 451 from Binance, so the browser may supply the exact same
public kline payload over XORA's application WebSocket.  `window_from_rows` is the
single parser for both paths so analysis semantics stay identical.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from xora_chart.domain.models import Candle, CandleWindow

REST_BASE = os.getenv("BINANCE_FUTURES_REST_BASE", "https://fapi.binance.com").rstrip("/")
MIN_HISTORY_CANDLES = 20


class BinanceHistoryError(RuntimeError):
    """Historical kline data could not be obtained or validated."""


def window_from_rows(
    symbol: str,
    interval: str,
    rows: list[Any],
    *,
    limit: int = 100,
) -> CandleWindow:
    """Parse Binance kline tuples and keep only exchange-closed candles."""
    if not isinstance(rows, list):
        raise BinanceHistoryError(f"Invalid Binance kline history for {symbol}")

    now_ms = int(time.time() * 1000)
    candles: list[Candle] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 7:
            continue
        try:
            candle = Candle(
                open_time=int(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                close_time=int(row[6]),
            )
        except (TypeError, ValueError):
            continue

        # Binance includes the currently forming candle in /klines.  Canonical
        # structure analysis must be based on closed candles only.
        if candle.close_time is not None and candle.close_time > now_ms:
            continue
        candles.append(candle)

    candles = candles[-max(1, int(limit)) :]
    if len(candles) < MIN_HISTORY_CANDLES:
        raise BinanceHistoryError(
            f"Only {len(candles)}/{MIN_HISTORY_CANDLES} closed REST candles available for {symbol.upper()}"
        )

    return CandleWindow(symbol=symbol.upper(), interval=interval, candles=candles)


async def fetch_klines(
    symbol: str,
    interval: str = "1m",
    limit: int = 100,
) -> CandleWindow:
    """Fetch recent Binance Futures history; live updates are intentionally not read here."""
    sym = symbol.upper()
    request_limit = min(1000, max(MIN_HISTORY_CANDLES + 1, int(limit) + 1))
    url = f"{REST_BASE}/fapi/v1/klines"

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            headers={"User-Agent": "XORA-Chart-AI/0.6"},
        ) as client:
            response = await client.get(
                url,
                params={"symbol": sym, "interval": interval, "limit": request_limit},
            )
    except httpx.HTTPError as exc:
        raise BinanceHistoryError(f"Binance Futures REST history connection failed for {sym}: {exc}") from exc

    if response.status_code != 200:
        detail = response.text.replace("\n", " ")[:180]
        if response.status_code == 451:
            raise BinanceHistoryError(
                f"Binance Futures REST history is geo-blocked from the backend (HTTP 451) for {sym}"
            )
        raise BinanceHistoryError(
            f"Binance Futures REST history HTTP {response.status_code} for {sym}: {detail}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise BinanceHistoryError(f"Invalid Binance Futures REST JSON for {sym}") from exc

    return window_from_rows(sym, interval, payload, limit=limit)
