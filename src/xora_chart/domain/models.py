from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class PatternType(str, Enum):
    CONTINUATION = "continuation"
    REVERSAL = "reversal"


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
