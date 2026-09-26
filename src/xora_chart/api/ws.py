"""WebSocket application transport for the XORA dashboard.

Application RPC remains WebSocket-only.  Market-data transport is hybrid:
historical Binance Futures klines may arrive from REST (backend or browser);
live prices/order-book state come from Binance WebSockets.
"""

from __future__ import annotations

import asyncio
import hmac
import os
from datetime import date, datetime
from enum import Enum
from typing import Any
import logging

log = logging.getLogger(__name__)

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from xora_chart.auth import AuthError, UserStore

from xora_chart.application import discovery
from xora_chart.application.llm_explainer import explain_opportunity, status as llm_status
from xora_chart.application.live import enrich_position, last_price
from xora_chart.application.pipeline import run_cycle
from xora_chart.application.reference_visual import library_status
from xora_chart.application.symbol_scan import analyze_symbol
from xora_chart.catalog import list_patterns
from xora_chart.config import load_config
from xora_chart.domain.enums import OpportunityStatus, PositionStatus
from xora_chart.engines.trade import close_position, list_positions, manage_open_positions
from xora_chart.engines.trade.engine import configured_max_open_positions, open_from_opportunity
from xora_chart.persistence.store import Store
from xora_chart.services.binance_ws import BinanceWSHub, MIN_CANDLES

router = APIRouter()


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(v) for v in value]
    if isinstance(value, dict):
        return {k: _dump(v) for k, v in value.items()}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _health() -> dict[str, Any]:
    store = Store.instance()
    latest = store.latest_cycle()
    settings = store.get_settings()
    trade_cfg = load_config().get("trade", {})
    max_leverage = int(trade_cfg.get("max_leverage", 10))
    trade_leverage = min(int(trade_cfg.get("default_leverage", 10)), max_leverage)
    hub = BinanceWSHub.instance()
    ref = library_status()
    connected = hub.websocket_connected()
    tickers = hub.ticker_count()
    refs_ready = int(ref.get("count", 0)) >= 10
    last_age = hub.last_message_age_seconds()
    events = hub.event_telemetry()
    ticker_age = events["ticker"]["age_seconds"]
    market_live = (
        connected
        and tickers > 0
        and ticker_age is not None
        and float(ticker_age) < 30
    )

    return {
        "status": "ok" if market_live and refs_ready else "degraded",
        "service": "xora-chart-ai",
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
        "ws_last_message_age_seconds": last_age,
        "ws_events": events,
        "auto_trade": settings.get("auto_trade", False),
        "trade_mode": settings.get("trade_mode", "demo"),
        "trade_margin": float(trade_cfg.get("margin_per_trade", 10)),
        "trade_leverage": trade_leverage,
        "max_open_positions": configured_max_open_positions(),
        "latest_cycle_id": latest.cycle_id if latest else None,
        "latest_cycle_errors": latest.errors[:5] if latest else [],
        "latest_opportunities": len(latest.opportunities) if latest else 0,
        "opportunities_cached": len(store.list_opportunities()),
        "positions_open": len([p for p in store.list_positions() if p.status == PositionStatus.OPEN]),
        "reference_gate": True,
        "reference_images": int(ref.get("count", 0)),
        "reference_ready": refs_ready,
        "llm": llm_status(),
    }


def _positions_summary() -> dict[str, Any]:
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


