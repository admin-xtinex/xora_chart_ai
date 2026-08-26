"""Binance USDT-M Futures market data helpers."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from xora_chart.domain.models import Candle, CandleWindow, DiscoveredCoin

log = logging.getLogger(__name__)

FAPI = "https://fapi.binance.com"


async def _get(path: str, params: dict | None = None) -> Any:
    url = f"{FAPI}{path}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params or {})
        r.raise_for_status()
        return r.json()


async def fetch_ticker_24h() -> list[dict]:
    return await _get("/fapi/v1/ticker/24hr")


async def discover_coins(
    *,
    top_gainers: int = 5,
    top_losers: int = 5,
    top_volume: int = 5,
    trending: int = 5,
    quote_asset: str = "USDT",
    min_quote_volume: float = 500_000,
) -> list[DiscoveredCoin]:
    tickers = await fetch_ticker_24h()

    usdt = [
        t
        for t in tickers
        if t.get("symbol", "").endswith(quote_asset)
        and float(t.get("quoteVolume") or 0) >= min_quote_volume
    ]

    def pct(t: dict) -> float:
        return float(t.get("priceChangePercent") or 0)

    def vol(t: dict) -> float:
        return float(t.get("quoteVolume") or 0)

    gainers = sorted(usdt, key=pct, reverse=True)[:top_gainers]
    losers = sorted(usdt, key=pct)[:top_losers]
    volume = sorted(usdt, key=vol, reverse=True)[:top_volume]
    trending_sorted = sorted(usdt, key=lambda t: abs(pct(t)) * (vol(t) ** 0.5), reverse=True)[
        :trending
    ]

    seen: set[str] = set()
    result: list[DiscoveredCoin] = []

    def add(items: list[dict], source: str) -> None:
        for i, t in enumerate(items):
            sym = t["symbol"]
            if sym in seen:
                continue
            seen.add(sym)
            result.append(
                DiscoveredCoin(
                    symbol=sym,
                    source=source,
                    rank_in_source=i + 1,
                    price_change_pct=pct(t),
                    quote_volume=vol(t),
                )
            )

    add(gainers, "gainer")
    add(losers, "loser")
    add(volume, "volume")
    add(trending_sorted, "trending")

    log.info("Discovered %d coins", len(result))
    return result


async def fetch_klines(symbol: str, interval: str = "1m", limit: int = 100) -> CandleWindow:
    raw = await _get(
        "/fapi/v1/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
    )
    candles = [
        Candle(
            open_time=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            close_time=int(row[6]),
        )
        for row in raw
    ]
    return CandleWindow(symbol=symbol, interval=interval, candles=candles)


async def fetch_order_book(symbol: str, limit: int = 20) -> dict:
    """Top-of-book depth for imbalance."""
    return await _get("/fapi/v1/depth", params={"symbol": symbol, "limit": limit})


async def fetch_premium_index(symbol: str) -> dict:
    """Mark price + last funding rate."""
    return await _get("/fapi/v1/premiumIndex", params={"symbol": symbol})


async def fetch_open_interest(symbol: str) -> dict:
    return await _get("/fapi/v1/openInterest", params={"symbol": symbol})
