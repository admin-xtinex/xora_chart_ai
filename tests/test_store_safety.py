from __future__ import annotations

import json

import pytest

from xora_chart.persistence.store import Store


def test_store_never_restores_stale_live_mode(tmp_path, monkeypatch):
    state = tmp_path / "xora_state.json"
    state.write_text(json.dumps({"settings": {"auto_trade": True, "trade_mode": "live"}}), encoding="utf-8")
    monkeypatch.setenv("XORA_STATE_FILE", str(state))

    store = Store()

    assert store.get_settings()["auto_trade"] is True
    assert store.get_settings()["trade_mode"] == "demo"


def test_store_rejects_live_mode_without_adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("XORA_STATE_FILE", str(tmp_path / "state.json"))
    store = Store()

    with pytest.raises(RuntimeError, match="Live trading is unavailable"):
        store.update_settings({"trade_mode": "live"})

    assert store.get_settings()["trade_mode"] == "demo"
