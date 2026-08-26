"""Decision Engine — gates trades using reference chart + structure + analysis."""

from __future__ import annotations

from xora_chart.application.reference_visual import compare_window_to_references
from xora_chart.config import load_config
from xora_chart.domain.enums import DecisionAction, Direction, MarketRegime, Side, SignalStatus
from xora_chart.domain.models import (
    CandleWindow,
    Confirmation,
    MarketAnalysis,
    PatternMatch,
    TradeDecision,
    TradeLevels,
)


def _build_levels(window: CandleWindow, match: PatternMatch) -> TradeLevels | None:
    cfg = load_config().get("decision", {}) or load_config().get("trade", {})
    rr_targets = cfg.get("rr_targets") or load_config().get("trade", {}).get("default_rr_targets", [1.5, 2.5, 3.5])
    min_rr = float(cfg.get("min_risk_reward") or load_config().get("trade", {}).get("min_risk_reward", 1.5))
    if not window.candles:
        return None

    entry = window.candles[-1].close
    recent = window.candles[-14:] if len(window.candles) >= 14 else window.candles
    atr = sum(c.high - c.low for c in recent) / len(recent) if recent else entry * 0.005
    risk = max(atr, entry * 0.002)

    if match.direction == Direction.BULLISH:
        side = Side.BUY
        stop = entry - risk
        tps = [entry + risk * float(r) for r in rr_targets]
    elif match.direction == Direction.BEARISH:
        side = Side.SELL
        stop = entry + risk
        tps = [entry - risk * float(r) for r in rr_targets]
    else:
        return None

    rr = float(rr_targets[0]) if rr_targets else 1.5
    if rr < min_rr:
        return None

    confidence = min(99.0, match.similarity * 0.45 + match.reference_similarity * 0.35 + 10)
    return TradeLevels(
        side=side,
        entry=round(entry, 6),
        stop_loss=round(stop, 6),
        take_profit_1=round(tps[0], 6) if tps else round(entry, 6),
        take_profit_2=round(tps[1], 6) if len(tps) > 1 else None,
        take_profit_3=round(tps[2], 6) if len(tps) > 2 else None,
        risk_reward=round(rr, 2),
        confidence=round(confidence, 2),
    )


def _confirmations(
    window: CandleWindow,
    match: PatternMatch,
    analysis: MarketAnalysis,
    *,
    reference_count: int,
    expected_references: int,
    min_reference_similarity: float,
) -> list[Confirmation]:
    closes = [c.close for c in window.candles]
    vols = [c.volume for c in window.candles]
    confs: list[Confirmation] = [
        Confirmation(
            name="reference_library",
            required=True,
            met=reference_count >= expected_references,
            note=f"{reference_count}/{expected_references} reference charts loaded",
        ),
        Confirmation(
            name="reference_chart_match",
            required=True,
            met=bool(match.matched_example) and match.reference_similarity >= min_reference_similarity,
            note=(
                f"{match.reference_similarity:.1f}% vs {match.matched_example}"
                if match.matched_example
                else "No uploaded reference image matched"
            ),
        ),
        Confirmation(
            name="pattern_strength",
            required=True,
            met=match.similarity >= 55,
            note=f"Structural similarity {match.similarity:.1f}%",
        ),
        Confirmation(
            name="analysis_score",
            required=True,
            met=analysis.score >= 45,
            note=f"Analysis score {analysis.score:.1f}",
        ),
    ]

    aligned = (
        analysis.bias == Direction.NEUTRAL
        or (match.direction == Direction.BULLISH and analysis.bias == Direction.BULLISH)
        or (match.direction == Direction.BEARISH and analysis.bias == Direction.BEARISH)
    )
    confs.append(Confirmation(name="direction_align", required=True, met=aligned, note=f"Pattern {match.direction.value} · bias {analysis.bias.value}"))

    vol_ok = False
    if len(vols) >= 10:
        avg = sum(vols[-10:-1]) / 9
        vol_ok = avg > 0 and vols[-1] >= avg * 0.8
    confs.append(Confirmation(name="volume_support", required=False, met=vol_ok, note="Last bar volume vs recent avg"))

    confs.append(Confirmation(name="regime_ok", required=False, met=analysis.regime != MarketRegime.HIGH_VOL, note=f"Regime {analysis.regime.value}"))

    hard_fail = any(s.status == SignalStatus.FAIL and s.name in ("volume", "volatility") for s in analysis.signals)
    confs.append(Confirmation(name="no_hard_fail", required=True, met=not hard_fail, note="Volume/volatility hard fail check"))

    mom_ok = True
    if len(closes) >= 5:
        move = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] else 0
        mom_ok = move > -0.01 if match.direction == Direction.BULLISH else move < 0.01
    confs.append(Confirmation(name="momentum", required=False, met=mom_ok, note="Short momentum not strongly against pattern"))
    return confs


