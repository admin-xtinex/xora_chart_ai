from __future__ import annotations

from xora_chart.config import load_config
from xora_chart.domain.enums import Direction, Side
from xora_chart.domain.models import CandleWindow, PatternMatch, TradeLevels


def generate_trade(window: CandleWindow, match: PatternMatch) -> TradeLevels | None:
    if not window.candles:
        return None

    cfg = load_config().get("trade", {})
    rr_targets = cfg.get("default_rr_targets", [1.5, 2.5, 3.5])
    min_rr = float(cfg.get("min_risk_reward", 1.5))

    last = window.candles[-1]
    entry = last.close

    # ATR-like range from last 14 bars
    recent = window.candles[-14:] if len(window.candles) >= 14 else window.candles
    ranges = [c.high - c.low for c in recent]
    atr = sum(ranges) / len(ranges) if ranges else entry * 0.005
    risk = max(atr, entry * 0.002)

    if match.direction == Direction.BULLISH:
        side = Side.BUY
        stop = entry - risk
        tps = [entry + risk * float(r) for r in rr_targets]
        rr = float(rr_targets[0]) if rr_targets else 1.5
    else:
        side = Side.SELL
        stop = entry + risk
        tps = [entry - risk * float(r) for r in rr_targets]
        rr = float(rr_targets[0]) if rr_targets else 1.5

    if rr < min_rr:
        return None

    # Confidence blends similarity with a mild trend/vol factor
    confidence = min(99.0, match.similarity * 0.85 + 10)

    return TradeLevels(
        side=side,
        entry=round(entry, 6),
        stop_loss=round(stop, 6),
        take_profit_1=round(tps[0], 6) if len(tps) > 0 else round(entry, 6),
        take_profit_2=round(tps[1], 6) if len(tps) > 1 else None,
        take_profit_3=round(tps[2], 6) if len(tps) > 2 else None,
        risk_reward=round(rr, 2),
        confidence=round(confidence, 2),
    )
