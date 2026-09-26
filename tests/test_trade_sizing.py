from __future__ import annotations

from xora_chart.engines.trade.engine import _sizing


def test_fixed_margin_and_leverage_produce_expected_notional() -> None:
    quantity, margin = _sizing(entry=50_000.0, margin=10.0, leverage=10)

    assert quantity == 0.002
    assert margin == 10.0
    assert round(quantity * 50_000.0, 4) == 100.0


def test_fixed_sizing_rejects_invalid_values() -> None:
    assert _sizing(entry=0.0, margin=10.0, leverage=10) == (0.0, 0.0)
    assert _sizing(entry=100.0, margin=0.0, leverage=10) == (0.0, 0.0)
    assert _sizing(entry=100.0, margin=10.0, leverage=0) == (0.0, 0.0)