async def _dispatch(action: str, payload: dict[str, Any], *, client_key: str = "unknown") -> Any:
    store = Store.instance()

    if action == "health":
        return _health()
    if action == "patterns.list":
        return list_patterns(direction=payload.get("direction"), pattern_type=payload.get("type"))
    if action == "opportunities.list":
        return store.list_opportunities(limit=min(int(payload.get("limit", 30)), 100))
    if action == "opportunity.explain":
        opp = store.get_opportunity(str(payload.get("opportunity_id") or ""))
        if not opp:
            raise RuntimeError("Opportunity not found")
        return await explain_opportunity(opp, client_key=client_key)
    if action == "settings.get":
        return store.get_settings()
    if action == "settings.update":
        patch = {k: v for k, v in payload.items() if k in {"auto_trade", "trade_mode"}}
        return store.update_settings(patch)
    if action == "cycle.plan":
        scan_limit = discovery.configured_scan_limit()
        coins = (await discovery.run_discovery())[:scan_limit]
        return {"coins": coins, "count": len(coins), "scan_limit": scan_limit}
    if action == "cycle.run":
        return await run_cycle(
            histories=payload.get("histories") or None,
            coins_override=payload.get("coins") or None,
        )
    if action == "analyze":
        symbol = str(payload.get("symbol") or "").upper()
        hub = BinanceWSHub.instance()
        # Add stream references for analysis
        hub.add_stream_ref(symbol, "kline_1m")
        hub.add_stream_ref(symbol, "ticker")
        hub.add_stream_ref(symbol, "markPrice@1s")
        try:
            return await analyze_symbol(
                str(payload.get("symbol") or ""),
                history_rows=payload.get("history") or None,
            )
        finally:
            # Remove stream references
            hub.remove_stream_ref(symbol, "kline_1m")
            hub.remove_stream_ref(symbol, "ticker")
            hub.remove_stream_ref(symbol, "markPrice@1s")
    if action == "quote":
        symbol = str(payload.get("symbol") or "").upper()
        hub = BinanceWSHub.instance()
        # Add stream references for live price data
        hub.add_stream_ref(symbol, "ticker")
        hub.add_stream_ref(symbol, "markPrice@1s")
        try:
            px = last_price(symbol)
            if px is None:
                raise RuntimeError(f"No WebSocket price for {symbol}")
            return {"symbol": symbol, "price": px}
        finally:
            # Remove stream references
            hub.remove_stream_ref(symbol, "ticker")
            hub.remove_stream_ref(symbol, "markPrice@1s")
    if action == "positions.list":
        # Add stream references for all open position symbols
        store = Store.instance()
        hub = BinanceWSHub.instance()
        try:
            all_positions = store.list_positions()
            open_positions = [p for p in all_positions if p.status.value == "open"]
            for pos in open_positions:
                hub.add_stream_ref(pos.symbol, "ticker")
                hub.add_stream_ref(pos.symbol, "markPrice@1s")
                # Note: May also need kline data depending on position management implementation
        except Exception as e:
            log.warning("Failed to add position stream references: %s", e)

        try:
            manage_open_positions()
            return [enrich_position(p) for p in list_positions(status=payload.get("status"), store=store)]
        finally:
            # Remove stream references for open position symbols
            try:
                all_positions = store.list_positions()
                hub = BinanceWSHub.instance()
                open_positions = [p for p in all_positions if p.status.value == "open"]
                for pos in open_positions:
                    hub.remove_stream_ref(pos.symbol, "ticker")
                    hub.remove_stream_ref(pos.symbol, "markPrice@1s")
            except Exception as e:
                log.warning("Failed to remove position stream references: %s", e)
    if action == "positions.summary":
        # Add stream references for all position symbols
        store = Store.instance()
        hub = BinanceWSHub.instance()
        try:
            all_positions = store.list_positions()
            for pos in all_positions:
                hub.add_stream_ref(pos.symbol, "ticker")
                hub.add_stream_ref(pos.symbol, "markPrice@1s")
        except Exception as e:
            log.warning("Failed to add position stream references for summary: %s", e)

        try:
            return _positions_summary()
        finally:
            # Remove stream references for all position symbols
            try:
                all_positions = store.list_positions()
                hub = BinanceWSHub.instance()
                for pos in all_positions:
                    hub.remove_stream_ref(pos.symbol, "ticker")
                    hub.remove_stream_ref(pos.symbol, "markPrice@1s")
            except Exception as e:
                log.warning("Failed to remove position stream references for summary: %s", e)
    if action == "positions.manage":
        # Add stream references for all open position symbols
        store = Store.instance()
        hub = BinanceWSHub.instance()
        try:
            all_positions = store.list_positions()
            open_positions = [p for p in all_positions if p.status.value == "open"]
            for pos in open_positions:
                hub.add_stream_ref(pos.symbol, "ticker")
                hub.add_stream_ref(pos.symbol, "markPrice@1s")
                # Note: May also need kline data depending on position management implementation
        except Exception as e:
            log.warning("Failed to add position stream references for management: %s", e)

        try:
            manage_open_positions()
            return [enrich_position(p) for p in list_positions(status="open", store=store)]
        finally:
            # Remove stream references for open position symbols
            try:
                all_positions = store.list_positions()
                hub = BinanceWSHub.instance()
                open_positions = [p for p in all_positions if p.status.value == "open"]
                for pos in open_positions:
                    hub.remove_stream_ref(pos.symbol, "ticker")
                    hub.remove_stream_ref(pos.symbol, "markPrice@1s")
            except Exception as e:
                log.warning("Failed to remove position stream references for management: %s", e)
    if action == "position.open":
        opp = store.get_opportunity(str(payload.get("opportunity_id") or ""))
        if not opp:
            raise RuntimeError("Opportunity not found")
        # Add stream references for the opportunity symbol
        hub = BinanceWSHub.instance()
        hub.add_stream_ref(opp.symbol, "ticker")
        hub.add_stream_ref(opp.symbol, "markPrice@1s")
        hub.add_stream_ref(opp.symbol, "kline_1m")
        try:
            pos = open_from_opportunity(opp, store=store)
            opp.status = OpportunityStatus.TRADED
            store.update_opportunity(opp)
            return pos
        finally:
            # Remove stream references for the opportunity symbol
            hub.remove_stream_ref(opp.symbol, "ticker")
            hub.remove_stream_ref(opp.symbol, "markPrice@1s")
            hub.remove_stream_ref(opp.symbol, "kline_1m")
    if action == "position.close":
        position_id = str(payload.get("position_id") or "")
        store = Store.instance()
        # Get the position to know its symbol for stream references
        position = store.get_position(position_id)
        if position:
            hub = BinanceWSHub.instance()
            # Add stream references for the position symbol
            hub.add_stream_ref(position.symbol, "ticker")
            hub.add_stream_ref(position.symbol, "markPrice@1s")
            # Note: May also need kline data depending on close position implementation
            try:
                return close_position(
                    position_id,
                    exit_price=payload.get("exit_price"),
                    reason=str(payload.get("reason") or "manual"),
                    store=store,
                )
            finally:
                # Remove stream references for the position symbol
                hub.remove_stream_ref(position.symbol, "ticker")
                hub.remove_stream_ref(position.symbol, "markPrice@1s")
        else:
            # Position not found, but still call close_position to handle the error appropriately
            return close_position(
                position_id,
                exit_price=payload.get("exit_price"),
                reason=str(payload.get("reason") or "manual"),
                store=store,
            )
    if action == "cycles.latest":
        return store.latest_cycle()
    if action == "xora_trades.list":
        limit = min(int(payload.get("limit", 50)), 100)
        return store.list_trades(limit)
    if action == "xora_trades.get":
        trade_id = str(payload.get("trade_id") or "")
        return store.get_trade(trade_id)
    if action == "trade_events.list":
        limit = min(int(payload.get("limit", 50)), 100)
        return store.list_events(limit)
    if action == "trade_events.get":
        event_id = str(payload.get("event_id") or "")
        return store.get_event(event_id)
    if action == "watchlist.get":
        store = Store.instance()
        hub = BinanceWSHub.instance()
        return {
            "symbols": list(hub._desired_symbols),
            "version": hub._watchlist_version
        }
    if action == "watchlist.update":
        symbols = payload.get("symbols", [])
        store = Store.instance()
        hub = BinanceWSHub.instance()
        hub.set_watchlist([s.upper() for s in symbols if s])
        return {"success": True}
    if action == "performance.metrics":
        store = Store.instance()
        trades = store.list_trades()
        closed_trades = [t for t in trades if t.status.value == "closed"]

        total_trades = len(closed_trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "realized_pnl": 0.0,
                "average_pnl": 0.0,
                "profit_factor": 0.0,
                "average_rr": 0.0,
                "average_trade_duration": 0
            }

        wins = [t for t in closed_trades if t.realized_pnl and t.realized_pnl > 0]
        losses = [t for t in closed_trades if t.realized_pnl and t.realized_pnl < 0]
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0.0

        realized_pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]
        total_realized_pnl = sum(realized_pnls) if realized_pnls else 0.0
        average_pnl = total_realized_pnl / len(realized_pnls) if realized_pnls else 0.0

        # Profit factor: gross profit / gross loss
        gross_profit = sum([p for p in realized_pnls if p > 0]) if realized_pnls else 0
        gross_loss = abs(sum([p for p in realized_pnls if p < 0])) if realized_pnls else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0 if gross_profit == 0 else float('inf')

        # Average R:R
        risk_ratios = [t.risk_reward for t in closed_trades if t.risk_reward is not None and t.risk_reward > 0]
        average_rr = sum(risk_ratios) / len(risk_ratios) if risk_ratios else 0.0

        # Average trade duration
        durations = [t.duration_seconds for t in closed_trades if t.duration_seconds is not None and t.duration_seconds >= 0]
        average_trade_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 2),
            "realized_pnl": round(total_realized_pnl, 4),
            "average_pnl": round(average_pnl, 4),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else 0.0,
            "average_rr": round(average_rr, 2),
            "average_trade_duration": round(average_trade_duration)
        }

    raise RuntimeError(f"Unknown WebSocket action: {action}")


