"""Build human-readable analysis text from match + trade + candles."""

from __future__ import annotations

from xora_chart.application.overlays import build_overlays
from xora_chart.domain.enums import Direction, Side
from xora_chart.domain.models import Candle, CandleWindow, PatternMatch, TradeLevels


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


def _local_extrema(vals: list[float], order: int = 3) -> tuple[list[int], list[int]]:
    peaks, troughs = [], []
    for i in range(order, len(vals) - order):
        window = vals[i - order : i + order + 1]
        if vals[i] == max(window) and vals[i] > vals[i - 1] and vals[i] > vals[i + 1]:
            peaks.append(i)
        if vals[i] == min(window) and vals[i] < vals[i - 1] and vals[i] < vals[i + 1]:
            troughs.append(i)
    return peaks, troughs


def _pct_from(level: float, price: float) -> float:
    if not level:
        return 0.0
    return (price - level) / level * 100


def _phase_head_shoulders(candles: list[Candle], last: float) -> tuple[str, str]:
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    peaks, _ = _local_extrema(highs, order=3)
    if len(peaks) < 3:
        return "forming", "Structure is incomplete — fewer than 3 clear peaks detected yet."

    l, h, r = peaks[-3], peaks[-2], peaks[-1]
    left_t = min(lows[l : h + 1]) if h > l else highs[l]
    right_t = min(lows[h : r + 1]) if r > h else highs[r]
    neck = (left_t + right_t) / 2
    head_px = highs[h]
    rs_px = highs[r]

    dist_neck = _pct_from(neck, last)
    if last < neck * 0.998:
        phase = "broken neckline — continuation down"
        detail = (
            f"Price is below the neckline (~{neck:.6g}), about {abs(dist_neck):.2f}% under it. "
            f"Classic H&S target zone is a measured move from the head ({head_px:.6g}) through the neckline."
        )
    elif abs(dist_neck) <= 0.35:
        phase = "at / testing neckline"
        detail = (
            f"Price is pressing the neckline near {neck:.6g} ({dist_neck:+.2f}%). "
            f"A decisive close below neckline confirms the bearish breakdown; a bounce back toward "
            f"the right shoulder (~{rs_px:.6g}) would invalidate the immediate short trigger."
        )
    elif last < rs_px and last > neck:
        phase = "right shoulder / post-head decline"
        detail = (
            f"Price sits between the right-shoulder high (~{rs_px:.6g}) and the neckline (~{neck:.6g}). "
            f"Pattern is mature; watch for neckline break to activate the measured move."
        )
    elif last >= head_px * 0.995:
        phase = "at the head"
        detail = f"Price is near the head peak (~{head_px:.6g}). Pattern is not complete until a right shoulder and neckline test form."
    else:
        phase = "between head and right shoulder"
        detail = (
            f"Head peak ~{head_px:.6g}, neckline ~{neck:.6g}. "
            f"Current price {last:.6g} is still above the neckline ({dist_neck:+.2f}%)."
        )
    return phase, detail


def _phase_double_top(candles: list[Candle], last: float) -> tuple[str, str]:
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    peaks, _ = _local_extrema(highs, order=4)
    if len(peaks) < 2:
        return "forming", "Need two clear peaks to complete a double top."
    p1, p2 = peaks[-2], peaks[-1]
    neck = min(lows[p1 : p2 + 1]) if p2 > p1 else lows[p2]
    top = (highs[p1] + highs[p2]) / 2
    dist = _pct_from(neck, last)
    if last < neck * 0.998:
        return (
            "broken neckline — bearish continuation",
            f"Price is below the neckline (~{neck:.6g}, {abs(dist):.2f}% under). "
            f"Double-top measured move uses the height from tops (~{top:.6g}) to neckline.",
        )
    if abs(dist) <= 0.35:
        return (
            "at / testing neckline",
            f"Price is on the neckline (~{neck:.6g}). Breakdown confirms the short; reclaim of the tops (~{top:.6g}) invalidates.",
        )
    if last >= top * 0.99:
        return "at second peak", f"Price is retesting the double-top zone near {top:.6g}. Rejection here sets up the neckline test."
    return (
        "between second peak and neckline",
        f"Tops ~{top:.6g}, neckline ~{neck:.6g}. Price {last:.6g} is {dist:+.2f}% vs neckline.",
    )


