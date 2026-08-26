from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from xora_chart.domain.enums import (
    DecisionAction,
    Direction,
    MarketRegime,
    OpportunityStatus,
    PatternType,
    PositionStatus,
    Side,
    SignalStatus,
    TradeMode,
)


class TradingSetup(BaseModel):
    entry: str
    stop_loss: str
    target: str


class Pattern(BaseModel):
    key: str
    name: str
    direction: Direction
    type: PatternType
    overview: str
    characteristics: list[str]
    trading_setup: TradingSetup
    key_points: list[str]
    volume_behaviour: dict[str, str] = Field(default_factory=dict)
    extras: dict[str, Any] = Field(default_factory=dict)


class Candle(BaseModel):
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int | None = None


class CandleWindow(BaseModel):
    symbol: str
    interval: str
    candles: list[Candle]
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class DiscoveredCoin(BaseModel):
    symbol: str
    source: str
    rank_in_source: int = 0
    price_change_pct: float | None = None
    quote_volume: float | None = None


class PatternMatch(BaseModel):
    pattern_key: str
    pattern_name: str
    direction: Direction
    similarity: float
    matched_example: str | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class AnalysisSignal(BaseModel):
    name: str
    score: float = 0.0
    status: SignalStatus = SignalStatus.WEAK
    note: str = ""


class MarketAnalysis(BaseModel):
    symbol: str
    score: float = 0.0
    bias: Direction = Direction.NEUTRAL
    regime: MarketRegime = MarketRegime.RANGING
    signals: list[AnalysisSignal] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TradeLevels(BaseModel):
    side: Side
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float | None = None
    take_profit_3: float | None = None
    risk_reward: float
    confidence: float


class Confirmation(BaseModel):
    name: str
    required: bool = True
    met: bool = False
    note: str = ""


class TradeDecision(BaseModel):
    action: DecisionAction
    reason: str = ""
    setup: TradeLevels | None = None
    confirmations: list[Confirmation] = Field(default_factory=list)
    analysis_score: float = 0.0
    pattern_similarity: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: Side
    mode: TradeMode = TradeMode.DEMO
    status: PositionStatus = PositionStatus.OPEN

    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float | None = None
    take_profit_3: float | None = None

    quantity: float = 0.0
    leverage: int = 1
    margin_used: float = 0.0

    opportunity_id: str | None = None
    decision_reason: str | None = None

    last_price: float | None = None
    exit_reason: str | None = None  # sl | tp1 | tp2 | tp3 | manual | expire

    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: datetime | None = None
    exit_price: float | None = None
    realized_pnl: float | None = None


class Opportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    interval: str = "1m"
    status: OpportunityStatus = OpportunityStatus.CANDIDATE

    best_match: PatternMatch | None = None
    all_matches: list[PatternMatch] = Field(default_factory=list)

    market_analysis: MarketAnalysis | None = None
    decision: TradeDecision | None = None
    trade: TradeLevels | None = None

    ai_validated: bool = False
    ai_rationale: str | None = None
    analysis: dict[str, Any] = Field(default_factory=dict)

    rank_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    cycle_id: str | None = None

    candle_count: int = 0
    last_price: float | None = None
    candles: list[Candle] = Field(default_factory=list)


class CycleResult(BaseModel):
    cycle_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    symbols_scanned: list[str] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    positions_closed: int = 0
