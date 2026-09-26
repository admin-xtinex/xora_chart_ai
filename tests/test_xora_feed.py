from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from xora_chart.application import xora_feed
from xora_chart.auth import UserStore
from xora_chart.domain.enums import DecisionAction, Direction, Side

KEY = "k" * 32


@pytest.fixture(autouse=True)
def clean():
    xora_feed.reset()
    yield
    xora_feed.reset()


def window(symbol="AAAUSDT", first_open=100.0, last_close=101.0):
    candles = [NS(open=first_open, close=first_open)] + [NS(open=last_close, close=last_close)] * 59
    return NS(symbol=symbol, candles=candles)


def decision(action, side=None):
    setup = NS(side=side, entry=1.0, stop_loss=0.9, take_profit_1=1.2) if side else None
    return NS(action=action, setup=setup)


def test_groups_keep_the_scan_cohorts_and_order():
    coins = [
        NS(symbol="G1USDT", source="gainer", rank_in_source=1, price_change_pct=9.0, quote_volume=1e7),
        NS(symbol="L1USDT", source="loser", rank_in_source=1, price_change_pct=-8.0, quote_volume=2e7),
        NS(symbol="M1USDT", source="ws-price-trending", rank_in_source=1, price_change_pct=3.0, quote_volume=3e7),
        NS(symbol="V1USDT", source="high-volume", rank_in_source=1, price_change_pct=0.5, quote_volume=9e8),
    ]
    xora_feed.record_groups(coins)
    g = xora_feed.groups()["groups"]
    assert [c["symbol"] for c in g["gainers"]] == ["G1USDT"]
    assert [c["symbol"] for c in g["losers"]] == ["L1USDT"]
    assert [c["symbol"] for c in g["movers"]] == ["M1USDT"]
    assert [c["symbol"] for c in g["high_volume"]] == ["V1USDT"]


def test_signal_rule_priority_decision_pattern_analysis_fallback():
    best_bear = NS(direction=Direction.BEARISH, pattern_name="Head and Shoulders", similarity=71.0)
    bull = NS(bias=Direction.BULLISH)

    # 1. APPROVE/WAIT with a setup wins, even against the pattern and analysis
    xora_feed.record_scan(window("A"), matches=[best_bear], analysis=bull, decision=decision(DecisionAction.WAIT, Side.BUY))
    assert (xora_feed.signal_for("A")["side"], xora_feed.signal_for("A")["source"]) == ("BUY", "decision")

    # 2. REJECT (no usable setup) → the best pattern's direction
    xora_feed.record_scan(window("B"), matches=[best_bear], analysis=bull, decision=decision(DecisionAction.REJECT))
    assert (xora_feed.signal_for("B")["side"], xora_feed.signal_for("B")["source"]) == ("SELL", "pattern")

    # 3. analysis ran but no pattern direction → analysis bias
    xora_feed.record_scan(window("C"), matches=[NS(direction=Direction.NEUTRAL, pattern_name="x", similarity=60.0)], analysis=bull, decision=decision(DecisionAction.REJECT))
    assert (xora_feed.signal_for("C")["side"], xora_feed.signal_for("C")["source"]) == ("BUY", "analysis")

    # 4. no pattern match at all → last hour's change (falling here), then remembered
    xora_feed.record_scan(window("D", first_open=100.0, last_close=97.0))
    assert (xora_feed.signal_for("D")["side"], xora_feed.signal_for("D")["source"]) == ("SELL", "fallback")


def test_fallback_remembers_the_last_side_and_stale_scans_are_ignored(monkeypatch):
    xora_feed.record_scan(window("E"), matches=[NS(direction=Direction.BULLISH, pattern_name="p", similarity=66.0)])
    assert xora_feed.signal_for("E")["side"] == "BUY"
    later = datetime.now(timezone.utc) + timedelta(minutes=10)
    monkeypatch.setattr(xora_feed, "_now", lambda: later)
    s = xora_feed.signal_for("E")
    assert (s["side"], s["source"], s["in_latest_scan"]) == ("BUY", "fallback", False)
    # a coin never scanned and with no candles has no side yet
    assert xora_feed.signal_for("ZZZUSDT")["side"] is None
    assert xora_feed.signal_for("YYYUSDT", hour_change_pct=-0.4)["side"] == "SELL"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("XORA_USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setenv("XORA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("XORA_ADMIN_PASSWORD", "correct horse")
    monkeypatch.setattr(UserStore, "_instance", None)
    UserStore.instance()
    from xora_chart.main import app

    return TestClient(app)  # no lifespan: the Binance hub is not started


def rpc(ws, rid, action, payload=None):
    ws.send_json({"id": rid, "action": action, "payload": payload or {}})
    return ws.receive_json()


def test_service_key_login_reaches_only_the_xora_feed(client, monkeypatch):
    xora_feed.record_groups([NS(symbol="G1USDT", source="gainer", rank_in_source=1, price_change_pct=5.0, quote_volume=1e7)])
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        # feed needs a login; the key must be configured and match
        assert not rpc(ws, "1", "xora.groups")["ok"]
        monkeypatch.setenv("XORA_SERVICE_KEY", KEY)
        assert not rpc(ws, "2", "auth.service", {"key": "wrong" * 8})["ok"]
        assert rpc(ws, "3", "auth.service", {"key": KEY})["ok"]
        r = rpc(ws, "4", "xora.groups")
        assert r["ok"] and r["data"]["groups"]["gainers"][0]["symbol"] == "G1USDT"
        # the service login cannot use anything else
        r = rpc(ws, "5", "positions.summary")
        assert not r["ok"] and "XORA feed" in r["error"]
        assert not rpc(ws, "6", "settings.update", {"auto_trade": True})["ok"]


def test_service_key_is_off_when_unset_or_short(client, monkeypatch):
    monkeypatch.setenv("XORA_SERVICE_KEY", "short")
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert not rpc(ws, "1", "auth.service", {"key": "short"})["ok"]


def test_regular_users_cannot_read_the_feed_but_admins_can(client):
    UserStore.instance().create_user("viewer", "viewer-pass", "user")
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert rpc(ws, "1", "auth.login", {"username": "viewer", "password": "viewer-pass"})["ok"]
        assert not rpc(ws, "2", "xora.groups")["ok"]
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert rpc(ws, "1", "auth.login", {"username": "admin", "password": "correct horse"})["ok"]
        assert rpc(ws, "2", "xora.groups")["ok"]