def _phase_double_bottom(candles: list[Candle], last: float) -> tuple[str, str]:
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    _, troughs = _local_extrema(lows, order=4)
    if len(troughs) < 2:
        return "forming", "Need two clear troughs to complete a double bottom."
    t1, t2 = troughs[-2], troughs[-1]
    neck = max(highs[t1 : t2 + 1]) if t2 > t1 else highs[t2]
    bottom = (lows[t1] + lows[t2]) / 2
    dist = _pct_from(neck, last)
    if last > neck * 1.002:
        return (
            "broken neckline — bullish continuation",
            f"Price is above the neckline (~{neck:.6g}, {dist:+.2f}%). "
            f"Measured move uses height from bottoms (~{bottom:.6g}) to neckline.",
        )
    if abs(dist) <= 0.35:
        return (
            "at / testing neckline",
            f"Price is on the neckline (~{neck:.6g}). Breakout confirms the long; loss of bottoms (~{bottom:.6g}) invalidates.",
        )
    if last <= bottom * 1.01:
        return "at second trough", f"Price is near the double-bottom zone (~{bottom:.6g}). Hold here leads to a neckline test."
    return (
        "between second trough and neckline",
        f"Bottoms ~{bottom:.6g}, neckline ~{neck:.6g}. Price {last:.6g} is {dist:+.2f}% vs neckline.",
    )


def _phase_flag(candles: list[Candle], last: float, bullish: bool) -> tuple[str, str]:
    closes = [c.close for c in candles]
    mid = len(closes) // 2
    first = closes[:mid]
    impulse_end = first[-1] if first else last
    flag_hi = max(c.high for c in candles[mid:]) if mid else last
    flag_lo = min(c.low for c in candles[mid:]) if mid else last

    if bullish:
        if last > flag_hi * 1.001:
            return (
                "breaking out of the flag",
                f"Price has pushed above the flag high (~{flag_hi:.6g}). Continuation of the prior impulse is in play.",
            )
        if last < flag_lo * 0.999:
            return (
                "breaking down — flag failed",
                f"Price slipped under the flag low (~{flag_lo:.6g}). Bull-flag thesis is invalidated for now.",
            )
        pos = (last - flag_lo) / (flag_hi - flag_lo) if flag_hi != flag_lo else 0.5
        return (
            "inside the flag consolidation",
            f"After the impulse toward {impulse_end:.6g}, price is coiling between {flag_lo:.6g} and {flag_hi:.6g} "
            f"(~{pos*100:.0f}% of the flag range). A break above {flag_hi:.6g} triggers the long continuation.",
        )
    if last < flag_lo * 0.999:
        return (
            "breaking down out of the flag",
            f"Price has pushed below the flag low (~{flag_lo:.6g}). Continuation of the prior selloff is in play.",
        )
    if last > flag_hi * 1.001:
        return (
            "breaking up — flag failed",
            f"Price rose above the flag high (~{flag_hi:.6g}). Bear-flag thesis is invalidated for now.",
        )
    pos = (last - flag_lo) / (flag_hi - flag_lo) if flag_hi != flag_lo else 0.5
    return (
        "inside the flag consolidation",
        f"After the impulse toward {impulse_end:.6g}, price is coiling between {flag_lo:.6g} and {flag_hi:.6g} "
        f"(~{pos*100:.0f}% of the flag range). A break below {flag_lo:.6g} triggers the short continuation.",
    )


def _phase_pennant(candles: list[Candle], last: float, bullish: bool) -> tuple[str, str]:
    phase, detail = _phase_flag(candles, last, bullish)
    detail = detail.replace("flag", "pennant")
    if "inside" in phase:
        phase = "inside the pennant coil"
    return phase, detail


def _phase_breakout_retest(candles: list[Candle], last: float) -> tuple[str, str]:
    highs = [c.high for c in candles]
    closes = [c.close for c in candles]
    cut = int(len(closes) * 0.6)
    resistance = max(highs[:cut]) if cut else max(highs)
    dist = _pct_from(resistance, last)
    if last > resistance * 1.005:
        return (
            "post-breakout expansion",
            f"Price is above prior resistance (~{resistance:.6g}, {dist:+.2f}%). Looking for continuation or a later retest.",
        )
    if abs(dist) <= 0.4:
        return (
            "retesting broken resistance as support",
            f"Price is back on the broken level (~{resistance:.6g}). Holding this zone keeps the long thesis alive.",
        )
    if last < resistance:
        return (
            "failed breakout / back below level",
            f"Price is back under resistance (~{resistance:.6g}, {dist:+.2f}%). Breakout thesis is weakened.",
        )
    return "above level", f"Resistance was ~{resistance:.6g}; price {last:.6g} ({dist:+.2f}%)."


def _phase_breakdown_retest(candles: list[Candle], last: float) -> tuple[str, str]:
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    cut = int(len(closes) * 0.6)
    support = min(lows[:cut]) if cut else min(lows)
    dist = _pct_from(support, last)
    if last < support * 0.995:
        return (
            "post-breakdown expansion",
            f"Price is below prior support (~{support:.6g}, {dist:+.2f}%). Looking for continuation or a later retest.",
        )
    if abs(dist) <= 0.4:
        return (
            "retesting broken support as resistance",
            f"Price is back on the broken level (~{support:.6g}). Rejection here keeps the short thesis alive.",
        )
    if last > support:
        return (
            "failed breakdown / back above level",
            f"Price is back above support (~{support:.6g}, {dist:+.2f}%). Breakdown thesis is weakened.",
        )
    return "below level", f"Support was ~{support:.6g}; price {last:.6g} ({dist:+.2f}%)."


