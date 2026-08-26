"""In-memory store — swap for Redis/Postgres later without changing engines."""

from __future__ import annotations

import threading
from collections import deque

from xora_chart.config import load_config
from xora_chart.domain.models import CycleResult, Opportunity, Position


class Store:
    _instance: "Store | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        cfg = load_config().get("store", {})
        self._max_cycles = int(cfg.get("max_cycles_kept", 50))
        self._max_opps = int(cfg.get("max_opportunities_kept", 200))
        self._max_positions = int(cfg.get("max_positions_kept", 200))
        self._cycles: deque[CycleResult] = deque(maxlen=self._max_cycles)
        self._opportunities: deque[Opportunity] = deque(maxlen=self._max_opps)
        self._positions: dict[str, Position] = {}
        self._position_order: deque[str] = deque(maxlen=self._max_positions)
        self._latest_cycle: CycleResult | None = None

    @classmethod
    def instance(cls) -> "Store":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = Store()
        return cls._instance

    def save_cycle(self, cycle: CycleResult) -> None:
        self._cycles.appendleft(cycle)
        self._latest_cycle = cycle

    def save_opportunities(self, opps: list[Opportunity]) -> None:
        for o in reversed(opps):
            self._opportunities.appendleft(o)

    def latest_cycle(self) -> CycleResult | None:
        return self._latest_cycle

    def list_cycles(self, limit: int = 20) -> list[CycleResult]:
        return list(self._cycles)[:limit]

    def list_opportunities(self, limit: int = 50) -> list[Opportunity]:
        return list(self._opportunities)[:limit]

    def get_opportunity(self, opp_id: str) -> Opportunity | None:
        for o in self._opportunities:
            if o.id == opp_id:
                return o
        return None

    def save_position(self, pos: Position) -> None:
        if pos.id not in self._positions:
            self._position_order.appendleft(pos.id)
        self._positions[pos.id] = pos

    def get_position(self, pos_id: str) -> Position | None:
        return self._positions.get(pos_id)

    def list_positions(self) -> list[Position]:
        return [self._positions[i] for i in self._position_order if i in self._positions]
