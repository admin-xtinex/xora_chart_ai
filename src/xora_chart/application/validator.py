"""
AI Validator — Phase 2 placeholder.

Only invoked when similarity ≥ ai_threshold.
When ai.enabled is false, high-similarity matches are auto-accepted.
Phase 3 will plug in a real LLM / vision validator here.
"""

from __future__ import annotations

from xora_chart.config import load_config
from xora_chart.domain.models import CandleWindow, PatternMatch


async def validate(
    window: CandleWindow,
    match: PatternMatch,
) -> tuple[bool, str | None]:
    cfg = load_config().get("ai", {})
    matcher_cfg = load_config().get("matcher", {})
    threshold = float(matcher_cfg.get("ai_threshold", 80.0))

    if match.similarity < threshold:
        return False, f"Similarity {match.similarity:.1f} below AI threshold {threshold}"

    if not cfg.get("enabled", False):
        return True, "Auto-accepted (AI validator disabled in config)"

    # Phase 3: call LLM/vision with candles + reference pattern context
    return True, "AI validation not yet implemented — accepted by default"
