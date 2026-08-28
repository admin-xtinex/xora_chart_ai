from __future__ import annotations

import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI

from xora_chart.api.ops import router as ops_router
from xora_chart.api.ws import router as ws_router
from xora_chart.application.cycle_runtime import run_cycle
from xora_chart.config import load_config
from xora_chart.services.binance_ws import ensure_hub

log = logging.getLogger(__name__)


async def _cycle_loop() -> None:
    cfg = load_config().get("cycle", {})
    interval = max(10, int(cfg.get("interval_seconds", 60)))
    enabled = bool(cfg.get("enabled", True))
    if not enabled:
        log.info("Automatic scan cycle disabled")
        return

    # Give the live WebSocket price feed time to populate before the first scan.
    # Historical windows use Binance Futures REST when reachable; the persisted
    # WS candle cache remains a recovery path for backend locations receiving 451.
    await asyncio.sleep(10)
    while True:
        try:
            result = await run_cycle()
            log.info(
                "Hybrid cycle %s scanned=%d opportunities=%d errors=%d",
                result.cycle_id,
                len(result.symbols_scanned),
                len(result.opportunities),
                len(result.errors),
            )
        except asyncio.CancelledError:
            raise
        except RuntimeError as exc:
            # A user-triggered scan can briefly own the single-cycle coordinator.
            # That is expected; the scheduler simply tries again next interval.
            if "already running" in str(exc):
                log.info("Automatic scan skipped because another cycle is active")
            else:
                log.exception("Hybrid automatic scan failed")
        except Exception:
            log.exception("Hybrid automatic scan failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    hub = await ensure_hub()
    cycle_task = asyncio.create_task(_cycle_loop(), name="xora-cycle-loop")
    try:
        yield
    finally:
        cycle_task.cancel()
        try:
            await cycle_task
        except asyncio.CancelledError:
            pass
        hub.stop()


app = FastAPI(
    title="XORA Chart AI",
    description="REST-history + WebSocket-live reference-chart gated scanner",
    version="0.7.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Trading/application commands remain WebSocket RPC. HTTP is limited to
# operational liveness/readiness so deployments do not need to open an RPC
# WebSocket merely to determine whether the service is healthy.
app.include_router(ops_router)
app.include_router(ws_router)
