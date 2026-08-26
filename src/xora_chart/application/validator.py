"""
AI Validator

Runs only when similarity ≥ ai_threshold.

Modes:
  1. ai.enabled=false → auto-accept above threshold (deterministic)
  2. ai.enabled=true + API key → call OpenAI-compatible chat API
  3. ai.enabled=true but no key → structured rule-based validation
"""

from __future__ import annotations

import json
import logging
import os
import re

import httpx

from xora_chart.config import load_config
from xora_chart.domain.models import CandleWindow, PatternMatch

log = logging.getLogger(__name__)


def _candle_summary(window: CandleWindow, n: int = 30) -> str:
    candles = window.candles[-n:]
    lines = []
    for c in candles:
        lines.append(
            f"o={c.open:.6g} h={c.high:.6g} l={c.low:.6g} c={c.close:.6g} v={c.volume:.4g}"
        )
    first, last = candles[0].close, candles[-1].close
    change = ((last - first) / first * 100) if first else 0
    return (
        f"Symbol={window.symbol} interval={window.interval} bars={len(window.candles)}\n"
        f"Window change={change:.2f}% last={last:.6g}\n"
        f"Last {len(candles)} candles:\n" + "\n".join(lines)
    )


def _rule_based(window: CandleWindow, match: PatternMatch) -> tuple[bool, str]:
    """Deterministic secondary checks when no LLM key is available."""
    closes = [c.close for c in window.candles]
    if len(closes) < 20:
        return False, "Insufficient candles for validation"

    # direction consistency with last 10 bars
    recent = closes[-10:]
    move = (recent[-1] - recent[0]) / recent[0] if recent[0] else 0
    bullish = match.direction.value == "bullish"

    if bullish and move < -0.015:
        return False, f"Rejected: bullish pattern but recent move {move*100:.2f}% is against"
    if not bullish and move > 0.015:
        return False, f"Rejected: bearish pattern but recent move {move*100:.2f}% is against"

    # require non-trivial structure score components if present
    bd = match.score_breakdown or {}
    weak = sum(1 for v in bd.values() if isinstance(v, (int, float)) and v < 0.15)
    if weak >= 3:
        return False, f"Rejected: too many weak feature components ({weak})"

    if match.similarity >= 85:
        return True, f"Rule-validated: high similarity {match.similarity:.1f}% + direction aligned"
    return True, f"Rule-validated: similarity {match.similarity:.1f}% passed secondary checks"


async def _llm_validate(window: CandleWindow, match: PatternMatch, cfg: dict) -> tuple[bool, str]:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("XORA_AI_API_KEY") or cfg.get("api_key")
    base_url = (
        os.getenv("XORA_AI_BASE_URL")
        or cfg.get("base_url")
        or "https://api.openai.com/v1"
    )
    model = os.getenv("XORA_AI_MODEL") or cfg.get("model") or "gpt-4o-mini"

    if not api_key:
        log.info("No AI API key — falling back to rule-based validation")
        return _rule_based(window, match)

    prompt = f"""You are a strict crypto chart-pattern validator for Binance Futures.

Candidate setup:
- Symbol: {window.symbol}
- Pattern: {match.pattern_name} ({match.pattern_key})
- Direction: {match.direction.value}
- Similarity score: {match.similarity:.1f}%
- Feature breakdown: {json.dumps(match.score_breakdown)}

Market window:
{_candle_summary(window)}

Decide if this is a TRADEABLE setup right now.
Reply ONLY with JSON:
{{"accept": true/false, "confidence": 0-100, "reason": "one short sentence"}}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "You validate chart patterns. Be conservative."},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log.warning("LLM call failed: %s — rule fallback", e)
        return _rule_based(window, match)

    # parse JSON from response
    try:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        data = json.loads(m.group(0) if m else content)
        accept = bool(data.get("accept", False))
        reason = str(data.get("reason") or content)[:300]
        conf = data.get("confidence")
        if conf is not None:
            reason = f"[{conf}%] {reason}"
        return accept, f"AI: {reason}"
    except Exception:
        lowered = content.lower()
        accept = "accept": true" in lowered or '"accept":true' in lowered or "accept: true" in lowered
        return accept, f"AI (unparsed): {content[:240]}"


async def validate(
    window: CandleWindow,
    match: PatternMatch,
) -> tuple[bool, str | None]:
    cfg = load_config().get("ai", {})
    matcher_cfg = load_config().get("matcher", {})
    threshold = float(matcher_cfg.get("ai_threshold", 70.0))

    if match.similarity < threshold:
        # still allow mid-tier matches through trade generator path without AI label
        # pipeline currently only keeps accepted — so soft-accept mid scores via rules
        if match.similarity >= float(matcher_cfg.get("min_similarity", 55.0)):
            ok, reason = _rule_based(window, match)
            return ok, f"Below AI threshold ({threshold}); {reason}"
        return False, f"Similarity {match.similarity:.1f} below threshold {threshold}"

    if not cfg.get("enabled", False):
        ok, reason = _rule_based(window, match)
        return ok, f"AI disabled — {reason}"

    return await _llm_validate(window, match, cfg)
