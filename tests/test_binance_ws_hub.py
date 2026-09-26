from pathlib import Path

import xora_chart.services.binance_ws as binance_ws
from xora_chart.services.binance_ws import BOOTSTRAP_SYMBOLS, BinanceWSHub


def test_bootstrap_watchlist_is_present():
    hub = BinanceWSHub()
    assert "BTCUSDT" in hub._desired_symbols
    assert len(BOOTSTRAP_SYMBOLS) >= 20


def test_individual_ticker_is_stored():
    hub = BinanceWSHub()
    hub._store_ticker({"s": "BTCUSDT", "c": "100", "P": "2.5", "q": "1000000"})
    assert hub.ticker_count() == 1
    coins = hub.discover_coins(min_quote_volume=500_000)
    assert coins
    assert coins[0].symbol == "BTCUSDT"


def test_discovery_returns_four_unique_ten_coin_cohorts():
    hub = BinanceWSHub()
    for i in range(80):
        hub._store_ticker(
            {
                "s": f"T{i:03d}USDT",
                "c": str(100 + i),
                "P": str(i - 40),
                "q": str(1_000_000 + i * 10_000),
            }
        )

    coins = hub.discover_coins(
        top_gainers=10,
        top_losers=10,
        trending=10,
        top_volume=10,
        min_quote_volume=500_000,
    )

    assert len(coins) == 40
    assert len({coin.symbol for coin in coins}) == 40
    assert {source: sum(coin.source == source for coin in coins) for source in {
        "gainer", "loser", "trending", "high-volume"
    }} == {"gainer": 10, "loser": 10, "trending": 10, "high-volume": 10}


def test_ws_api_price_snapshot_is_stored(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(binance_ws, "STATE_PATH", tmp_path / "ws_market.json")
    hub = BinanceWSHub()
    hub._store_price_snapshot({"symbol": "BTCUSDT", "price": "80000", "time": 60_000})
    assert hub.ticker_count() == 1
    assert float(hub._tickers["BTCUSDT"]["c"]) == 80000.0


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
