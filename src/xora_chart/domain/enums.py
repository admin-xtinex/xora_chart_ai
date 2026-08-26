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
    VALIDATED = "validated"
    REJECTED = "rejected"
    EXPIRED = "expired"
