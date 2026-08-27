"""Analysis Engine — REST history plus WebSocket live market evidence."""

from __future__ import annotations

import logging

from xora_chart.config import load_config
from xora_chart.domain.enums import Direction, MarketRegime, SignalStatus
from xora_chart.domain.models import AnalysisSignal, CandleWindow, MarketAnalysis, PatternMatch
from xora_chart.services import binance

log = logging.getLogger(__name__)


def _status(score: float, pass_at: float = 65, fail_at: float = 35) -> SignalStatus:
    if score >= pass_at:
        return SignalStatus.PASS
    if score <= fail_at:
        return SignalStatus.FAIL
    return SignalStatus.WEAK


def _volume_signal(window: CandleWindow) -> AnalysisSignal:
    vols = [float(c.volume) for c in window.candles]
    if len(vols) < 20:
        return AnalysisSignal(name="volume", score=50, status=SignalStatus.WEAK, note="Insufficient history bars")
    recent = vols[-20:]
    if not any(v > 0 for v in recent):
        return AnalysisSignal(
            name="volume",
            score=50,
            status=SignalStatus.WEAK,
            note="Volume unavailable on WebSocket recovery candles",
        )
    avg = sum(recent[:-1]) / 19
    last = recent[-1]
    ratio = (last / avg) if avg > 0 else 1.0
    score = max(0.0, min(100.0, (ratio - 0.5) / 2.0 * 100))
    note = f"REST kline volume {ratio:.2f}× 20-bar avg"
    return AnalysisSignal(name="volume", score=round(score, 1), status=_status(score), note=note)


def _volatility_signal(window: CandleWindow) -> tuple[AnalysisSignal, MarketRegime]:
    candles = window.candles
    if len(candles) < 20:
        return (
            AnalysisSignal(name="volatility", score=50, status=SignalStatus.WEAK, note="Insufficient history bars"),
            MarketRegime.RANGING,
        )
    ranges = [(c.high - c.low) / c.close for c in candles[-20:] if c.close]
    atr_pct = sum(ranges) / len(ranges) * 100 if ranges else 0
    if atr_pct < 0.08:
        regime = MarketRegime.LOW_VOL
        score = 35
        note = f"Historical ATR% {atr_pct:.3f} — low volatility"
    elif atr_pct > 1.2:
        regime = MarketRegime.HIGH_VOL
        score = 40
        note = f"Historical ATR% {atr_pct:.3f} — high volatility"
    else:
        regime = MarketRegime.TRENDING if atr_pct > 0.25 else MarketRegime.RANGING
        score = 70 if 0.12 <= atr_pct <= 0.9 else 55
        note = f"Historical ATR% {atr_pct:.3f} — tradeable"
    return AnalysisSignal(name="volatility", score=float(score), status=_status(score, 55, 30), note=note), regime


def _trend_bias(window: CandleWindow) -> Direction:
    closes = [c.close for c in window.candles]
    if len(closes) < 20:
        return Direction.NEUTRAL
    sma_fast = sum(closes[-10:]) / 10
    sma_slow = sum(closes[-20:]) / 20
    if sma_fast > sma_slow * 1.001:
        return Direction.BULLISH
    if sma_fast < sma_slow * 0.999:
        return Direction.BEARISH
    return Direction.NEUTRAL


async def _book_signal(symbol: str) -> AnalysisSignal:
    depth = await binance.fetch_order_book(symbol, limit=20)
    bids = sum(float(x[1]) for x in depth.get("bids", []))
    asks = sum(float(x[1]) for x in depth.get("asks", []))
    total = bids + asks
    if total <= 0:
        return AnalysisSignal(name="order_book", score=50, status=SignalStatus.WEAK, note="WS book not ready")
    imb = (bids - asks) / total
    score = max(0.0, min(100.0, 50 + imb * 50))
    note = f"WS bid/ask imbalance {imb:+.2%}"
    return AnalysisSignal(name="order_book", score=round(score, 1), status=_status(score), note=note)


async def _funding_signal(symbol: str) -> AnalysisSignal:
    data = await binance.fetch_premium_index(symbol)
    if not data or data.get("lastFundingRate") is None:
        return AnalysisSignal(name="funding", score=50, status=SignalStatus.WEAK, note="WS mark/funding not ready")
    rate = float(data.get("lastFundingRate") or 0) * 100
    abs_r = abs(rate)
    if abs_r < 0.01:
        score = 70
        note = f"WS funding {rate:.4f}% — neutral"
    elif abs_r < 0.05:
        score = 55
        note = f"WS funding {rate:.4f}% — mild skew"
    else:
        score = 30
        note = f"WS funding {rate:.4f}% — crowded side risk"
    return AnalysisSignal(name="funding", score=float(score), status=_status(score, 50, 35), note=note)


def _oi_signal_unavailable() -> AnalysisSignal:
    return AnalysisSignal(
        name="open_interest",
        score=50,
        status=SignalStatus.WEAK,
        note="Excluded: no approved live WebSocket source",
    )


async def run_analysis(window: CandleWindow, match: PatternMatch | None = None) -> MarketAnalysis:
    cfg = load_config().get("analysis", {})
    weights = cfg.get("weights", {})

    vol_sig = _volume_signal(window)
    atr_sig, regime = _volatility_signal(window)
    book_sig = await _book_signal(window.symbol)
    fund_sig = await _funding_signal(window.symbol)
    oi_sig = _oi_signal_unavailable()

    volume_available = any(float(c.volume) > 0 for c in window.candles[-20:])
    book_available = "not ready" not in book_sig.note.lower()
    funding_available = "not ready" not in fund_sig.note.lower()

    # Missing live signals are excluded instead of being silently scored as
    # neutral.  Available evidence is renormalized back onto a 0–100 scale.
    raw_weights = {
        "volume": float(weights.get("volume", 0.30)) if volume_available else 0.0,
        "order_book": float(weights.get("order_book", 0.25)) if book_available else 0.0,
        "funding": float(weights.get("funding", 0.15)) if funding_available else 0.0,
        "volatility": float(weights.get("volatility", 0.20)),
    }
    total_weight = sum(raw_weights.values()) or 1.0
    normalized = {k: v / total_weight for k, v in raw_weights.items()}

    signals = [vol_sig, book_sig, fund_sig, oi_sig, atr_sig]
    score = (
        normalized["volume"] * vol_sig.score
        + normalized["order_book"] * book_sig.score
        + normalized["funding"] * fund_sig.score
        + normalized["volatility"] * atr_sig.score
    )

    bias = _trend_bias(window)
    details = {
        "volume_ratio_note": vol_sig.note,
        "regime": regime.value,
        "pattern_key": match.pattern_key if match else None,
        "market_data_source": "binance_rest_history_websocket_live",
        "volume_weight": round(normalized["volume"], 4),
        "order_book_weight": round(normalized["order_book"], 4),
        "funding_weight": round(normalized["funding"], 4),
        "volatility_weight": round(normalized["volatility"], 4),
        "open_interest_weight": 0.0,
    }

    return MarketAnalysis(
        symbol=window.symbol,
        score=round(score, 1),
        bias=bias,
        regime=regime,
        signals=signals,
        details=details,
    )
