"""Read-only data feed for the XORA trading app.

XORA asks two things over the WebSocket (service key login):

* ``xora.groups``  - the coin groups of the LATEST scan cycle, exactly as the
  dashboard uses them (gainers, losers, movers, high volume).
* ``xora.signals`` - BUY or SELL per requested coin, for XORA only.

Nothing here changes a decision, an opportunity, a position or the scan. The
scan pipeline only *records* what it already computed for every coin
(:func:`record_scan`), and the signal rule below reads those records:

1. ``decision``  - an APPROVE, then WAIT, decision with a setup -> its side
2. ``pattern``   - otherwise the best reference-pattern match direction
3. ``analysis``  - otherwise the Analysis Engine bias
4. ``fallback``  - otherwise the coin's last side given here, or for a new coin
   the sign of its last-hour price change (from candles already in memory)

No extra matcher, analysis or market-data work is ever started for XORA.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from xora_chart.domain.enums import DecisionAction, Direction

_lock = threading.Lock()
_scans: dict[str, dict[str, Any]] = {}      # symbol -> what the latest scan saw
_last_side: dict[str, str] = {}              # symbol -> last side returned to XORA
_groups: dict[str, Any] = {"as_of": None, "groups": {}}

GROUP_KEYS = {"gainer": "gainers", "loser": "losers", "trending": "movers", "high-volume": "high_volume"}
SCAN_MAX_AGE_SECONDS = 5 * 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _side_of(direction: Any) -> str | None:
    value = getattr(direction, "value", direction)
    if value == Direction.BULLISH.value:
        return "BUY"
    if value == Direction.BEARISH.value:
        return "SELL"
    return None


def _hour_change_pct(window: Any) -> float | None:
    candles = list(getattr(window, "candles", None) or [])[-60:]
    if len(candles) < 2 or not candles[0].open:
        return None
    return (candles[-1].close - candles[0].open) / candles[0].open * 100.0


def record_groups(coins: list[Any]) -> None:
    """Called by discovery with the coins of the cycle about to be scanned."""
    groups: dict[str, list[dict[str, Any]]] = {name: [] for name in GROUP_KEYS.values()}
    for coin in coins:
        source = str(getattr(coin, "source", "") or "").removeprefix("ws-price-")
        name = GROUP_KEYS.get(source)
        if not name:
            continue
        groups[name].append({
            "symbol": coin.symbol,
            "rank": getattr(coin, "rank_in_source", None),
            "change_24h_pct": getattr(coin, "price_change_pct", None),
            "quote_volume": getattr(coin, "quote_volume", None),
        })
    with _lock:
        _groups["as_of"] = _now().isoformat()
        _groups["groups"] = groups


def record_scan(window: Any, *, matches: list[Any] | None = None, analysis: Any = None, decision: Any = None) -> None:
    """Called by the scan loop for every coin it looked at - recording only."""
    best = (matches or [None])[0]
    setup = getattr(decision, "setup", None)
    action = getattr(getattr(decision, "action", None), "value", None)
    entry = {
        "at": _now(),
        "decision": action,
        "decision_side": getattr(getattr(setup, "side", None), "value", getattr(setup, "side", None)) if setup else None,
        "levels": (
            {"entry": setup.entry, "stop_loss": setup.stop_loss, "take_profit": getattr(setup, "take_profit_1", None)}
            if setup is not None and hasattr(setup, "entry") else None
        ),
        "pattern_side": _side_of(getattr(best, "direction", None)) if best else None,
        "pattern": getattr(best, "pattern_name", None) or getattr(best, "name", None) if best else None,
        "similarity": getattr(best, "similarity", None) if best else None,
        "analysis_side": _side_of(getattr(analysis, "bias", None)) if analysis is not None else None,
        "hour_change_pct": _hour_change_pct(window),
    }
    with _lock:
        _scans[str(getattr(window, "symbol", "")).upper()] = entry


def groups() -> dict[str, Any]:
    with _lock:
        return {"as_of": _groups["as_of"], "groups": {k: list(v) for k, v in _groups["groups"].items()}}


def signal_for(symbol: str, *, hour_change_pct: float | None = None) -> dict[str, Any]:
    """BUY/SELL for one coin by the four-step rule, with where it came from."""
    sym = symbol.upper()
    with _lock:
        scan = _scans.get(sym)
        fresh = bool(scan) and (_now() - scan["at"]).total_seconds() <= SCAN_MAX_AGE_SECONDS
        side, source = None, None
        if fresh:
            if scan["decision"] in (DecisionAction.APPROVE.value, DecisionAction.WAIT.value) and scan["decision_side"] in ("BUY", "SELL"):
                side, source = scan["decision_side"], "decision"
            elif scan["pattern_side"]:
                side, source = scan["pattern_side"], "pattern"
            elif scan["analysis_side"]:
                side, source = scan["analysis_side"], "analysis"
        if side is None:
            change = hour_change_pct if hour_change_pct is not None else (scan or {}).get("hour_change_pct")
            if sym in _last_side:
                side, source = _last_side[sym], "fallback"
            elif change is not None:
                side, source = ("BUY" if change >= 0 else "SELL"), "fallback"
        if side:
            _last_side[sym] = side
        return {
            "symbol": sym,
            "side": side,
            "source": source,
            "decision": scan["decision"] if fresh else None,
            "levels": scan["levels"] if fresh else None,
            "pattern": scan["pattern"] if fresh else None,
            "similarity": scan["similarity"] if fresh else None,
            "scanned_at": scan["at"].isoformat() if scan else None,
            "in_latest_scan": fresh,
        }


def reset() -> None:
    """Test helper."""
    with _lock:
        _scans.clear()
        _last_side.clear()
        _groups.update(as_of=None, groups={})
