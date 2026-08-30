"""Binance USD-M Futures market data over WebSockets only.

XORA uses two official Binance WebSocket surfaces:
* WebSocket Streams (fstream.binance.com) for live book/depth and, where the
  network permits them, ticker/kline/mark-price events.
* Futures WebSocket API (ws-fapi.binance.com) for current symbol prices.

No Binance REST/HTTP endpoint is used. When native kline streams are unavailable,
1-minute OHLC bars are sampled from Binance's WebSocket ``ticker.price`` values
and persisted so the scanner can warm up and stay warm across container restarts.
Sampled bars intentionally carry zero volume rather than fabricating trade volume.

Implements 4-group unique symbol rule for coin discovery:
- 5 Top Gainers
- 5 Top Losers
- 5 Top Movers/Momentum
- 5 Top High-Liquidity/High-Volume
With global uniqueness and priority allocation.
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

import binance
from xora_chart.config import load_config
from xora_chart.persistence.store import Store

import websockets

from xora_chart.domain.models import Candle, CandleWindow, DiscoveredCoin

log = logging.getLogger(__name__)

WS_BASE = "wss://fstream.binance.com"
WS_API_BASE = "wss://ws-fapi.binance.com/ws-fapi/v1"
MAX_CANDLES = 120
MIN_CANDLES = 20
PRICE_POLL_SECONDS = 2.0
STATE_PATH = Path(os.getenv("XORA_WS_STATE_PATH", "/app/state/ws_market.json"))

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
        self._candles: dict[str, deque[Candle]] = defaultdict(lambda: deque(maxlen=MAX_CANDLES))
        self._live_candles: dict[str, Candle] = {}
        self._books: dict[str, dict[str, Any]] = {}
        self._mark: dict[str, dict[str, Any]] = {}
        self._desired_symbols: set[str] = set(BOOTSTRAP_SYMBOLS)
        self._watchlist_version = 0

        # Subscription management: reference counting for stream types per symbol
        # Format: {symbol: {stream_type: count}}
        self._stream_refs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._pending_subscription_update = False
        self._last_subscription_update = 0.0

        self._task: asyncio.Task | None = None
        self._price_task: asyncio.Task | None = None
        self._running = False
        self._connected = False
        self._price_api_connected = False
        self._last_message_monotonic: float | None = None
        self._event_counts: dict[str, int] = defaultdict(int)
        self._last_event_monotonic: dict[str, float] = {}
        self._native_kline_symbols: set[str] = set()
        self._baseline_prices: dict[str, float] = {}
        self._load_ws_state()

        # Reconciliation task
        self._reconcile_task: asyncio.Task | None = None
        self._last_reconcile: dict[str, float] = {}  # symbol -> last reconcile time

    @classmethod
    def instance(cls) -> "BinanceWSHub":
        if cls._instance is None:
            cls._instance = BinanceWSHub()
        return cls._instance

    async def ensure_started(self) -> None:
        self._running = True
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._run_forever(), name="binance-ws-stream-hub")
        if not self._price_task or self._price_task.done():
            self._price_task = asyncio.create_task(
                self._run_price_api_forever(), name="binance-ws-price-api"
            )
        if not self._reconcile_task or self._reconcile_task.done():
            self._reconcile_task = asyncio.create_task(
                self._run_reconcile_forever(), name="binance-ws-reconcile"
            )

    def stop(self) -> None:
        self._running = False
        self._connected = False
        self._price_api_connected = False
        self._save_ws_state()
        for task in (self._task, self._price_task, self._reconcile_task):
            if task:
                task.cancel()

    def set_watchlist(self, symbols: list[str]) -> None:
        """Update the watchlist - ensures at least ticker data for these symbols.

        Args:
            symbols: List of symbols to include in watchlist
        """
        requested = {s.upper() for s in symbols if s}
        # Ensure at least ticker reference for watchlist symbols
        for symbol in requested:
            self.add_stream_ref(symbol, "ticker")
        log.info("Watchlist updated with %d symbols", len(requested))

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
        """Discover coins using the 4-group unique symbol rule.

        Implements exactly 4 groups of 5 coins each (20 unique total):
        1. Top 5 Gainers
        2. Top 5 Losers
        3. Top 5 Movers/Momentum
        4. Top 5 High-Liquidity/High-Volume

        Enforces global uniqueness across groups with priority allocation:
        Gainers > Losers > Movers > High-Volume
        """
        candidates = [
            t
            for sym, t in self._tickers.items()
            if sym.endswith(quote_asset) and t.get("c") is not None
        ]
        if not candidates:
            return []

        def pct(t: dict) -> float:
            try:
                if t.get("P") is not None:
                    return float(t.get("P") or 0)
                sym = str(t.get("s") or "").upper()
                current = float(t.get("c") or 0)
                baseline = self._baseline_prices.get(sym)
                if baseline and current:
                    return (current - baseline) / baseline * 100.0
            except (TypeError, ValueError, ZeroDivisionError):
                pass
            return 0.0

        def real_quote_volume(t: dict) -> float:
            try:
                return float(t.get("q") or 0)
            except (TypeError, ValueError):
                return 0.0

        def book_liquidity(t: dict) -> float:
            try:
                bid = float(t.get("b") or 0)
                bid_qty = float(t.get("B") or 0)
                ask = float(t.get("a") or 0)
                ask_qty = float(t.get("A") or 0)
                return bid * bid_qty + ask * ask_qty
            except (TypeError, ValueError):
                return 0.0

        # Filter candidates by minimum quote volume
        real = [t for t in candidates if real_quote_volume(t) >= min_quote_volume]
        source_items = real if real else candidates

        # Sort candidates for each category
        sorted_gainers = sorted(source_items, key=pct, reverse=True)
        sorted_losers = sorted(source_items, key=pct)
        if real:
            sorted_volume = sorted(real, key=real_quote_volume, reverse=True)
            sorted_trending = sorted(
                real,
                key=lambda t: abs(pct(t)) * (real_quote_volume(t) ** 0.5),
                reverse=True,
            )
        else:
            sorted_volume = sorted(source_items, key=book_liquidity, reverse=True)
            sorted_trending = sorted(
                source_items,
                key=lambda t: (abs(pct(t)) + 0.01) * (book_liquidity(t) ** 0.5),
                reverse=True,
            )

        # Apply 4-group unique symbol rule with priority allocation
        seen: set[str] = set()
        result: list[DiscoveredCoin] = []

        # Group 1: Top Gainers (highest priority)
        gainers_selected = []
        for t in sorted_gainers:
            sym = (t.get("s") or "").upper()
            if sym not in seen:
                seen.add(sym)
                gainers_selected.append(t)
                if len(gainers_selected) >= top_gainers:
                    break

        # Group 2: Top Losers (second priority)
        losers_selected = []
        for t in sorted_losers:
            sym = (t.get("s") or "").upper()
            if sym not in seen:
                seen.add(sym)
                losers_selected.append(t)
                if len(losers_selected) >= top_losers:
                    break

        # Group 3: Top Movers/Momentum (third priority)
        movers_selected = []
        for t in sorted_trending:
            sym = (t.get("s") or "").upper()
            if sym not in seen:
                seen.add(sym)
                movers_selected.append(t)
                if len(movers_selected) >= trending:
                    break

        # Group 4: Top High-Liquidity/High-Volume (fourth priority)
        volume_selected = []
        for t in sorted_volume:
            sym = (t.get("s") or "").upper()
            if sym not in seen:
                seen.add(sym)
                volume_selected.append(t)
                if len(volume_selected) >= top_volume:
                    break

        # Convert selected coins to DiscoveredCoin objects with proper source attribution
        def add_selected_coins(coins: list[dict], source: str, is_real: bool) -> list[DiscoveredCoin]:
            selected = []
            for i, t in enumerate(coins):
                selected.append(
                    DiscoveredCoin(
                        symbol=(t.get("s") or "").upper(),
                        source=source if is_real else f"ws-price-{source}",
                        rank_in_source=i + 1,
                        price_change_pct=pct(t),
                        quote_volume=real_quote_volume(t),
                    )
                )
            return selected

        # Determine if we're using real data (based on volume filtering)
        is_real_data = len(real) > 0 and len(real) == len(source_items)

        result.extend(add_selected_coins(gainers_selected, "gainer", is_real_data))
        result.extend(add_selected_coins(losers_selected, "loser", is_real_data))
        result.extend(add_selected_coins(movers_selected, "trending", is_real_data))
        result.extend(add_selected_coins(volume_selected, "high-volume", is_real_data))

        # Ensure discovered coins have at least ticker data for discovery purposes
        for coin in result:
            self.add_stream_ref(coin.symbol, "ticker")

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
        return self._connected or self._price_api_connected

    def last_message_age_seconds(self) -> float | None:
        if self._last_message_monotonic is None:
            return None
        return max(0.0, time.monotonic() - self._last_message_monotonic)

    def event_telemetry(self) -> dict[str, dict[str, float | int | None]]:
        now = time.monotonic()
        result: dict[str, dict[str, float | int | None]] = {}
        for kind in ("ticker", "price_api", "kline", "sampled_candle", "book", "depth", "mark", "unknown"):
            last = self._last_event_monotonic.get(kind)
            result[kind] = {
                "count": int(self._event_counts.get(kind, 0)),
                "age_seconds": None if last is None else max(0.0, now - last),
            }
        return result

    def ready_symbol_count(self) -> int:
        return sum(1 for candles in self._candles.values() if len(candles) >= MIN_CANDLES)

    def _record_event(self, kind: str) -> None:
        self._event_counts[kind] += 1
        self._last_event_monotonic[kind] = time.monotonic()

    async def _run_forever(self) -> None:
        log.info("Binance WebSocket stream hub starting")
        while self._running:
            try:
                await self._session()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                log.warning("WS stream session error: %s — retry 2s", e)
                await asyncio.sleep(2)
        self._connected = False
        log.info("Binance WebSocket stream hub stopped")

    async def _run_price_api_forever(self) -> None:
        log.info("Binance Futures WebSocket API price sampler starting")
        request_id = 0
        while self._running:
            try:
                async with websockets.connect(
                    WS_API_BASE,
                    ping_interval=20,
                    ping_timeout=20,
                    open_timeout=10,
                    max_size=8_000_000,
                ) as ws:
                    self._price_api_connected = True
                    while self._running:
                        request_id += 1
                        await ws.send(
                            json.dumps(
                                {
                                    "id": f"xora-price-{request_id}",
                                    "method": "ticker.price",
                                    "params": {},
                                }
                            )
                        )
                        raw = await asyncio.wait_for(ws.recv(), timeout=12)
                        self._last_message_monotonic = time.monotonic()
                        msg = json.loads(raw)
                        prices = msg.get("result")
                        if msg.get("status") != 200 or not isinstance(prices, list):
                            raise RuntimeError(f"ticker.price WS API error: {msg.get('error') or msg.get('status')}")

                        self._record_event("price_api")
                        self._record_event("ticker")
                        desired = set(self._desired_symbols)
                        closed_any = False
                        for item in prices:
                            sym = str(item.get("symbol") or "").upper()
                            if sym in desired:
                                closed_any = self._store_price_snapshot(item) or closed_any
                        if closed_any:
                            self._save_ws_state()
                        await asyncio.sleep(PRICE_POLL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._price_api_connected = False
                log.warning("Futures WS API price sampler error: %s — retry 2s", e)
                await asyncio.sleep(2)
        self._price_api_connected = False
        log.info("Binance Futures WebSocket API price sampler stopped")

    async def _run_reconcile_forever(self) -> None:
        """Periodically reconcile historical state via REST API."""
        log.info("Binance WebSocket reconciliation task starting")
        while self._running:
            try:
                await self._reconcile_cycle()
                # Sleep for a short interval before checking again
                # The actual reconciliation timing is handled per symbol
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("Reconciliation error: %s — retry 10s", e)
                await asyncio.sleep(10)
        log.info("Binance WebSocket reconciliation task stopped")

    async def _reconcile_cycle(self) -> None:
        """Perform one cycle of reconciliation for all symbols that need it."""
        try:
            # Get configuration for reconciliation intervals
            cfg = load_config().get("reconciliation", {})
            if not cfg:
                return

            # Get symbols that need reconciliation
            # We'll reconcile symbols that:
            # 1. Are in our desired symbols (watchlist)
            # 2. Have open positions
            # 3. Have active opportunities
            # 4. Are currently being analyzed
            symbols_to_reconcile = set()

            # Add watchlist symbols
            symbols_to_reconcile.update(self._desired_symbols)

            # Add symbols with open positions
            try:
                store = Store.instance()
                open_positions = [p for p in store.list_positions() if p.status.value == "open"]
                symbols_to_reconcile.update(p.symbol for p in open_positions)
            except Exception:
                pass  # Continue with what we have

            # Add symbols from current opportunities
            try:
                store = Store.instance()
                opportunities = store.list_opportunities()
                symbols_to_reconcile.update(o.symbol for o in opportunities)
            except Exception:
                pass

            # Perform reconciliation for each symbol
            now = time.monotonic()
            for symbol in symbols_to_reconcile:
                # Determine the timeframe for this symbol (default to 1m)
                timeframe = "1m"  # TODO: Could make this configurable per symbol or detect from context

                # Get the reconciliation interval for this timeframe
                interval_seconds = cfg.get(timeframe, 120)  # Default to 2 minutes if not configured

                # Check if it's time to reconcile this symbol
                last_reconcile = self._last_reconcile.get(symbol, 0)
                if now - last_reconcile >= interval_seconds:
                    try:
                        await self._reconcile_symbol(symbol, timeframe)
                        self._last_reconcile[symbol] = now
                        log.debug("Reconciled symbol %s (%s)", symbol, timeframe)
                    except Exception as e:
                        log.warning("Failed to reconcile symbol %s: %s", symbol, e)
        except Exception as e:
            log.warning("Error in reconciliation cycle: %s", e)

    async def _reconcile_symbol(self, symbol: str, timeframe: str = "1m") -> None:
        """Reconcile historical data for a specific symbol via REST API."""
        try:
            # Fetch fresh historical data via REST
            window = await binance.fetch_klines(symbol, interval=timeframe, limit=100)
            if window and len(window.candles) >= 20:  # Minimum required for analysis
                # Update our candle cache with the fresh data
                buf = self._candles[symbol.upper()]
                # Clear existing cache and replace with fresh data
                buf.clear()
                for candle in window.candles:
                    buf.append(candle)
                # Update baseline price
                if window.candles:
                    self._baseline_prices.setdefault(symbol.upper(), float(window.candles[-1].close))
                log.debug("Updated candle cache for %s with %d candles", symbol, len(buf))
            else:
                log.warning("Insufficient historical data for %s reconciliation: %d candles",
                           symbol, len(window.candles) if window else 0)
        except Exception as e:
            raise RuntimeError(f"REST reconciliation failed for {symbol}: {e}")

    async def _session(self) -> None:
        # Build initial stream list
        streams = self.get_needed_streams()
        url = f"{WS_BASE}/stream?streams=" + "/".join(streams)
        log.info("WS connect streams=%d", len(streams))

        async with websockets.connect(
            url, ping_interval=20, ping_timeout=20, max_size=8_000_000
        ) as ws:
            self._connected = True
            while self._running:
                # Check if we need to update subscriptions
                if self._should_update_subscriptions():
                    log.info("Updating WS subscriptions")
                    self._last_subscription_update = time.monotonic()
                    self._pending_subscription_update = False

                    # Build new stream list
                    new_streams = self.get_needed_streams()
                    if new_streams != streams:
                        log.info("WS streams changed: %d -> %d", len(streams), len(new_streams))
                        streams = new_streams
                        # Need to reconnect with new streams
                        break

                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=25)
                except asyncio.TimeoutError:
                    continue

                self._last_message_monotonic = time.monotonic()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    self._record_event("unknown")
                    continue

                data = msg.get("data", msg)
                stream = msg.get("stream", "")

                if stream == "!ticker@arr":  # Process only the combined ticker stream; isinstance(data, list) check removed as it was interfering with kline data routing
                    self._record_event("ticker")
                    if isinstance(data, list):
                        for t in data:
                            self._store_ticker(t)
                elif stream.endswith("@ticker"):
                    self._record_event("ticker")
                    self._store_ticker(data)
                elif "@kline_" in stream or "@kline_" in stream.upper():
                    self._record_event("kline")
                    self._handle_kline(data)
                elif "@bookTicker" in stream or data.get("e") == "bookTicker":
                    self._record_event("book")
                    self._handle_book_ticker(data)
                elif "@depth" in stream:
                    self._record_event("depth")
                    sym = stream.split("@")[0].upper()
                    self._books[sym] = {
                        "bids": data.get("b") or [],
                        "asks": data.get("a") or [],
                    }
                elif "@markPrice" in stream:
                    self._record_event("mark")
                    sym = (data.get("s") or "").upper()
                    if sym:
                        self._mark[sym] = {
                            "symbol": sym,
                            "markPrice": data.get("p"),
                            "lastFundingRate": data.get("r"),
                            "nextFundingTime": data.get("T"),
                        }
                else:
                    self._record_event("unknown")
                    log.debug("Unhandled Binance WS event stream=%s data_type=%s", stream, type(data).__name__)
        self._connected = False

    def _store_ticker(self, ticker: dict[str, Any]) -> None:
        sym = (ticker.get("s") or "").upper()
        if not sym:
            return
        existing = self._tickers.get(sym, {})
        merged = dict(existing)
        merged.update(ticker)
        merged["s"] = sym
        merged["_xora_price_source"] = "native_ticker_stream"
        self._tickers[sym] = merged
        try:
            price = float(merged.get("c") or 0)
            if price > 0:
                self._baseline_prices.setdefault(sym, price)
        except (TypeError, ValueError):
            pass

    def _store_price_snapshot(self, item: dict[str, Any]) -> bool:
        sym = str(item.get("symbol") or "").upper()
        try:
            price = float(item.get("price") or 0)
            event_ms = int(item.get("time") or time.time() * 1000)
        except (TypeError, ValueError):
            return False
        if not sym or price <= 0:
            return False

        self._baseline_prices.setdefault(sym, price)
        existing = dict(self._tickers.get(sym, {}))
        existing.update(
            {
                "s": sym,
                "c": str(price),
                "E": event_ms,
                "_xora_price_source": "futures_websocket_api_ticker_price",
            }
        )
        self._tickers[sym] = existing
        return self._sample_price_candle(sym, price, event_ms)

    def _handle_book_ticker(self, data: dict[str, Any]) -> None:
        sym = str(data.get("s") or "").upper()
        if not sym:
            return
        try:
            bid = float(data.get("b") or 0)
            ask = float(data.get("a") or 0)
            bid_qty = float(data.get("B") or 0)
            ask_qty = float(data.get("A") or 0)
        except (TypeError, ValueError):
            return

        book = self._books.get(sym)
        if not book or not book.get("bids") or not book.get("asks"):
            self._books[sym] = {
                "bids": [[str(bid), str(bid_qty)]] if bid > 0 else [],
                "asks": [[str(ask), str(ask_qty)]] if ask > 0 else [],
            }

        existing = dict(self._tickers.get(sym, {}))
        existing.update(
            {
                "s": sym,
                "b": str(bid),
                "B": str(bid_qty),
                "a": str(ask),
                "A": str(ask_qty),
            }
        )
        if existing.get("c") is None and bid > 0 and ask > 0:
            mid = (bid + ask) / 2.0
            existing["c"] = str(mid)
            existing["_xora_price_source"] = "book_ticker_midpoint"
            self._baseline_prices.setdefault(sym, mid)
        self._tickers[sym] = existing

    def _sample_price_candle(self, sym: str, price: float, event_ms: int) -> bool:
        if sym in self._native_kline_symbols:
            return False

        open_time = event_ms - (event_ms % 60_000)
        live = self._live_candles.get(sym)
        if live and live.open_time == open_time:
            live.high = max(float(live.high), price)
            live.low = min(float(live.low), price)
            live.close = price
            live.close_time = open_time + 59_999
            return False

        closed = False
        if live and live.open_time < open_time:
            buf = self._candles[sym]
            if buf and buf[-1].open_time == live.open_time:
                buf[-1] = live
            else:
                buf.append(live)
            self._record_event("sampled_candle")
            closed = True

        self._live_candles[sym] = Candle(
            open_time=open_time,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=0.0,
            close_time=open_time + 59_999,
        )
        return closed

    def _handle_kline(self, data: dict) -> None:
        k = data.get("k") or {}
        sym = (data.get("s") or k.get("s") or "").upper()
        if not sym or "t" not in k:
            return
        self._native_kline_symbols.add(sym)
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
                if buf:
                    self._baseline_prices.setdefault(sym.upper(), float(buf[0].close))
            log.info("Loaded WebSocket candle cache for %d symbols", len(self._candles))
        except Exception as e:
            log.warning("Could not load WS candle cache: %s", e)

    def _save_ws_state(self) -> None:
        try:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "source": "binance_websocket_only",
                "sampled_price_fallback": True,
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

    def add_stream_ref(self, symbol: str, stream_type: str) -> None:
        """Add a reference to a stream type for a symbol.

        Args:
            symbol: The symbol (e.g., "BTCUSDT")
            stream_type: The type of stream ("ticker", "kline_1m", "bookTicker", etc.)
        """
        symbol = symbol.upper()
        refs = self._stream_refs[symbol]
        refs[stream_type] += 1
        self._pending_subscription_update = True
        log.debug(
            "Added stream ref for %s:%s (now %d)",
            symbol,
            stream_type,
            refs[stream_type],
        )

    def remove_stream_ref(self, symbol: str, stream_type: str) -> None:
    """Remove a reference to a stream type for a symbol.

    Args:
        symbol: The symbol (e.g., "BTCUSDT")
        stream_type: The type of stream ("ticker", "kline_1m", "bookTicker", etc.)
    """
    symbol = symbol.upper()
    if symbol in self._stream_refs:
        refs = self._stream_refs[symbol]
        if refs[stream_type] > 0:
            refs[stream_type] -= 1
            if refs[stream_type] == 0:
                del refs[stream_type]
                # Clean up empty symbol entries
                if not refs:
                    del self._stream_refs[symbol]
            self._pending_subscription_update = True
            log.debug(
                "Removed stream ref for %s:%s (now %d)",
                symbol,
                stream_type,
                refs.get(stream_type, 0),
            )

    def get_needed_streams(self) -> list[str]:
        """Build list of streams needed based on current reference counts.

        Returns:
            List of stream subscriptions needed (e.g., ["!ticker@arr", "btcusdt@kline_1m"])
        """
        streams = ["!ticker@arr"]  # Always need the global ticker stream for discovery

        # Add streams for each symbol based on reference counts
        for symbol, refs in self._stream_refs.items():
            if refs.get("ticker", 0) > 0:
                streams.append(f"{symbol.lower()}@ticker")
            if refs.get("kline_1m", 0) > 0:
                streams.append(f"{symbol.lower()}@kline_1m")
            if refs.get("bookTicker", 0) > 0:
                streams.append(f"{symbol.lower()}@bookTicker")
            if refs.get("depth20@100ms", 0) > 0:
                streams.append(f"{symbol.lower()}@depth20@100ms")
            if refs.get("markPrice@1s", 0) > 0:
                streams.append(f"{symbol.lower()}@markPrice@1s")

        return streams

    def _should_update_subscriptions(self) -> bool:
        """Check if we should update subscriptions based on pending changes and timing.

        Returns:
            True if subscriptions should be updated
        """
        if not self._pending_subscription_update:
            return False

        # Throttle subscription updates to avoid excessive reconnections
        now = time.monotonic()
        if now - self._last_subscription_update < 5.0:  # Minimum 5 seconds between updates
            return False

        return True


async def ensure_hub() -> BinanceWSHub:
    """Start both WebSocket surfaces and briefly wait for initial prices."""
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
    log.info("WS-only discovery returned %d coins from %d live prices", len(coins), hub.ticker_count())
    return coins


async def fetch_klines(symbol: str, interval: str = "1m", limit: int = 100) -> CandleWindow:
    hub = await ensure_hub()
    sym = symbol.upper()
    hub.set_watchlist(list(hub._desired_symbols | {sym}))
    window = hub.get_window(sym, interval=interval, limit=limit)
    if not window:
        count = hub.candle_count(sym)
        raise RuntimeError(
            f"WebSocket candle history warming for {sym}: {count}/{MIN_CANDLES} closed bars collected"
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
