import json

from xora_chart.api import ops


def test_healthz_is_liveness_even_when_market_not_ready(monkeypatch):
    monkeypatch.setattr(
        ops,
        "health_snapshot",
        lambda: {"service": "xora-chart-ai", "version": "0.7.0", "ready": False},
    )
    result = ops.healthz()
    assert result == {
        "status": "ok",
        "service": "xora-chart-ai",
        "version": "0.7.0",
        "ready": False,
    }


def test_readyz_returns_503_until_runtime_is_ready(monkeypatch):
    snapshot = {
        "status": "degraded",
        "ready": False,
        "service": "xora-chart-ai",
        "market_live": False,
        "reference_ready": True,
    }
    monkeypatch.setattr(ops, "health_snapshot", lambda: snapshot)
    response = ops.readyz()
    assert response.status_code == 503
    assert json.loads(response.body) == snapshot


def test_readyz_returns_200_for_ready_runtime(monkeypatch):
    snapshot = {
        "status": "ok",
        "ready": True,
        "service": "xora-chart-ai",
        "market_live": True,
        "reference_ready": True,
    }
    monkeypatch.setattr(ops, "health_snapshot", lambda: snapshot)
    response = ops.readyz()
    assert response.status_code == 200
    assert json.loads(response.body) == snapshot
