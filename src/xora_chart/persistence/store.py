"""Small durable state store for the single-VM deployment.

The domain API remains the same, but state is snapshotted to JSON so settings,
opportunities, cycles, and demo positions survive container rebuilds/restarts.
"""

from __future__ import annotations

import json
import os
import threading
from collections import deque
from pathlib import Path
from typing import Any

from xora_chart.config import load_config
from xora_chart.domain.models import CycleResult, Opportunity, Position


class Store:
    _instance: "Store | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        cfg = load_config().get("store", {})
        trade_cfg = load_config().get("trade", {})
        self._max_cycles = int(cfg.get("max_cycles_kept", 50))
        self._max_opps = int(cfg.get("max_opportunities_kept", 200))
        self._max_positions = int(cfg.get("max_positions_kept", 200))
        self._cycles: deque[CycleResult] = deque(maxlen=self._max_cycles)
        self._opps_by_symbol: dict[str, Opportunity] = {}
        self._opp_order: deque[str] = deque()
        self._positions: dict[str, Position] = {}
        self._position_order: deque[str] = deque(maxlen=self._max_positions)
        self._latest_cycle: CycleResult | None = None
        self._settings: dict[str, Any] = {
            "auto_trade": bool(trade_cfg.get("auto_trade", False)),
            "trade_mode": str(trade_cfg.get("mode", "demo")),
        }
        self._state_path = Path(os.getenv("XORA_STATE_FILE", "state/xora_state.json"))
        self._io_lock = threading.RLock()
        self._restore()

    @classmethod
    def instance(cls) -> "Store":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = Store()
        return cls._instance

    def _restore(self) -> None:
        try:
            if not self._state_path.exists():
                return
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            self._settings.update(raw.get("settings") or {})

            cycles = [CycleResult.model_validate(x) for x in raw.get("cycles") or []]
            self._cycles = deque(cycles[: self._max_cycles], maxlen=self._max_cycles)
            self._latest_cycle = self._cycles[0] if self._cycles else None

            opps = [Opportunity.model_validate(x) for x in raw.get("opportunities") or []]
            self._opps_by_symbol = {o.symbol.upper(): o for o in opps[: self._max_opps]}
            self._opp_order = deque([o.symbol.upper() for o in opps[: self._max_opps]])

            positions = [Position.model_validate(x) for x in raw.get("positions") or []]
            positions = positions[: self._max_positions]
            self._positions = {p.id: p for p in positions}
            self._position_order = deque([p.id for p in positions], maxlen=self._max_positions)
        except Exception:
            # Corrupt/old state must never stop the scanner from booting.
            return

    def _persist(self) -> None:
        with self._io_lock:
            try:
                self._state_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "settings": self._settings,
                    "cycles": [c.model_dump(mode="json") for c in self._cycles],
                    "opportunities": [o.model_dump(mode="json") for o in self.list_opportunities(self._max_opps)],
                    "positions": [p.model_dump(mode="json") for p in self.list_positions()],
                }
                tmp = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
                tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
                tmp.replace(self._state_path)
            except Exception:
                # Runtime scanning should continue even if persistence is temporarily unavailable.
                return

    def get_settings(self) -> dict[str, Any]:
        return dict(self._settings)

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        if "auto_trade" in patch:
            self._settings["auto_trade"] = bool(patch["auto_trade"])
        if "trade_mode" in patch and patch["trade_mode"] in ("demo", "live"):
            self._settings["trade_mode"] = patch["trade_mode"]
        self._persist()
        return self.get_settings()

    def auto_trade_enabled(self) -> bool:
        return bool(self._settings.get("auto_trade"))

    def save_cycle(self, cycle: CycleResult) -> None:
        self._cycles.appendleft(cycle)
        self._latest_cycle = cycle
        self._persist()

    def save_opportunities(self, opps: list[Opportunity]) -> None:
        for o in opps:
            key = o.symbol.upper()
            if key not in self._opps_by_symbol:
                self._opp_order.appendleft(key)
            self._opps_by_symbol[key] = o
        while len(self._opp_order) > self._max_opps:
            old = self._opp_order.pop()
            self._opps_by_symbol.pop(old, None)
        self._persist()

    def update_opportunity(self, opp: Opportunity) -> None:
        key = opp.symbol.upper()
        self._opps_by_symbol[key] = opp
        if key not in self._opp_order:
            self._opp_order.appendleft(key)
        self._persist()

    def latest_cycle(self) -> CycleResult | None:
        return self._latest_cycle

    def list_cycles(self, limit: int = 20) -> list[CycleResult]:
        return list(self._cycles)[:limit]

    def list_opportunities(self, limit: int = 50) -> list[Opportunity]:
        items: list[Opportunity] = []
        seen: set[str] = set()
        for key in self._opp_order:
            if key in seen:
                continue
            seen.add(key)
            o = self._opps_by_symbol.get(key)
            if o:
                items.append(o)
            if len(items) >= limit:
                break
        return items

    def get_opportunity(self, opp_id: str) -> Opportunity | None:
        for o in self._opps_by_symbol.values():
            if o.id == opp_id:
                return o
        return None

    def get_opportunity_by_symbol(self, symbol: str) -> Opportunity | None:
        return self._opps_by_symbol.get(symbol.upper())

    def save_position(self, pos: Position) -> None:
        if pos.id not in self._positions:
            self._position_order.appendleft(pos.id)
        self._positions[pos.id] = pos
        self._persist()

    def get_position(self, pos_id: str) -> Position | None:
        return self._positions.get(pos_id)

    def list_positions(self) -> list[Position]:
        return [self._positions[i] for i in self._position_order if i in self._positions]
