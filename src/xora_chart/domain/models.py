from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from xora_chart.domain.enums import Direction, OpportunityStatus, PatternType, Side


# ── Phase 1 educational catalog ──────────────────────────────────────────────

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


# ── Market data ──────────────────────────────────────────────────────────────

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


# ── Discovery ────────────────────────────────────────────────────────────────

class DiscoveredCoin(BaseModel):
    symbol: str
    source: str  # gainer | loser | volume | trending
    rank_in_source: int = 0
    price_change_pct: float | None = None
    quote_volume: float | None = None


# ── Pattern matching ─────────────────────────────────────────────────────────

class PatternMatch(BaseModel):
    pattern_key: str
    pattern_name: str
    direction: Direction
    similarity: float  # 0–100
    matched_example: str | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)


# ── Trade setup ──────────────────────────────────────────────────────────────

class TradeLevels(BaseModel):
    side: Side
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float | None = None
    take_profit_3: float | None = None
    risk_reward: float
    confidence: float  # 0–100


# ── Opportunity (final ranked item) ──────────────────────────────────────────

class Opportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    interval: str = "1m"
    status: OpportunityStatus = OpportunityStatus.CANDIDATE

    best_match: PatternMatch | None = None
    all_matches: list[PatternMatch] = Field(default_factory=list)

    trade: TradeLevels | None = None

    ai_validated: bool = False
    ai_rationale: str | None = None

    rank_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    cycle_id: str | None = None

    # raw context for detail view
    candle_count: int = 0
    last_price: float | None = None


class CycleResult(BaseModel):
    cycle_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    symbols_scanned: list[str] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
