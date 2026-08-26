"""Binance USDT-M Futures market data via WebSocket only (no REST).

Streams used:
  - !ticker@arr          → discovery (gainers / losers / volume)
  - <symbol>@kline_1m    → rolling candle buffers
  - <symbol>@depth20@100ms → order book imbalance
  - <symbol>@markPrice@1s  → funding / mark price

A background hub keeps subscriptions warm so the scan cycle reads
from in-memory buffers instead of HTTP.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from xora_chart.domain.models import Candle, CandleWindow, DiscoveredCoin

log = logging.getLogger(__name__)

WS_BASE = "wss://fstream.binance.com"
MAX_CANDLES = 120


class BinanceWSHub:
    """Singleton live market-data hub."""

    _instance: "BinanceWSHub | None" = None

    def __init__(self) -> None:
        self._tickers: dict[str, dict[str, Any]] = {}
        self._candles: dict[str, deque[Candle]] = defaultdict(lambda: deque(maxlen=MAX_CANDLES))
        self._books: dict[str, dict[str, Any]] = {}
        self._mark: dict[str, dict[str, Any]] = {}
        self._oi_proxy: dict[str, float] = {}  # not on public WS; leave empty
        self._desired_symbols: set[str] = set()
        self._task: asyncio.Task | None = None
        self._running = False
        self._lock = asyncio.Lock()
        self._last_ticker_ts = 0.0

    @classmethod
    def instance(cls) -> "BinanceWSHub":
        if cls._instance is None:
            cls._instance = BinanceWSHub()
        return cls._instance

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_forever(), name="binance-ws-hub")
        except RuntimeError:
            log.warning("No running loop — hub will start on first await ensure_started()")

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
        self._desired_symbols = {s.upper() for s in symbols}

    # ── Public reads (used by engines) ───────────────────────────────────────

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
            and float(t.get("q") or t.get("quoteVolume") or 0) >= min_quote_volume
        ]

        def pct(t: dict) -> float:
            return float(t.get("P") or t.get("priceChangePercent") or 0)

        def vol(t: dict) -> float:
            return float(t.get("q") or t.get("quoteVolume") or 0)

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
                sym = (t.get("s") or t.get("symbol") or "").upper()
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
        if not buf or len(buf) < 20:
            return None
        candles = list(buf)[-limit:]
        return CandleWindow(symbol=symbol.upper(), interval=interval, candles=candles)

    def get_order_book(self, symbol: str) -> dict:
        return dict(self._books.get(symbol.upper(), {}))

    def get_mark(self, symbol: str) -> dict:
        return dict(self._mark.get(symbol.upper(), {}))

    def ticker_count(self) -> int:
        return len(self._tickers)

    def candle_count(self, symbol: str) -> int:
        return len(self._candles.get(symbol.upper(), ()))

    # ── Background loop ──────────────────────────────────────────────────────

    async def _run_forever(self) -> None:
        log.info("Binance WS hub starting")
        while self._running:
            try:
                await self._session()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("WS hub session ended: %s — reconnect in 3s", e)
                await asyncio.sleep(3)
        log.info("Binance WS hub stopped")

    async def _session(self) -> None:
        # Always listen to all mini tickers for discovery
        streams = ["!ticker@arr"]
        # Dynamic per-symbol streams rebuilt each reconnect
        symbols = sorted(self._desired_symbols)[:40]
        for sym in symbols:
            s = sym.lower()
            streams.append(f"{s}@kline_1m")
            streams.append(f"{s}@depth20@100ms")
            streams.append(f"{s}@markPrice@1s")

        path = "/stream?streams=" + "/".join(streams)
        url = WS_BASE + path
        log.info("WS connect streams=%d symbols=%d", len(streams), len(symbols))

        async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=8_000_000) as ws:
            last_rebuild = time.time()
            while self._running:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                except asyncio.TimeoutError:
                    # rebuild subscription set if watchlist changed
                    if time.time() - last_rebuild > 45:
                        break
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                data = msg.get("data", msg)
                stream = msg.get("stream", "")

                if stream == "!ticker@arr" or isinstance(data, list):
                    self._handle_tickers(data if isinstance(data, list) else [])
                elif "@kline_" in stream:
                    self._handle_kline(data)
                elif "@depth" in stream:
                    self._handle_depth(stream, data)
                elif "@markPrice" in stream:
                    self._handle_mark(data)

                # Hot-reload streams when watchlist changes
                if time.time() - last_rebuild > 60:
                    current = set()
                    for s in streams:
                        if s.startswith("!") or "@" not in s:
                            continue
                        current.add(s.split("@")[0].upper())
                    if current != {x.upper() for x in self._desired_symbols}:
                        log.info("Watchlist changed — reconnecting streams")
                        break
                    last_rebuild = time.time()

    def _handle_tickers(self, arr: list) -> None:
        for t in arr:
            sym = (t.get("s") or "").upper()
            if not sym:
                continue
            self._tickers[sym] = t
        self._last_ticker_ts = time.time()

    def _handle_kline(self, data: dict) -> None:
        k = data.get("k") or {}
        sym = (data.get("s") or k.get("s") or "").upper()
        if not sym:
            return
        try:
            candle = Candle(
                open_time=int(k["t"]),
                open=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                close_time=int(k["T"]),
            )
        except (KeyError, TypeError, ValueError):
            return

        buf = self._candles[sym]
        if buf and buf[-1].open_time == candle.open_time:
            buf[-1] = candle
        else:
            # only append when previous closed or first
            if not buf or k.get("x") or candle.open_time > buf[-1].open_time:
                if buf and not k.get("x") and candle.open_time == buf[-1].open_time:
                    buf[-1] = candle
                elif buf and candle.open_time > buf[-1].open_time:
                    buf.append(candle)
                elif not buf:
                    buf.append(candle)
                else:
                    buf[-1] = candle

    def _handle_depth(self, stream: str, data: dict) -> None:
        sym = stream.split("@")[0].upper() if "@" in stream else ""
        if not sym:
            return
        self._books[sym] = {
            "bids": data.get("b") or data.get("bids") or [],
            "asks": data.get("a") or data.get("asks") or [],
        }

    def _handle_mark(self, data: dict) -> None:
        sym = (data.get("s") or "").upper()
        if not sym:
            return
        self._mark[sym] = {
            "symbol": sym,
            "markPrice": data.get("p") or data.get("markPrice"),
            "lastFundingRate": data.get("r") or data.get("lastFundingRate"),
            "nextFundingTime": data.get("T") or data.get("nextFundingTime"),
        }


# ── Module-level helpers matching previous binance.py surface ────────────────

async def ensure_hub() -> BinanceWSHub:
    hub = BinanceWSHub.instance()
    await hub.ensure_started()
    # wait briefly for first ticker snapshot
    for _ in range(40):
        if hub.ticker_count() > 10:
            break
        await asyncio.sleep(0.25)
    return hub


async def discover_coins(**kwargs) -> list[DiscoveredCoin]:
    hub = await ensure_hub()
    coins = hub.discover_coins(**kwargs)
    if coins:
        hub.set_watchlist([c.symbol for c in coins])
        # allow kline streams to attach on next reconnect cycle; nudge by waiting
        await asyncio.sleep(1.5)
    return coins


async def fetch_klines(symbol: str, interval: str = "1m", limit: int = 100) -> CandleWindow:
    hub = await ensure_hub()
    hub.set_watchlist(list(hub._desired_symbols | {symbol.upper()}))
    # wait for buffer to grow
    for _ in range(30):
        w = hub.get_window(symbol, interval=interval, limit=limit)
        if w and len(w.candles) >= min(30, limit):
            return w
        await asyncio.sleep(0.5)
    w = hub.get_window(symbol, interval=interval, limit=limit)
    if not w:
        raise RuntimeError(f"No WS candle buffer yet for {symbol} — hub warming up")
    return w


async def fetch_order_book(symbol: str, limit: int = 20) -> dict:
    hub = await ensure_hub()
    book = hub.get_order_book(symbol)
    if book:
        return book
    return {"bids": [], "asks": []}


async def fetch_premium_index(symbol: str) -> dict:
    hub = await ensure_hub()
    mark = hub.get_mark(symbol)
    if mark:
        return mark
    return {"lastFundingRate": 0, "markPrice": None}


async def fetch_open_interest(symbol: str) -> dict:
    # Open interest is not on the public combined WS without auth; return neutral.
    return {"openInterest": 0}
