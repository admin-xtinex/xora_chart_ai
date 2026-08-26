"""Binance Futures market data — WebSocket only (see binance_ws)."""

from __future__ import annotations

from xora_chart.services import binance_ws

# Re-export WS-backed helpers so existing imports keep working.
discover_coins = binance_ws.discover_coins
fetch_klines = binance_ws.fetch_klines
fetch_order_book = binance_ws.fetch_order_book
fetch_premium_index = binance_ws.fetch_premium_index
fetch_open_interest = binance_ws.fetch_open_interest
