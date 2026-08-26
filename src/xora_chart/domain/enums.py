from enum import Enum


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class PatternType(str, Enum):
    CONTINUATION = "continuation"
    REVERSAL = "reversal"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OpportunityStatus(str, Enum):
    CANDIDATE = "candidate"
    WAITING = "waiting"
    VALIDATED = "validated"
    REJECTED = "rejected"
    EXPIRED = "expired"
    TRADED = "traded"


class DecisionAction(str, Enum):
    APPROVE = "APPROVE"
    WAIT = "WAIT"
    REJECT = "REJECT"


class SignalStatus(str, Enum):
    PASS = "pass"
    WEAK = "weak"
    FAIL = "fail"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"


class TradeMode(str, Enum):
    DEMO = "demo"
    LIVE = "live"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
