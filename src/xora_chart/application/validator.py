"""Local deterministic validator.

XORA's no-REST invariant forbids external HTTP validation services. Validation
therefore uses only the current WebSocket-derived candle window plus the
reference-chart match already produced locally.
"""

from __future__ import annotations

from xora_chart.config import load_config
from xora_chart.domain.models import CandleWindow, PatternMatch


def _rule_based(window: CandleWindow, match: PatternMatch) -> tuple[bool, str]:
    closes = [c.close for c in window.candles]
    if len(closes) < 20:
        return False, "Insufficient WebSocket candles for validation"

    if not match.reference_verified or not match.matched_example:
        return False, "Reference-chart verification is required"

    recent = closes[-10:]
    move = (recent[-1] - recent[0]) / recent[0] if recent[0] else 0
    bullish = match.direction.value == "bullish"

    if bullish and move < -0.015:
        return False, f"Bullish reference match conflicts with WS momentum {move*100:.2f}%"
    if not bullish and move > 0.015:
        return False, f"Bearish reference match conflicts with WS momentum {move*100:.2f}%"

    bd = match.score_breakdown or {}
    weak = sum(1 for v in bd.values() if isinstance(v, (int, float)) and v < 0.15)
    if weak >= 3:
        return False, f"Too many weak structural components ({weak})"

    return True, (
        f"Local validation passed: reference={match.matched_example} "
        f"visual={match.reference_similarity:.1f}% structural={match.similarity:.1f}%"
    )


async def validate(window: CandleWindow, match: PatternMatch) -> tuple[bool, str | None]:
    matcher_cfg = load_config().get("matcher", {})
    threshold = float(matcher_cfg.get("min_similarity", 55.0))
    if match.similarity < threshold:
        return False, f"Similarity {match.similarity:.1f} below threshold {threshold}"
    return _rule_based(window, match)
