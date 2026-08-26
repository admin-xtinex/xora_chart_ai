"""
Pattern Matcher — Phase 2 skeleton.

Uses simple geometric / statistical heuristics on the candle window to score
similarity against the known pattern catalog. Real vision / embedding similarity
lands in Phase 3; this layer already returns the same PatternMatch shape so the
rest of the pipeline stays stable.
"""

from __future__ import annotations

from xora_chart.catalog import load_patterns
from xora_chart.config import load_config
from xora_chart.domain.enums import Direction
from xora_chart.domain.models import CandleWindow, PatternMatch


def _returns(window: CandleWindow) -> list[float]:
    closes = [c.close for c in window.candles]
    if len(closes) < 2:
        return []
    return [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]


def _trend_score(window: CandleWindow) -> float:
    """Positive = uptrend, negative = downtrend, magnitude ~0–1."""
    closes = [c.close for c in window.candles]
    if len(closes) < 10:
        return 0.0
    first = sum(closes[:10]) / 10
    last = sum(closes[-10:]) / 10
    if first == 0:
        return 0.0
    return max(-1.0, min(1.0, (last - first) / first * 5))


def _volatility(window: CandleWindow) -> float:
    rets = _returns(window)
    if not rets:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return var ** 0.5


def _score_pattern(window: CandleWindow, pattern_key: str, direction: Direction) -> float:
    """Heuristic score 0–100. Replace with real similarity in Phase 3."""
    trend = _trend_score(window)
    vol = _volatility(window)
    closes = [c.close for c in window.candles]
    if not closes:
        return 0.0

    # Direction alignment
    dir_align = 0.0
    if direction == Direction.BULLISH and trend > 0:
        dir_align = min(1.0, trend)
    elif direction == Direction.BEARISH and trend < 0:
        dir_align = min(1.0, -trend)

    # Pattern-family hints (very rough)
    family_bonus = 0.0
    recent = closes[-20:] if len(closes) >= 20 else closes
    hi, lo = max(recent), min(recent)
    rng = (hi - lo) / lo if lo else 0

    if pattern_key in ("bull_flag", "bear_flag", "bull_pennant", "bear_pennant"):
        # flags/pennants prefer prior impulse + consolidation (lower recent vol vs full)
        family_bonus = 0.15 if vol < 0.01 else 0.05
    elif pattern_key in ("double_top", "double_bottom", "head_and_shoulders"):
        family_bonus = 0.1 if rng > 0.01 else 0.0
    elif pattern_key in ("breakout_retest", "breakdown_retest"):
        family_bonus = 0.1 if abs(trend) > 0.2 else 0.0
    elif pattern_key == "cup_and_handle":
        family_bonus = 0.1 if trend > 0 else 0.0

    raw = 40 * dir_align + 25 * min(1.0, abs(trend)) + 20 * family_bonus + 15 * min(1.0, vol * 50)
    return round(max(0.0, min(100.0, raw * 100 if raw <= 1 else raw)), 2)


def match_window(window: CandleWindow) -> list[PatternMatch]:
    cfg = load_config().get("matcher", {})
    min_sim = float(cfg.get("min_similarity", 60.0))
    max_matches = int(cfg.get("max_matches_per_symbol", 3))

    patterns = load_patterns()
    matches: list[PatternMatch] = []

    for p in patterns:
        # catalog Direction may include only bullish/bearish
        sim = _score_pattern(window, p.key, p.direction)
        if sim < min_sim:
            continue
        matches.append(
            PatternMatch(
                pattern_key=p.key,
                pattern_name=p.name,
                direction=p.direction,
                similarity=sim,
                matched_example=None,
                score_breakdown={"heuristic": sim},
            )
        )

    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches[:max_matches]
