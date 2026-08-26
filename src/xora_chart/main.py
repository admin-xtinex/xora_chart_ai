from __future__ import annotations

import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI

from xora_chart.api.ws import router as ws_router
from xora_chart.application.pipeline import run_cycle
from xora_chart.config import load_config
from xora_chart.services.binance_ws import BinanceWSHub, ensure_hub

log = logging.getLogger(__name__)


async def _cycle_loop() -> None:
    cfg = load_config().get("cycle", {})
    interval = max(10, int(cfg.get("interval_seconds", 60)))
    enabled = bool(cfg.get("enabled", True))
    if not enabled:
        log.info("Automatic scan cycle disabled")
        return

    # Give the all-market ticker stream time to populate and subscribe the
    # discovered watchlist before attempting candle-based analysis.
    await asyncio.sleep(10)
    while True:
        try:
            result = await run_cycle()
            log.info(
                "WS-only cycle %s scanned=%d opportunities=%d errors=%d",
                result.cycle_id,
                len(result.symbols_scanned),
                len(result.opportunities),
                len(result.errors),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("WS-only automatic scan failed")
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
    description="WebSocket-only reference-chart gated scanner",
    version="0.5.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# The production application transport is WebSocket-only. No REST data router
# is mounted. Static UI is served separately by Nginx.
app.include_router(ws_router)
