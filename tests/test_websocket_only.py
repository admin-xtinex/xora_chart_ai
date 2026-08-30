from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_live_binance_service_remains_websocket_only():
    source = text("src/xora_chart/services/binance_ws.py")
    assert "import httpx" not in source
    assert "https://fapi.binance.com/fapi/v1" not in source
    assert "wss://ws-fapi.binance.com/ws-fapi/v1" in source
    assert "wss://fstream.binance.com" in source


def test_historical_service_uses_binance_futures_rest_klines():
    source = text("src/xora_chart/services/binance_rest.py")
    assert "import httpx" in source
    assert "https://fapi.binance.com" in source
    assert "/fapi/v1/klines" in source
    assert "window_from_rows" in source


def test_frontend_keeps_application_rpc_on_websocket_and_rest_only_for_history():
    source = text("frontend/src/api.js")
    assert "new WebSocket(" in source
    assert "rpc('analyze'" in source
    assert "rpc('cycle.run'" in source
    assert "fapi.binance.com/fapi/v1" in source
    assert "/klines?" in source
    assert "fetch(" in source
    assert "/api/v1" not in source


def test_production_has_no_rest_application_worker():
    compose = text("docker-compose.prod.yml")
    assert "worker:" not in compose
    assert "XORA_API_BASE" not in compose
    assert "api/v1/health" not in compose


def test_backend_mounts_only_websocket_application_router():
    source = text("src/xora_chart/main.py")
    assert "ws_router" in source
    assert "v1_router" not in source
    assert "docs_url=None" in source
    assert "openapi_url=None" in source


def test_external_rest_ai_validation_is_disabled():
    source = text("src/xora_chart/application/validator.py")
    assert "httpx" not in source
    assert "chat/completions" not in source
