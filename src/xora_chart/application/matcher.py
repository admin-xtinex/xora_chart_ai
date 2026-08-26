"""
Pattern Matcher — geometric similarity engine.

Extracts structure features from the candle window and scores each catalog
pattern with dedicated detectors (flags, double top/bottom, H&S, breakout
retest, cup & handle). Returns ranked PatternMatch list.
"""

from __future__ import annotations

from xora_chart.catalog import load_patterns
from xora_chart.config import load_config
from xora_chart.domain.enums import Direction
from xora_chart.domain.models import Candle, CandleWindow, PatternMatch


# ── Feature helpers ──────────────────────────────────────────────────────────

def _closes(c: list[Candle]) -> list[float]:
    return [x.close for x in c]


def _highs(c: list[Candle]) -> list[float]:
    return [x.high for x in c]


def _lows(c: list[Candle]) -> list[float]:
    return [x.low for x in c]


def _vols(c: list[Candle]) -> list[float]:
    return [x.volume for x in c]


def _sma(vals: list[float], n: int) -> float:
    if len(vals) < n or n <= 0:
        return vals[-1] if vals else 0.0
    return sum(vals[-n:]) / n


def _trend(closes: list[float]) -> float:
    """-1 … +1 overall trend."""
    if len(closes) < 10:
        return 0.0
    a, b = _sma(closes[: max(10, len(closes) // 3)], 10), _sma(closes, 10)
    if a == 0:
        return 0.0
    return max(-1.0, min(1.0, (b - a) / a * 8))


def _local_extrema(vals: list[float], order: int = 3) -> tuple[list[int], list[int]]:
    """Return indices of local peaks and troughs."""
    peaks, troughs = [], []
    for i in range(order, len(vals) - order):
        window = vals[i - order : i + order + 1]
        if vals[i] == max(window) and vals[i] > vals[i - 1] and vals[i] > vals[i + 1]:
            peaks.append(i)
        if vals[i] == min(window) and vals[i] < vals[i - 1] and vals[i] < vals[i + 1]:
            troughs.append(i)
    return peaks, troughs


def _impulse_then_consolidate(closes: list[float], bullish: bool) -> float:
    """Score 0–1: strong move in first half, tighter range in second half."""
    if len(closes) < 30:
        return 0.0
    mid = len(closes) // 2
    first, second = closes[:mid], closes[mid:]
    move = (first[-1] - first[0]) / first[0] if first[0] else 0
    if bullish and move < 0.005:
        return 0.0
    if not bullish and move > -0.005:
        return 0.0
    r1 = (max(first) - min(first)) / min(first) if min(first) else 0
    r2 = (max(second) - min(second)) / min(second) if min(second) else 0
    if r1 <= 0:
        return 0.0
    compression = max(0.0, min(1.0, 1.0 - (r2 / r1)))
    impulse = min(1.0, abs(move) * 20)
    return 0.55 * impulse + 0.45 * compression


def _near_equal(a: float, b: float, tol: float = 0.008) -> bool:
    if a == 0:
        return abs(b) < tol
    return abs(a - b) / abs(a) <= tol


def _vol_confirm(vols: list[float], impulse_end: int) -> float:
    """Higher volume on impulse vs consolidation → bonus 0–1."""
    if len(vols) < 20 or impulse_end <= 5:
        return 0.3
    imp = sum(vols[:impulse_end]) / impulse_end
    rest = sum(vols[impulse_end:]) / max(1, len(vols) - impulse_end)
    if rest == 0:
        return 0.5
    ratio = imp / rest
    return max(0.0, min(1.0, (ratio - 0.8) / 1.5))


# ── Pattern-specific detectors (return 0–100) ────────────────────────────────

def _score_bull_flag(candles: list[Candle]) -> dict[str, float]:
    closes, vols = _closes(candles), _vols(candles)
    base = _impulse_then_consolidate(closes, bullish=True)
    trend = _trend(closes)
    vol_b = _vol_confirm(vols, len(closes) // 2)
    # mild downward drift in second half is classic flag
    mid = len(closes) // 2
    drift = 0.0
    if mid > 5:
        d = (closes[-1] - closes[mid]) / closes[mid]
        drift = 0.15 if -0.03 < d < 0.01 else 0.0
    score = 100 * (0.50 * base + 0.25 * max(0, trend) + 0.15 * vol_b + drift)
    return {"total": round(min(100, score), 2), "impulse_compress": base, "trend": trend, "volume": vol_b}


def _score_bear_flag(candles: list[Candle]) -> dict[str, float]:
    closes, vols = _closes(candles), _vols(candles)
    base = _impulse_then_consolidate(closes, bullish=False)
    trend = _trend(closes)
    vol_b = _vol_confirm(vols, len(closes) // 2)
    mid = len(closes) // 2
    drift = 0.0
    if mid > 5:
        d = (closes[-1] - closes[mid]) / closes[mid]
        drift = 0.15 if -0.01 < d < 0.03 else 0.0
    score = 100 * (0.50 * base + 0.25 * max(0, -trend) + 0.15 * vol_b + drift)
    return {"total": round(min(100, score), 2), "impulse_compress": base, "trend": trend, "volume": vol_b}


def _score_bull_pennant(candles: list[Candle]) -> dict[str, float]:
    # similar to flag but prefer converging range (lower highs + higher lows)
    closes = _closes(candles)
    base = _impulse_then_consolidate(closes, bullish=True)
    highs, lows = _highs(candles), _lows(candles)
    mid = len(closes) // 2
    converge = 0.0
    if mid > 8:
        h1, h2 = max(highs[mid : mid + mid // 2]), max(highs[mid + mid // 2 :])
        l1, l2 = min(lows[mid : mid + mid // 2]), min(lows[mid + mid // 2 :])
        if h1 > 0 and l1 > 0:
            converge = max(0.0, min(1.0, ((h1 - h2) / h1) + ((l2 - l1) / l1)))
    trend = max(0, _trend(closes))
    score = 100 * (0.45 * base + 0.30 * converge + 0.25 * trend)
    return {"total": round(min(100, score), 2), "impulse_compress": base, "converge": converge, "trend": trend}


def _score_bear_pennant(candles: list[Candle]) -> dict[str, float]:
    closes = _closes(candles)
    base = _impulse_then_consolidate(closes, bullish=False)
    highs, lows = _highs(candles), _lows(candles)
    mid = len(closes) // 2
    converge = 0.0
    if mid > 8:
        h1, h2 = max(highs[mid : mid + mid // 2]), max(highs[mid + mid // 2 :])
        l1, l2 = min(lows[mid : mid + mid // 2]), min(lows[mid + mid // 2 :])
        if h1 > 0 and l1 > 0:
            converge = max(0.0, min(1.0, ((h1 - h2) / h1) + ((l2 - l1) / l1)))
    trend = max(0, -_trend(closes))
    score = 100 * (0.45 * base + 0.30 * converge + 0.25 * trend)
    return {"total": round(min(100, score), 2), "impulse_compress": base, "converge": converge, "trend": trend}


def _score_double_top(candles: list[Candle]) -> dict[str, float]:
    highs = _highs(candles)
    peaks, _ = _local_extrema(highs, order=4)
    if len(peaks) < 2:
        return {"total": 0.0}
    # last two significant peaks at similar height
    p1, p2 = peaks[-2], peaks[-1]
    equal = 1.0 if _near_equal(highs[p1], highs[p2], 0.012) else 0.0
    # neckline = min between peaks, price should be breaking or near it
    neck = min(_lows(candles)[p1:p2 + 1]) if p2 > p1 else highs[p2]
    last = candles[-1].close
    break_score = 1.0 if last < neck else max(0.0, 1.0 - (last - neck) / neck * 20) if neck else 0
    prior_up = 1.0 if _trend(_closes(candles)[: p1 + 1]) > 0.1 else 0.3
    score = 100 * (0.40 * equal + 0.35 * break_score + 0.25 * prior_up)
    return {"total": round(min(100, score), 2), "equal_peaks": equal, "breakdown": break_score, "prior_up": prior_up}


def _score_double_bottom(candles: list[Candle]) -> dict[str, float]:
    lows = _lows(candles)
    _, troughs = _local_extrema(lows, order=4)
    if len(troughs) < 2:
        return {"total": 0.0}
    t1, t2 = troughs[-2], troughs[-1]
    equal = 1.0 if _near_equal(lows[t1], lows[t2], 0.012) else 0.0
    neck = max(_highs(candles)[t1:t2 + 1]) if t2 > t1 else lows[t2]
    last = candles[-1].close
    break_score = 1.0 if last > neck else max(0.0, 1.0 - (neck - last) / neck * 20) if neck else 0
    prior_down = 1.0 if _trend(_closes(candles)[: t1 + 1]) < -0.1 else 0.3
    score = 100 * (0.40 * equal + 0.35 * break_score + 0.25 * prior_down)
    return {"total": round(min(100, score), 2), "equal_troughs": equal, "breakout": break_score, "prior_down": prior_down}


def _score_head_shoulders(candles: list[Candle]) -> dict[str, float]:
    highs = _highs(candles)
    peaks, _ = _local_extrema(highs, order=3)
    if len(peaks) < 3:
        return {"total": 0.0}
    l, h, r = peaks[-3], peaks[-2], peaks[-1]
    # head higher than both shoulders
    head_ok = 1.0 if highs[h] > highs[l] and highs[h] > highs[r] else 0.0
    shoulders_eq = 1.0 if _near_equal(highs[l], highs[r], 0.02) else 0.4
    # neckline approx avg of troughs between
    left_t = min(_lows(candles)[l:h + 1]) if h > l else highs[l]
    right_t = min(_lows(candles)[h:r + 1]) if r > h else highs[r]
    neck = (left_t + right_t) / 2
    last = candles[-1].close
    break_score = 1.0 if last < neck else max(0.0, 1.0 - (last - neck) / neck * 15) if neck else 0
    score = 100 * (0.40 * head_ok + 0.25 * shoulders_eq + 0.35 * break_score)
    return {"total": round(min(100, score), 2), "head": head_ok, "shoulders": shoulders_eq, "breakdown": break_score}


def _score_breakout_retest(candles: list[Candle]) -> dict[str, float]:
    closes, highs = _closes(candles), _highs(candles)
    if len(closes) < 40:
        return {"total": 0.0}
    # resistance = prior high in first 60%
    cut = int(len(closes) * 0.6)
    resistance = max(highs[:cut])
    later = closes[cut:]
    broke = any(c > resistance * 1.001 for c in later)
    # retest: after break, price came back near resistance then held
    retest = 0.0
    if broke:
        post = [(i, c) for i, c in enumerate(later) if c > resistance]
        if post:
            # look for pullback toward resistance after first break
            first_break_i = post[0][0]
            after = later[first_break_i:]
            if after:
                mn = min(after)
                if mn <= resistance * 1.008:
                    retest = 1.0 if closes[-1] >= resistance else 0.5
    trend = max(0, _trend(closes))
    score = 100 * (0.35 * (1.0 if broke else 0.0) + 0.40 * retest + 0.25 * trend)
    return {"total": round(min(100, score), 2), "broke": 1.0 if broke else 0.0, "retest": retest, "trend": trend}


def _score_breakdown_retest(candles: list[Candle]) -> dict[str, float]:
    closes, lows = _closes(candles), _lows(candles)
    if len(closes) < 40:
        return {"total": 0.0}
    cut = int(len(closes) * 0.6)
    support = min(lows[:cut])
    later = closes[cut:]
    broke = any(c < support * 0.999 for c in later)
    retest = 0.0
    if broke:
        post = [(i, c) for i, c in enumerate(later) if c < support]
        if post:
            first_break_i = post[0][0]
            after = later[first_break_i:]
            if after:
                mx = max(after)
                if mx >= support * 0.992:
                    retest = 1.0 if closes[-1] <= support else 0.5
    trend = max(0, -_trend(closes))
    score = 100 * (0.35 * (1.0 if broke else 0.0) + 0.40 * retest + 0.25 * trend)
    return {"total": round(min(100, score), 2), "broke": 1.0 if broke else 0.0, "retest": retest, "trend": trend}


def _score_cup_handle(candles: list[Candle]) -> dict[str, float]:
    closes = _closes(candles)
    if len(closes) < 50:
        return {"total": 0.0}
    # U-shape: high → low mid → recovery near prior high, then small dip (handle)
    n = len(closes)
    left_hi = max(closes[: n // 4])
    mid_lo = min(closes[n // 4 : 3 * n // 4])
    right = closes[3 * n // 4 :]
    right_hi = max(right) if right else closes[-1]
    depth = (left_hi - mid_lo) / left_hi if left_hi else 0
    recovery = (right_hi - mid_lo) / (left_hi - mid_lo) if left_hi > mid_lo else 0
    u_shape = max(0.0, min(1.0, depth * 5)) * max(0.0, min(1.0, recovery))
    # handle: small pullback in last 15%
    handle_zone = closes[int(n * 0.85) :]
    handle = 0.0
    if handle_zone and right_hi:
        pull = (max(handle_zone) - min(handle_zone)) / max(handle_zone)
        handle = 1.0 if 0.005 < pull < 0.04 else 0.3
    trend = max(0, _trend(closes))
    score = 100 * (0.50 * u_shape + 0.25 * handle + 0.25 * trend)
    return {"total": round(min(100, score), 2), "u_shape": u_shape, "handle": handle, "trend": trend}


_DETECTORS = {
    "bull_flag": _score_bull_flag,
    "bear_flag": _score_bear_flag,
    "bull_pennant": _score_bull_pennant,
    "bear_pennant": _score_bear_pennant,
    "double_top": _score_double_top,
    "double_bottom": _score_double_bottom,
    "head_and_shoulders": _score_head_shoulders,
    "breakout_retest": _score_breakout_retest,
    "breakdown_retest": _score_breakdown_retest,
    "cup_and_handle": _score_cup_handle,
}


def match_window(window: CandleWindow) -> list[PatternMatch]:
    cfg = load_config().get("matcher", {})
    min_sim = float(cfg.get("min_similarity", 55.0))
    max_matches = int(cfg.get("max_matches_per_symbol", 3))

    patterns = load_patterns()
    matches: list[PatternMatch] = []

    for p in patterns:
        detector = _DETECTORS.get(p.key)
        if detector is None:
            continue
        breakdown = detector(window.candles)
        sim = float(breakdown.get("total", 0.0))
        if sim < min_sim:
            continue
        matches.append(
            PatternMatch(
                pattern_key=p.key,
                pattern_name=p.name,
                direction=p.direction,
                similarity=sim,
                matched_example=None,
                score_breakdown={k: float(v) for k, v in breakdown.items() if k != "total"},
            )
        )

    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches[:max_matches]
