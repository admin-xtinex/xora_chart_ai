"""Build human-readable analysis text from match + trade + candles."""

from __future__ import annotations

from xora_chart.domain.enums import Direction, Side
from xora_chart.domain.models import CandleWindow, PatternMatch, TradeLevels


_FEATURE_LABELS = {
    "impulse_compress": "Impulse then consolidation",
    "trend": "Trend alignment",
    "volume": "Volume confirmation",
    "converge": "Range compression (pennant)",
    "equal_peaks": "Equal peaks (double top)",
    "equal_troughs": "Equal troughs (double bottom)",
    "breakdown": "Breakdown vs neckline/support",
    "breakout": "Breakout vs resistance",
    "prior_up": "Prior uptrend into pattern",
    "prior_down": "Prior downtrend into pattern",
    "head": "Head higher than shoulders",
    "shoulders": "Shoulders near equal height",
    "broke": "Level break confirmed",
    "retest": "Retest of broken level",
    "u_shape": "Cup U-shape recovery",
    "handle": "Handle pullback",
}


_PATTERN_BLURBS = {
    "bull_flag": "A sharp upward impulse followed by a tight downward-drifting consolidation. Continuation higher is favored after the flag.",
    "bear_flag": "A sharp downward impulse followed by a tight upward-drifting consolidation. Continuation lower is favored after the flag.",
    "bull_pennant": "Strong rally then a converging, lower-volatility coil. Break of the upper boundary supports continuation higher.",
    "bear_pennant": "Strong selloff then a converging coil. Break of the lower boundary supports continuation lower.",
    "double_top": "Two peaks at similar highs with a neckline between them. A close below the neckline signals a bearish reversal.",
    "double_bottom": "Two troughs at similar lows with a neckline between them. A close above the neckline signals a bullish reversal.",
    "head_and_shoulders": "Left shoulder, higher head, right shoulder. Breakdown through the neckline targets a measured move lower.",
    "breakout_retest": "Price broke above resistance, then retested it as support. Holding the retest favors long continuation.",
    "breakdown_retest": "Price broke below support, then retested it as resistance. Rejecting the retest favors short continuation.",
    "cup_and_handle": "Rounded base recovery toward the prior high, then a shallow handle. Break above the handle favors upside continuation.",
}


def _window_context(window: CandleWindow) -> str:
    if not window.candles:
        return "No candle data."
    first = window.candles[0].close
    last = window.candles[-1].close
    hi = max(c.high for c in window.candles)
    lo = min(c.low for c in window.candles)
    chg = ((last - first) / first * 100) if first else 0
    return (
        f"Analyzed last {len(window.candles)} × {window.interval} candles on {window.symbol}. "
        f"Window range {lo:.6g} – {hi:.6g}, net move {chg:+.2f}% to last price {last:.6g}."
    )


def _feature_lines(match: PatternMatch) -> list[str]:
    lines = []
    for key, val in (match.score_breakdown or {}).items():
        label = _FEATURE_LABELS.get(key, key.replace("_", " ").title())
        if isinstance(val, (int, float)):
            strength = "strong" if val >= 0.75 else "moderate" if val >= 0.4 else "weak"
            lines.append(f"{label}: {val:.2f} ({strength})")
        else:
            lines.append(f"{label}: {val}")
    return lines


def _levels_text(trade: TradeLevels) -> str:
    side = "long (BUY)" if trade.side == Side.BUY else "short (SELL)"
    parts = [
        f"Side: {side}",
        f"Entry: {trade.entry}",
        f"Stop loss: {trade.stop_loss}",
        f"TP1: {trade.take_profit_1}",
    ]
    if trade.take_profit_2 is not None:
        parts.append(f"TP2: {trade.take_profit_2}")
    if trade.take_profit_3 is not None:
        parts.append(f"TP3: {trade.take_profit_3}")
    parts.append(f"Risk/reward (to TP1): 1 : {trade.risk_reward}")
    parts.append(
        "Levels are derived from recent ATR-style range: "
        "risk distance ≈ average true range of the last ~14 bars; "
        "targets are multiples of that risk (1.5R / 2.5R / 3.5R)."
    )
    return "\n".join(parts)


def build_analysis(
    window: CandleWindow,
    match: PatternMatch,
    trade: TradeLevels,
    validation_note: str | None = None,
) -> dict:
    """Return structured analysis for API + UI."""
    blurb = _PATTERN_BLURBS.get(
        match.pattern_key,
        f"Matched pattern {match.pattern_name} with similarity {match.similarity:.1f}%.",
    )
    direction = "bullish" if match.direction == Direction.BULLISH else "bearish"

    summary = (
        f"{window.symbol} scored {match.similarity:.1f}% similarity to {match.pattern_name} "
        f"({direction}). {blurb}"
    )

    features = _feature_lines(match)
    context = _window_context(window)
    levels = _levels_text(trade)

    why_trade = (
        f"Trade idea is {trade.side.value} because the best structure match is {direction}. "
        f"Confidence {trade.confidence:.0f}% blends pattern similarity with secondary checks."
    )

    sections = {
        "summary": summary,
        "market_context": context,
        "pattern": match.pattern_name,
        "pattern_key": match.pattern_key,
        "direction": direction,
        "similarity": match.similarity,
        "structure_features": features,
        "why_this_trade": why_trade,
        "levels_explanation": levels,
        "validation": validation_note or "",
    }

    # Single narrative block for simple consumers
    narrative_parts = [
        summary,
        "",
        "Market context",
        context,
        "",
        "Structure features",
        *[f"• {f}" for f in features] if features else ["• No feature breakdown"],
        "",
        "Why this trade",
        why_trade,
        "",
        "Entry / exit levels",
        levels,
    ]
    if validation_note:
        narrative_parts.extend(["", "Validation", validation_note])

    sections["narrative"] = "\n".join(narrative_parts)
    return sections
