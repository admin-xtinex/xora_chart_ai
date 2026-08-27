from __future__ import annotations

import time

import pytest

from xora_chart.services.binance_rest import BinanceHistoryError, window_from_rows


def _rows(count: int, *, include_open: bool = False):
    now = int(time.time() * 1000)
    base = now - (count + 2) * 60_000
    rows = []
    for i in range(count):
        open_time = base + i * 60_000
        close_time = open_time + 59_999
        price = 100 + i
        rows.append(
            [
                open_time,
                str(price),
                str(price + 2),
                str(price - 2),
                str(price + 1),
                str(10 + i),
                close_time,
                "0",
                1,
                "0",
                "0",
                "0",
            ]
        )
    if include_open:
        open_time = now - (now % 60_000)
        rows.append([open_time, "999", "999", "999", "999", "999", open_time + 59_999])
    return rows


def test_rest_rows_create_closed_candle_window_with_real_volume():
    window = window_from_rows("btcusdt", "1m", _rows(25, include_open=True), limit=100)
    assert window.symbol == "BTCUSDT"
    assert len(window.candles) == 25
    assert window.candles[-1].volume > 0
    assert window.candles[-1].close != 999


def test_rest_rows_require_minimum_history():
    with pytest.raises(BinanceHistoryError):
        window_from_rows("ETHUSDT", "1m", _rows(10), limit=100)