# ── XORA app feed (read-only). The XORA server signs in with a shared service
# key (XORA_SERVICE_KEY) and may call ONLY these actions; admins may call them
# too, to inspect what XORA receives. Nothing here changes scans or trades.
XORA_ACTIONS = {"xora.groups", "xora.signals"}
SERVICE_ROLE = "service"
MAX_XORA_SYMBOLS = 50


def _service_key_ok(given: str) -> bool:
    expected = os.getenv("XORA_SERVICE_KEY", "")
    return len(expected) >= 24 and hmac.compare_digest(given.encode(), expected.encode())


def _xora_dispatch(action: str, payload: dict[str, Any]) -> Any:
    from xora_chart.application import xora_feed
    from xora_chart.services.binance_ws import BinanceWSHub

    if action == "xora.groups":
        return xora_feed.groups()
    symbols = [str(s).upper() for s in (payload.get("symbols") or []) if str(s).strip()][:MAX_XORA_SYMBOLS]
    hub = BinanceWSHub.instance()
    out = []
    for sym in symbols:
        # Only candles the hub already holds in memory - never a new fetch or subscription.
        window = hub.get_window(sym, interval="1m", limit=60)
        change = None
        if window and window.candles and window.candles[0].open:
            change = (window.candles[-1].close - window.candles[0].open) / window.candles[0].open * 100.0
        out.append(xora_feed.signal_for(sym, hour_change_pct=change))
    return {"signals": out}


