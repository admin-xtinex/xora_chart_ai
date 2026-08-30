from __future__ import annotations

import pytest

from xora_chart.domain.enums import DecisionAction, Direction, Side
from xora_chart.domain.models import Opportunity, PatternMatch, TradeDecision, TradeLevels
from xora_chart.engines.trade.engine import open_from_opportunity


def setup() -> TradeLevels:
    return TradeLevels(
        side=Side.BUY,
        entry=100.0,
        stop_loss=99.0,
        take_profit_1=101.5,
        take_profit_2=102.5,
        take_profit_3=103.5,
        risk_reward=1.5,
        confidence=80.0,
    )


def approved(reference_verified: bool, matched_example: str | None = "reference.png") -> Opportunity:
    match = PatternMatch(
        pattern_key="bull_flag",
        pattern_name="Bull Flag",
        direction=Direction.BULLISH,
        similarity=80.0,
        matched_example=matched_example,
        reference_similarity=80.0,
        reference_verified=reference_verified,
    )
    return Opportunity(
        symbol="BTCUSDT",
        best_match=match,
        decision=TradeDecision(action=DecisionAction.APPROVE, setup=setup()),
        trade=setup(),
    )


def test_approve_without_reference_verification_is_blocked():
    with pytest.raises(RuntimeError, match="reference-chart verification"):
        open_from_opportunity(approved(False))


def test_approve_without_reference_image_name_is_blocked():
    with pytest.raises(RuntimeError, match="reference-chart verification"):
        open_from_opportunity(approved(True, None))


def test_wait_is_never_executable():
    opp = approved(True)
    opp.decision.action = DecisionAction.WAIT
    with pytest.raises(RuntimeError, match="not APPROVE"):
        open_from_opportunity(opp)
