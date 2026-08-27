"""Binance Futures market data — WebSocket only.

Hard invariant: this module never calls Binance REST/HTTP endpoints.
All market observations used by XORA originate from WebSocket streams.

The hub uses a liquid USDT bootstrap universe so discovery doesn't depend on
Binance's all-market ticker stream being available from a particular network.
Closed candles are persisted locally so a restart can reuse observations that
were originally received over WebSocket. No HTTP history bootstrap exists.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import websockets

from xora_chart.domain.models import Candle, CandleWindow, DiscoveredCoin

log = logging.getLogger(__name__)

WS_BASE = "wss://fstream.binance.com"
MAX_CANDLES = 120
MIN_CANDLES = 20
STATE_PATH = Path(os.getenv("XORA_WS_STATE_PATH", "/app/state/ws_market.json"))

# WS-only bootstrap universe. These are subscription seeds, not trading signals.
# Discovery still ranks symbols using live ticker data received from Binance.
BOOTSTRAP_SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT", "BCHUSDT", "DOTUSDT",
    "TRXUSDT", "UNIUSDT", "SUIUSDT", "APTUSDT", "NEARUSDT", "ARBUSDT",
    "OPUSDT", "AAVEUSDT", "FILUSDT", "ETCUSDT", "ATOMUSDT", "INJUSDT",
    "SEIUSDT", "TIAUSDT", "WIFUSDT", "PEPEUSDT", "1000SHIBUSDT", "ENAUSDT",
)


class BinanceWSHub:
    _instance: "BinanceWSHub | None" = None

    def __init__(self) -> None:
        self._tickers: dict[str, dict[str, Any]] = {}
        # _candles contains CLOSED candles only. In-progress candles live in
        # _live_candles and are never used for strategy history/readiness.
        self._candles: dict[str, deque[Candle]] = defaultdict(lambda: deque(maxlen=MAX_CANDLES))
        self._live_candles: dict[str, Candle] = {}
        self._books: dict[str, dict[str, Any]] = {}
        self._mark: dict[str, dict[str, Any]] = {}
        self._desired_symbols: set[str] = set(BOOTSTRAP_SYMBOLS)
        self._watchlist_version = 0
        self._task: asyncio.Task | None = None
        self._running = False
        self._connected = False
        self._last_message_monotonic: float | None = None
        self._load_ws_state()

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
        self._connected = False
        self._save_ws_state()
        if self._task:
            self._task.cancel()

    def set_watchlist(self, symbols: list[str]) -> None:
        requested = {s.upper() for s in symbols if s}
        new = set(BOOTSTRAP_SYMBOLS) | requested
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
        if not buf or len(buf) < MIN_CANDLES:
            return None
        return CandleWindow(symbol=symbol.upper(), interval=interval, candles=list(buf)[-limit:])

    def candle_count(self, symbol: str) -> int:
        return len(self._candles.get(symbol.upper(), ()))

    def get_order_book(self, symbol: str) -> dict:
        return dict(self._books.get(symbol.upper(), {}))

    def get_mark(self, symbol: str) -> dict:
        return dict(self._mark.get(symbol.upper(), {}))

    def ticker_count(self) -> int:
        return len(self._tickers)

    def websocket_connected(self) -> bool:
        return self._connected

    def last_message_age_seconds(self) -> float | None:
        if self._last_message_monotonic is None:
            return None
        return max(0.0, time.monotonic() - self._last_message_monotonic)

    def ready_symbol_count(self) -> int:
        return sum(1 for candles in self._candles.values() if len(candles) >= MIN_CANDLES)

    async def _run_forever(self) -> None:
        log.info("Binance WS-only hub starting")
        while self._running:
            try:
                await self._session()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                log.warning("WS session error: %s — retry 2s", e)
                await asyncio.sleep(2)
        self._connected = False
        log.info("Binance WS-only hub stopped")

    async def _session(self) -> None:
        # Keep the all-market stream as an opportunistic source, but never rely
        # on it. Individual ticker streams provide deterministic bootstrap data.
        streams = ["!ticker@arr"]
        symbols = sorted(self._desired_symbols)[:40]
        for sym in symbols:
            s = sym.lower()
            streams.append(f"{s}@ticker")
            streams.append(f"{s}@kline_1m")
            streams.append(f"{s}@depth20@100ms")
            streams.append(f"{s}@markPrice@1s")

        url = f"{WS_BASE}/stream?streams=" + "/".join(streams)
        version = self._watchlist_version
        log.info("WS connect streams=%d symbols=%d", len(streams), len(symbols))

        async with websockets.connect(
            url, ping_interval=20, ping_timeout=20, max_size=8_000_000
        ) as ws:
            self._connected = True
            while self._running:
                if self._watchlist_version != version:
                    log.info("Watchlist version changed — reconnect")
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=25)
                except asyncio.TimeoutError:
                    continue

                self._last_message_monotonic = time.monotonic()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                data = msg.get("data", msg)
                stream = msg.get("stream", "")

                if stream == "!ticker@arr" or isinstance(data, list):
                    if isinstance(data, list):
                        for t in data:
                            self._store_ticker(t)
                elif stream.endswith("@ticker"):
                    self._store_ticker(data)
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
        self._connected = False

    def _store_ticker(self, ticker: dict[str, Any]) -> None:
        sym = (ticker.get("s") or "").upper()
        if sym:
            self._tickers[sym] = ticker

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

        if not bool(k.get("x")):
            self._live_candles[sym] = candle
            return

        self._live_candles.pop(sym, None)
        buf = self._candles[sym]
        if buf and buf[-1].open_time == candle.open_time:
            buf[-1] = candle
        else:
            buf.append(candle)
        self._save_ws_state()

    def _load_ws_state(self) -> None:
        try:
            if not STATE_PATH.exists():
                return
            raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            for sym, items in (raw.get("candles") or {}).items():
                buf = self._candles[sym.upper()]
                for item in items[-MAX_CANDLES:]:
                    buf.append(Candle.model_validate(item))
            log.info("Loaded WS-only candle cache for %d symbols", len(self._candles))
        except Exception as e:
            log.warning("Could not load WS candle cache: %s", e)

    def _save_ws_state(self) -> None:
        try:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "source": "binance_websocket_only",
                "candles": {
                    sym: [c.model_dump(mode="json") for c in list(buf)]
                    for sym, buf in self._candles.items()
                    if buf
                },
            }
            tmp = STATE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            tmp.replace(STATE_PATH)
        except Exception as e:
            log.debug("Could not persist WS candle cache: %s", e)


async def ensure_hub() -> BinanceWSHub:
    """Start the WebSocket hub and briefly wait for initial ticker messages."""
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
    log.info("WS-only discovery returned %d coins from %d live tickers", len(coins), hub.ticker_count())
    return coins


async def fetch_klines(symbol: str, interval: str = "1m", limit: int = 100) -> CandleWindow:
    hub = await ensure_hub()
    sym = symbol.upper()
    hub.set_watchlist(list(hub._desired_symbols | {sym}))
    window = hub.get_window(sym, interval=interval, limit=limit)
    if not window:
        count = hub.candle_count(sym)
        raise RuntimeError(
            f"WebSocket candle history not ready for {sym}: {count}/{MIN_CANDLES} closed bars collected"
        )
    return window


async def fetch_order_book(symbol: str, limit: int = 20) -> dict:
    hub = await ensure_hub()
    hub.set_watchlist(list(hub._desired_symbols | {symbol.upper()}))
    return hub.get_order_book(symbol)


async def fetch_premium_index(symbol: str) -> dict:
    hub = await ensure_hub()
    hub.set_watchlist(list(hub._desired_symbols | {symbol.upper()}))
    return hub.get_mark(symbol)


async def fetch_open_interest(symbol: str) -> dict:
    """Open interest is intentionally unavailable: no REST fallback is allowed."""
    return {"openInterest": None, "source": "unavailable_websocket_only"}
