"""Operational runtime status shared by WebSocket RPC and health endpoints.

This module intentionally exposes observability only. Trading and analysis commands
remain behind the application WebSocket RPC surface.
"""

from __future__ import annotations

from typing import Any

from xora_chart.application.live import enrich_position
from xora_chart.application.reference_visual import library_status
from xora_chart.domain.enums import PositionStatus
from xora_chart.persistence.store import Store
from xora_chart.services.binance_ws import BinanceWSHub, MIN_CANDLES


def health_snapshot() -> dict[str, Any]:
    store = Store.instance()
    latest = store.latest_cycle()
    settings = store.get_settings()
    hub = BinanceWSHub.instance()
    ref = library_status()

    connected = hub.websocket_connected()
    tickers = hub.ticker_count()
    refs_ready = int(ref.get("count", 0)) >= 10
    events = hub.event_telemetry()
    ticker_age = events["ticker"]["age_seconds"]
    market_live = (
        connected
        and tickers > 0
        and ticker_age is not None
        and float(ticker_age) < 30.0
    )
    ready = bool(market_live and refs_ready)

    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "service": "xora-chart-ai",
        "version": "0.7.0",
        "transport": "websocket-rpc",
        "market_data": "binance-rest-history-websocket-live",
        "rest_market_data": True,
        "history_data": "binance-futures-rest",
        "live_market_data": "binance-futures-websocket",
        "market_live": market_live,
        "ws_connected": connected,
        "ws_tickers": tickers,
        "ws_ready_symbols": hub.ready_symbol_count(),
        "ws_min_candles": MIN_CANDLES,
        "ws_last_message_age_seconds": hub.last_message_age_seconds(),
        "ws_events": events,
        "auto_trade": settings.get("auto_trade", False),
        "trade_mode": settings.get("trade_mode", "demo"),
        "live_trading_available": False,
        "latest_cycle_id": latest.cycle_id if latest else None,
        "latest_cycle_errors": latest.errors[:5] if latest else [],
        "latest_opportunities": len(latest.opportunities) if latest else 0,
        "opportunities_cached": len(store.list_opportunities()),
        "positions_open": len([p for p in store.list_positions() if p.status == PositionStatus.OPEN]),
        "reference_gate": True,
        "reference_images": int(ref.get("count", 0)),
        "reference_ready": refs_ready,
    }


def positions_summary() -> dict[str, Any]:
    all_pos = [enrich_position(p) for p in Store.instance().list_positions()]
    closed = [p for p in all_pos if p.get("status") == "closed"]
    open_p = [p for p in all_pos if p.get("status") == "open"]
    realized = [p.get("realized_pnl") for p in closed if p.get("realized_pnl") is not None]
    live = [p.get("live_pnl") for p in open_p if p.get("live_pnl") is not None]
    wins = [p for p in realized if p > 0]
    losses = [p for p in realized if p < 0]
    total_pnl = sum(realized) if realized else 0.0
    return {
        "open_count": len(open_p),
        "closed_count": len(closed),
        "total_trades": len(all_pos),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(realized) * 100, 1) if realized else 0.0,
        "total_realized_pnl": round(total_pnl, 4),
        "open_unrealized_pnl": round(sum(live), 4) if live else 0.0,
        "avg_pnl": round(total_pnl / len(realized), 4) if realized else 0.0,
        "best_trade": max(realized) if realized else None,
        "worst_trade": min(realized) if realized else None,
    }
