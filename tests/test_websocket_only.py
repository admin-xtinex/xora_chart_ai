from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_binance_market_service_has_no_rest_client_or_endpoint():
    source = text("src/xora_chart/services/binance_ws.py")
    forbidden = [
        "import httpx",
        "https://fapi.binance.com",
        "/fapi/v1/",
        "AsyncClient(",
        "_http_get",
        "_seed_klines_http",
        "_seed_tickers_http",
    ]
    for marker in forbidden:
        assert marker not in source, f"REST market-data path returned: {marker}"
    assert "wss://ws-fapi.binance.com/ws-fapi/v1" in source


def test_frontend_uses_websocket_not_fetch_for_backend_data():
    source = text("frontend/src/api.js")
    assert "new WebSocket(" in source
    assert "fetch(" not in source
    assert "/api/v1" not in source


def test_production_has_no_rest_worker():
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
