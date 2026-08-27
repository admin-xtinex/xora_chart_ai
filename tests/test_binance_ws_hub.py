from pathlib import Path

import xora_chart.services.binance_ws as binance_ws
from xora_chart.services.binance_ws import BOOTSTRAP_SYMBOLS, BinanceWSHub


def test_bootstrap_watchlist_is_present():
    hub = BinanceWSHub()
    assert "BTCUSDT" in hub._desired_symbols
    assert len(BOOTSTRAP_SYMBOLS) >= 20


def test_individual_ticker_is_stored():
    hub = BinanceWSHub()
    hub._store_ticker({"s": "BTCUSDT", "P": "2.5", "q": "1000000"})
    assert hub.ticker_count() == 1
    coins = hub.discover_coins(min_quote_volume=500_000)
    assert coins
    assert coins[0].symbol == "BTCUSDT"


def test_only_closed_kline_enters_history(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(binance_ws, "STATE_PATH", tmp_path / "ws_market.json")
    hub = BinanceWSHub()

    open_event = {
        "s": "BTCUSDT",
        "k": {
            "t": 1000,
            "T": 1999,
            "s": "BTCUSDT",
            "o": "100",
            "h": "110",
            "l": "90",
            "c": "105",
            "v": "10",
            "x": False,
        },
    }
    hub._handle_kline(open_event)
    assert hub.candle_count("BTCUSDT") == 0
    assert "BTCUSDT" in hub._live_candles

    closed_event = {
        "s": "BTCUSDT",
        "k": {**open_event["k"], "c": "106", "x": True},
    }
    hub._handle_kline(closed_event)
    assert hub.candle_count("BTCUSDT") == 1
    assert "BTCUSDT" not in hub._live_candles
    assert (tmp_path / "ws_market.json").exists()
