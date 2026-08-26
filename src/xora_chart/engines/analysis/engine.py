"""Analysis Engine — market context scores. Does not decide trades."""

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
    vols = [c.volume for c in window.candles]
    if len(vols) < 20:
        return AnalysisSignal(name="volume", score=40, status=SignalStatus.WEAK, note="Insufficient bars")
    avg = sum(vols[-20:-1]) / 19 if len(vols) > 19 else sum(vols[:-1]) / max(1, len(vols) - 1)
    last = vols[-1]
    ratio = (last / avg) if avg > 0 else 1.0
    # relative volume 0.5x–2.5x mapped to 0–100
    score = max(0.0, min(100.0, (ratio - 0.5) / 2.0 * 100))
    note = f"Last vol {ratio:.2f}× 20-bar avg"
    return AnalysisSignal(name="volume", score=round(score, 1), status=_status(score), note=note)


def _volatility_signal(window: CandleWindow) -> tuple[AnalysisSignal, MarketRegime]:
    candles = window.candles
    if len(candles) < 20:
        return (
            AnalysisSignal(name="volatility", score=50, status=SignalStatus.WEAK, note="Insufficient bars"),
            MarketRegime.RANGING,
        )
    ranges = [(c.high - c.low) / c.close for c in candles[-20:] if c.close]
    atr_pct = sum(ranges) / len(ranges) * 100 if ranges else 0
    # sweet spot ~0.15%–0.8% on 1m; outside is harder
    if atr_pct < 0.08:
        regime = MarketRegime.LOW_VOL
        score = 35
        note = f"ATR% {atr_pct:.3f} — low volatility"
    elif atr_pct > 1.2:
        regime = MarketRegime.HIGH_VOL
        score = 40
        note = f"ATR% {atr_pct:.3f} — high volatility"
    else:
        regime = MarketRegime.TRENDING if atr_pct > 0.25 else MarketRegime.RANGING
        score = 70 if 0.12 <= atr_pct <= 0.9 else 55
        note = f"ATR% {atr_pct:.3f} — tradeable"
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
    try:
        depth = await binance.fetch_order_book(symbol, limit=20)
        bids = sum(float(x[1]) for x in depth.get("bids", []))
        asks = sum(float(x[1]) for x in depth.get("asks", []))
        total = bids + asks
        if total <= 0:
            return AnalysisSignal(name="order_book", score=50, status=SignalStatus.WEAK, note="Empty book")
        imb = (bids - asks) / total  # -1..+1
        score = max(0.0, min(100.0, 50 + imb * 50))
        note = f"Bid/ask imbalance {imb:+.2%} (bids={bids:.2f} asks={asks:.2f})"
        return AnalysisSignal(name="order_book", score=round(score, 1), status=_status(score), note=note)
    except Exception as e:
        log.debug("order book failed %s: %s", symbol, e)
        return AnalysisSignal(name="order_book", score=50, status=SignalStatus.WEAK, note="Book unavailable")


async def _funding_signal(symbol: str) -> AnalysisSignal:
    try:
        data = await binance.fetch_premium_index(symbol)
        rate = float(data.get("lastFundingRate") or 0) * 100  # percent
        # extreme funding = crowded; mild is fine
        abs_r = abs(rate)
        if abs_r < 0.01:
            score = 70
            note = f"Funding {rate:.4f}% — neutral"
        elif abs_r < 0.05:
            score = 55
            note = f"Funding {rate:.4f}% — mild skew"
        else:
            score = 30
            note = f"Funding {rate:.4f}% — crowded side risk"
        return AnalysisSignal(name="funding", score=float(score), status=_status(score, 50, 35), note=note)
    except Exception as e:
        log.debug("funding failed %s: %s", symbol, e)
        return AnalysisSignal(name="funding", score=50, status=SignalStatus.WEAK, note="Funding unavailable")


async def _oi_signal(symbol: str) -> AnalysisSignal:
    try:
        data = await binance.fetch_open_interest(symbol)
        oi = float(data.get("openInterest") or 0)
        # absolute OI alone is weak without history; treat presence as mild pass
        score = 60 if oi > 0 else 40
        note = f"Open interest {oi:.4g}"
        return AnalysisSignal(name="open_interest", score=float(score), status=_status(score, 55, 35), note=note)
    except Exception as e:
        log.debug("OI failed %s: %s", symbol, e)
        return AnalysisSignal(name="open_interest", score=50, status=SignalStatus.WEAK, note="OI unavailable")


async def run_analysis(window: CandleWindow, match: PatternMatch | None = None) -> MarketAnalysis:
    cfg = load_config().get("analysis", {})
    weights = cfg.get("weights", {})
    w_vol = float(weights.get("volume", 0.30))
    w_book = float(weights.get("order_book", 0.25))
    w_fund = float(weights.get("funding", 0.15))
    w_oi = float(weights.get("open_interest", 0.10))
    w_atr = float(weights.get("volatility", 0.20))

    vol_sig = _volume_signal(window)
    atr_sig, regime = _volatility_signal(window)
    book_sig = await _book_signal(window.symbol)
    fund_sig = await _funding_signal(window.symbol)
    oi_sig = await _oi_signal(window.symbol)

    signals = [vol_sig, book_sig, fund_sig, oi_sig, atr_sig]
    score = (
        w_vol * vol_sig.score
        + w_book * book_sig.score
        + w_fund * fund_sig.score
        + w_oi * oi_sig.score
        + w_atr * atr_sig.score
    )

    bias = _trend_bias(window)

    # Align book imbalance direction into details for Decision Engine
    details = {
        "volume_ratio_note": vol_sig.note,
        "regime": regime.value,
        "pattern_key": match.pattern_key if match else None,
    }

    return MarketAnalysis(
        symbol=window.symbol,
        score=round(score, 1),
        bias=bias,
        regime=regime,
        signals=signals,
        details=details,
    )
