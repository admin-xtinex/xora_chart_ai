"""Binance USDT-M Futures market data via WebSocket only (no REST).

Streams:
  - !ticker@arr
  - <symbol>@kline_1m
  - <symbol>@depth20@100ms
  - <symbol>@markPrice@1s
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from typing import Any

import websockets

from xora_chart.domain.models import Candle, CandleWindow, DiscoveredCoin

log = logging.getLogger(__name__)

WS_BASE = "wss://fstream.binance.com"
MAX_CANDLES = 120


class BinanceWSHub:
    _instance: "BinanceWSHub | None" = None

    def __init__(self) -> None:
        self._tickers: dict[str, dict[str, Any]] = {}
        self._candles: dict[str, deque[Candle]] = defaultdict(lambda: deque(maxlen=MAX_CANDLES))
        self._books: dict[str, dict[str, Any]] = {}
        self._mark: dict[str, dict[str, Any]] = {}
        self._desired_symbols: set[str] = set()
        self._watchlist_version = 0
        self._task: asyncio.Task | None = None
        self._running = False

    @classmethod
    def instance(cls) -> "BinanceWSHub":
        if cls._instance is None:
            cls._instance = BinanceWSHub()
        return cls._instance

    async def ensure_started(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run_forever(), name="binance-ws-hub")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    def set_watchlist(self, symbols: list[str]) -> None:
        new = {s.upper() for s in symbols}
        if new != self._desired_symbols:
            self._desired_symbols = new
            self._watchlist_version += 1
            log.info("Watchlist updated (%d symbols) v%d", len(new), self._watchlist_version)

    def discover_coins(
        self,
        *,
        top_gainers: int = 5,
        top_losers: int = 5,
        top_volume: int = 5,
        trending: int = 5,
        quote_asset: str = "USDT",
        min_quote_volume: float = 500_000,
    ) -> list[DiscoveredCoin]:
        usdt = [
            t
            for sym, t in self._tickers.items()
            if sym.endswith(quote_asset)
            and float(t.get("q") or 0) >= min_quote_volume
        ]

        def pct(t: dict) -> float:
            return float(t.get("P") or 0)

        def vol(t: dict) -> float:
            return float(t.get("q") or 0)

        gainers = sorted(usdt, key=pct, reverse=True)[:top_gainers]
        losers = sorted(usdt, key=pct)[:top_losers]
        volume = sorted(usdt, key=vol, reverse=True)[:top_volume]
        trending_sorted = sorted(
            usdt, key=lambda t: abs(pct(t)) * (vol(t) ** 0.5), reverse=True
        )[:trending]

        seen: set[str] = set()
        result: list[DiscoveredCoin] = []

        def add(items: list[dict], source: str) -> None:
            for i, t in enumerate(items):
                sym = (t.get("s") or "").upper()
                if not sym or sym in seen:
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
        return result

    def get_window(self, symbol: str, interval: str = "1m", limit: int = 100) -> CandleWindow | None:
        buf = self._candles.get(symbol.upper())
        if not buf or len(buf) < 15:
            return None
        return CandleWindow(symbol=symbol.upper(), interval=interval, candles=list(buf)[-limit:])

    def get_order_book(self, symbol: str) -> dict:
        return dict(self._books.get(symbol.upper(), {}))

    def get_mark(self, symbol: str) -> dict:
        return dict(self._mark.get(symbol.upper(), {}))

    def ticker_count(self) -> int:
        return len(self._tickers)

    async def _run_forever(self) -> None:
        log.info("Binance WS hub starting")
        while self._running:
            try:
                await self._session()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("WS session error: %s — retry 2s", e)
                await asyncio.sleep(2)
        log.info("Binance WS hub stopped")

    async def _session(self) -> None:
        streams = ["!ticker@arr"]
        symbols = sorted(self._desired_symbols)[:30]
        for sym in symbols:
            s = sym.lower()
            streams.append(f"{s}@kline_1m")
            streams.append(f"{s}@depth20@100ms")
            streams.append(f"{s}@markPrice@1s")

        url = f"{WS_BASE}/stream?streams=" + "/".join(streams)
        version = self._watchlist_version
        log.info("WS connect streams=%d symbols=%d", len(streams), len(symbols))

        async with websockets.connect(
            url, ping_interval=20, ping_timeout=20, max_size=8_000_000
        ) as ws:
            while self._running:
                if self._watchlist_version != version:
                    log.info("Watchlist version changed — reconnect")
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=25)
                except asyncio.TimeoutError:
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                data = msg.get("data", msg)
                stream = msg.get("stream", "")

                if stream == "!ticker@arr" or isinstance(data, list):
                    if isinstance(data, list):
                        for t in data:
                            sym = (t.get("s") or "").upper()
                            if sym:
                                self._tickers[sym] = t
                elif "@kline_" in stream:
                    self._handle_kline(data)
                elif "@depth" in stream:
                    sym = stream.split("@")[0].upper()
                    self._books[sym] = {
                        "bids": data.get("b") or [],
                        "asks": data.get("a") or [],
                    }
                elif "@markPrice" in stream:
                    sym = (data.get("s") or "").upper()
                    if sym:
                        self._mark[sym] = {
                            "symbol": sym,
                            "markPrice": data.get("p"),
                            "lastFundingRate": data.get("r"),
                            "nextFundingTime": data.get("T"),
                        }

    def _handle_kline(self, data: dict) -> None:
        k = data.get("k") or {}
        sym = (data.get("s") or k.get("s") or "").upper()
        if not sym or "t" not in k:
            return
        try:
            candle = Candle(
                open_time=int(k["t"]),
                open=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                close_time=int(k.get("T") or 0),
            )
        except (TypeError, ValueError):
            return

        buf = self._candles[sym]
        if buf and buf[-1].open_time == candle.open_time:
            buf[-1] = candle
        else:
            buf.append(candle)


async def ensure_hub() -> BinanceWSHub:
    hub = BinanceWSHub.instance()
    await hub.ensure_started()
    for _ in range(50):
        if hub.ticker_count() > 10:
            break
        await asyncio.sleep(0.2)
    return hub


async def discover_coins(**kwargs) -> list[DiscoveredCoin]:
    hub = await ensure_hub()
    coins = hub.discover_coins(**kwargs)
    if coins:
        hub.set_watchlist([c.symbol for c in coins])
        # wait for reconnect + some kline updates
        await asyncio.sleep(2.5)
    return coins


async def fetch_klines(symbol: str, interval: str = "1m", limit: int = 100) -> CandleWindow:
    hub = await ensure_hub()
    hub.set_watchlist(list(hub._desired_symbols | {symbol.upper()}))
    for _ in range(40):
        w = hub.get_window(symbol, interval=interval, limit=limit)
        if w and len(w.candles) >= 15:
            return w
        await asyncio.sleep(0.4)
    w = hub.get_window(symbol, interval=interval, limit=limit)
    if not w:
        raise RuntimeError(f"No WS candle buffer for {symbol} yet (warming up)")
    return w


async def fetch_order_book(symbol: str, limit: int = 20) -> dict:
    hub = await ensure_hub()
    return hub.get_order_book(symbol) or {"bids": [], "asks": []}


async def fetch_premium_index(symbol: str) -> dict:
    hub = await ensure_hub()
    return hub.get_mark(symbol) or {"lastFundingRate": 0, "markPrice": None}


async def fetch_open_interest(symbol: str) -> dict:
    return {"openInterest": 0}