def _phase_cup_handle(candles: list[Candle], last: float) -> tuple[str, str]:
    closes = [c.close for c in candles]
    n = len(closes)
    if n < 30:
        return "forming", "Not enough bars to locate cup and handle stages."
    left_hi = max(closes[: n // 4])
    mid_lo = min(closes[n // 4 : 3 * n // 4])
    handle = closes[int(n * 0.85) :]
    handle_hi = max(handle) if handle else last
    handle_lo = min(handle) if handle else last
    if last > left_hi * 1.002:
        return (
            "breaking out of the cup/handle",
            f"Price cleared the rim / prior high zone (~{left_hi:.6g}). Upside continuation is active.",
        )
    if handle and last <= handle_hi and last >= handle_lo:
        return (
            "in the handle",
            f"Cup low was ~{mid_lo:.6g}, rim ~{left_hi:.6g}. Price is in the handle band "
            f"{handle_lo:.6g} – {handle_hi:.6g}. Break above {handle_hi:.6g} is the trigger.",
        )
    if last < mid_lo * 1.02:
        return "near cup low", f"Price is near the cup base (~{mid_lo:.6g}). Recovery toward the rim is still required."
    return (
        "climbing the right side of the cup",
        f"Base ~{mid_lo:.6g}, rim ~{left_hi:.6g}. Price {last:.6g} is recovering toward the handle zone.",
    )


def detect_pattern_phase(window: CandleWindow, pattern_key: str) -> dict:
    if not window.candles:
        return {"phase": "unknown", "detail": "No candles", "label": "Unknown"}

    last = window.candles[-1].close
    key = pattern_key

    if key == "head_and_shoulders":
        phase, detail = _phase_head_shoulders(window.candles, last)
    elif key == "double_top":
        phase, detail = _phase_double_top(window.candles, last)
    elif key == "double_bottom":
        phase, detail = _phase_double_bottom(window.candles, last)
    elif key == "bull_flag":
        phase, detail = _phase_flag(window.candles, last, bullish=True)
    elif key == "bear_flag":
        phase, detail = _phase_flag(window.candles, last, bullish=False)
    elif key == "bull_pennant":
        phase, detail = _phase_pennant(window.candles, last, bullish=True)
    elif key == "bear_pennant":
        phase, detail = _phase_pennant(window.candles, last, bullish=False)
    elif key == "breakout_retest":
        phase, detail = _phase_breakout_retest(window.candles, last)
    elif key == "breakdown_retest":
        phase, detail = _phase_breakdown_retest(window.candles, last)
    elif key == "cup_and_handle":
        phase, detail = _phase_cup_handle(window.candles, last)
    else:
        phase, detail = "matched", f"Last price {last:.6g} on {window.symbol}."

    return {
        "phase": phase,
        "label": phase.replace("—", "-").title() if phase else "Unknown",
        "detail": detail,
        "last_price": last,
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
        "Levels use recent ATR-style range (~14 bars). "
        "Targets are 1.5R / 2.5R / 3.5R from entry."
    )
    return "\n".join(parts)


def build_analysis(
    window: CandleWindow,
    match: PatternMatch,
    trade: TradeLevels,
    validation_note: str | None = None,
) -> dict:
    blurb = _PATTERN_BLURBS.get(
        match.pattern_key,
        f"Matched pattern {match.pattern_name} with similarity {match.similarity:.1f}%.",
    )
    direction = "bullish" if match.direction == Direction.BULLISH else "bearish"
    position = detect_pattern_phase(window, match.pattern_key)
    overlays = build_overlays(window, match.pattern_key)

    summary = (
        f"{window.symbol} scored {match.similarity:.1f}% similarity to {match.pattern_name} "
        f"({direction}). {blurb}"
    )

    current_area = (
        f"Current area in pattern: {position['phase']}.\n{position['detail']}"
    )

    features = _feature_lines(match)
    context = _window_context(window)
    levels = _levels_text(trade)

    why_trade = (
        f"Trade idea is {trade.side.value} because the best structure match is {direction}. "
        f"Price is currently in the “{position['phase']}” stage of the pattern. "
        f"Confidence {trade.confidence:.0f}% blends similarity with secondary checks."
    )

    sections = {
        "summary": summary,
        "market_context": context,
        "pattern": match.pattern_name,
        "pattern_key": match.pattern_key,
        "direction": direction,
        "similarity": match.similarity,
        "current_area": current_area,
        "pattern_phase": position["phase"],
        "pattern_phase_label": position["label"],
        "pattern_phase_detail": position["detail"],
        "structure_features": features,
        "why_this_trade": why_trade,
        "levels_explanation": levels,
        "validation": validation_note or "",
        "chart_overlays": overlays,
    }

    narrative_parts = [
        summary,
        "",
        "Where price is now in the pattern",
        current_area,
        "",
        "Market context",
        context,
        "",
        "Structure features",
        *([f"• {f}" for f in features] if features else ["• No feature breakdown"]),
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