def run_decision(window: CandleWindow, match: PatternMatch, analysis: MarketAnalysis) -> TradeDecision:
    cfg = load_config().get("decision", {})
    min_sim = float(cfg.get("min_similarity", 55))
    min_analysis = float(cfg.get("min_analysis_score", 45))
    min_reference = float(cfg.get("min_reference_similarity", 55))
    expected_references = int(cfg.get("expected_reference_images", 10))
    require_all_required = bool(cfg.get("require_all_required", True))

    reference = compare_window_to_references(window)
    match.matched_example = reference.get("image")
    match.reference_similarity = float(reference.get("similarity") or 0.0)
    match.reference_verified = bool(match.matched_example and match.reference_similarity >= min_reference)
    match.score_breakdown["reference_visual"] = match.reference_similarity

    reference_count = int(reference.get("reference_count") or 0)
    confs = _confirmations(
        window,
        match,
        analysis,
        reference_count=reference_count,
        expected_references=expected_references,
        min_reference_similarity=min_reference,
    )
    required = [c for c in confs if c.required]
    optional = [c for c in confs if not c.required]
    required_met = all(c.met for c in required) if required else True
    optional_met_count = sum(1 for c in optional if c.met)
    setup = _build_levels(window, match)

    if reference_count < expected_references:
        return TradeDecision(
            action=DecisionAction.REJECT,
            reason=f"Reference library incomplete: {reference_count}/{expected_references} images",
            confirmations=confs,
            analysis_score=analysis.score,
            pattern_similarity=match.similarity,
        )

    if not match.reference_verified:
        return TradeDecision(
            action=DecisionAction.REJECT,
            reason=f"Reference chart match {match.reference_similarity:.1f} < {min_reference}",
            confirmations=confs,
            analysis_score=analysis.score,
            pattern_similarity=match.similarity,
        )

    if match.similarity < min_sim:
        return TradeDecision(
            action=DecisionAction.REJECT,
            reason=f"Structural similarity {match.similarity:.1f} < {min_sim}",
            confirmations=confs,
            analysis_score=analysis.score,
            pattern_similarity=match.similarity,
        )

    if analysis.score < min_analysis and require_all_required:
        return TradeDecision(
            action=DecisionAction.REJECT,
            reason=f"Analysis score {analysis.score:.1f} < {min_analysis}",
            confirmations=confs,
            analysis_score=analysis.score,
            pattern_similarity=match.similarity,
        )

    if not required_met:
        failed = [c.name for c in required if not c.met]
        hard_names = {"reference_library", "reference_chart_match", "no_hard_fail", "pattern_strength"}
        action = DecisionAction.REJECT if any(name in hard_names for name in failed) else DecisionAction.WAIT
        return TradeDecision(
            action=action,
            reason=f"Required confirmations failed: {', '.join(failed)}",
            setup=setup if action == DecisionAction.WAIT else None,
            confirmations=confs,
            analysis_score=analysis.score,
            pattern_similarity=match.similarity,
        )

    if setup is None:
        return TradeDecision(
            action=DecisionAction.REJECT,
            reason="Could not build valid RR levels",
            confirmations=confs,
            analysis_score=analysis.score,
            pattern_similarity=match.similarity,
        )

    setup.confidence = round(min(99.0, setup.confidence * 0.55 + analysis.score * 0.30 + match.reference_similarity * 0.15), 2)

    if optional_met_count < 1:
        return TradeDecision(
            action=DecisionAction.WAIT,
            reason="Reference + structure valid, waiting for volume/regime confirmation",
            setup=setup,
            confirmations=confs,
            analysis_score=analysis.score,
            pattern_similarity=match.similarity,
        )

    return TradeDecision(
        action=DecisionAction.APPROVE,
        reason=(
            f"Approved: reference {match.reference_similarity:.0f}% · structure {match.similarity:.0f}% · "
            f"analysis {analysis.score:.0f} · optional {optional_met_count}/{len(optional)}"
        ),
        setup=setup,
        confirmations=confs,
        analysis_score=analysis.score,
        pattern_similarity=match.similarity,
    )