# Actions only admins may call; every other action needs any signed-in user.
ADMIN_ACTIONS = {"settings.update", "watchlist.update", "users.list", "users.create", "users.delete", "users.reset_password"}


async def _auth_dispatch(action: str, payload: dict[str, Any], session: dict[str, Any]) -> Any:
    """Handle auth.* / users.* actions. Returns None when the action isn't one of them."""
    users = UserStore.instance()
    user = session.get("user")
    if action == "auth.service":
        if not _service_key_ok(str(payload.get("key") or "")):
            raise AuthError("Invalid service key")
        info = {"username": "xora-service", "role": SERVICE_ROLE}
        session.update(user=info, token=None)
        return {"user": info}
    if action == "auth.login":
        token, info = await asyncio.to_thread(users.login, str(payload.get("username") or ""), str(payload.get("password") or ""))
        session.update(user=info, token=token)
        return {"token": token, "user": info}
    if action == "auth.resume":
        info = users.resume(str(payload.get("token") or ""))
        session.update(user=info, token=str(payload.get("token")))
        return {"user": info}
    if action == "auth.logout":
        if session.get("token"):
            users.logout(session["token"])
        session.clear()
        return {"ok": True}
    if not action.startswith(("auth.", "users.")):
        return None
    if not user:
        raise AuthError("Please sign in")
    if action == "auth.me":
        return {"user": user}
    if action == "auth.change_password":
        await asyncio.to_thread(
            users.change_password, user["username"], str(payload.get("current_password") or ""),
            str(payload.get("new_password") or ""), token=session["token"],
        )
        return {"ok": True}
    if action == "users.list":
        return users.list_users()
    if action == "users.create":
        return await asyncio.to_thread(
            users.create_user, str(payload.get("username") or ""), str(payload.get("password") or ""),
            str(payload.get("role") or "user"),
        )
    if action == "users.delete":
        users.delete_user(str(payload.get("username") or ""), acting=user["username"])
        return {"ok": True}
    if action == "users.reset_password":
        await asyncio.to_thread(users.set_password, str(payload.get("username") or ""), str(payload.get("new_password") or ""))
        return {"ok": True}
    raise RuntimeError(f"Unknown WebSocket action: {action}")


@router.websocket("/ws")
async def dashboard_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    client_key = websocket.client.host if websocket.client else "unknown"
    session: dict[str, Any] = {}
    try:
        # Unauthenticated clients only learn that the service is up.
        await websocket.send_json({"type": "ready", "data": {"status": "ok", "service": "xora-chart-ai", "auth_required": True}})
        while True:
            message = await websocket.receive_json()
            request_id = message.get("id")
            action = str(message.get("action") or "")
            payload = message.get("payload") or {}
            try:
                if action in ADMIN_ACTIONS and (session.get("user") or {}).get("role") != "admin":
                    raise AuthError("Admin access required" if session.get("user") else "Please sign in")
                role = (session.get("user") or {}).get("role")
                if role == SERVICE_ROLE and action not in XORA_ACTIONS and not action.startswith("auth."):
                    raise AuthError("Service access is limited to the XORA feed")
                if action in XORA_ACTIONS:
                    if role not in (SERVICE_ROLE, "admin"):
                        raise AuthError("XORA feed requires the service key" if not session.get("user") else "Admin access required")
                    await websocket.send_json({"type": "response", "id": request_id, "ok": True, "data": _dump(_xora_dispatch(action, payload))})
                    continue
                data = await _auth_dispatch(action, payload, session)
                if data is None:
                    if not session.get("user"):
                        raise AuthError("Please sign in")
                    data = await _dispatch(action, payload, client_key=client_key)
                await websocket.send_json(
                    {"type": "response", "id": request_id, "ok": True, "data": _dump(data)}
                )
            except Exception as exc:
                await websocket.send_json(
                    {
                        "type": "response", "id": request_id, "ok": False, "error": str(exc),
                        "auth_error": isinstance(exc, AuthError) and not session.get("user"),
                    }
                )
    except WebSocketDisconnect:
        return
