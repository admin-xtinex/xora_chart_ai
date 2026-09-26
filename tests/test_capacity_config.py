from __future__ import annotations

from xora_chart.application.discovery import configured_scan_limit
from xora_chart.config import load_config
from xora_chart.engines.trade.engine import configured_max_open_positions


def test_scan_capacity_and_position_cap_defaults(monkeypatch) -> None:
    monkeypatch.delenv("XORA_MAX_OPEN_POSITIONS", raising=False)
    cfg = load_config()
    discovery = cfg["discovery"]

    assert discovery["top_gainers"] == 10
    assert discovery["top_losers"] == 10
    assert discovery["trending"] == 10
    assert discovery["top_volume"] == 10
    assert configured_scan_limit() == 40
    assert configured_max_open_positions() == 20


def test_server_position_cap_can_be_lowered_by_environment(monkeypatch) -> None:
    monkeypatch.setenv("XORA_MAX_OPEN_POSITIONS", "12")
    assert configured_max_open_positions() == 12
