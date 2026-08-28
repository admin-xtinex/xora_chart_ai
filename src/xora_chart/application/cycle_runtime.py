"""Single-process scan-cycle coordinator.

The automatic scheduler and user-triggered scans share this gate so expensive
market analysis cannot overlap and mutate the same opportunities/positions at
once on the single-VM deployment.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from xora_chart.application.pipeline import run_cycle as _run_cycle
from xora_chart.domain.models import CycleResult, DiscoveredCoin
from xora_chart.persistence.store import Store

_lock = asyncio.Lock()
_state: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_cycle_id": None,
    "last_error": None,
}


def cycle_status() -> dict[str, Any]:
    return dict(_state)


async def run_cycle(
    store: Store | None = None,
    *,
    histories: dict[str, list[Any]] | None = None,
    coins_override: list[dict[str, Any] | DiscoveredCoin] | None = None,
) -> CycleResult:
    if _lock.locked():
        raise RuntimeError("A market scan is already running. Wait for the active cycle to finish.")

    async with _lock:
        _state.update(
            running=True,
            started_at=datetime.now(UTC).isoformat(),
            last_error=None,
        )
        try:
            result = await _run_cycle(
                store=store,
                histories=histories,
                coins_override=coins_override,
            )
            _state["last_cycle_id"] = result.cycle_id
            return result
        except Exception as exc:
            _state["last_error"] = str(exc)
            raise
        finally:
            _state["running"] = False
            _state["finished_at"] = datetime.now(UTC).isoformat()
