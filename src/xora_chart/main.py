from contextlib import asynccontextmanager

from fastapi import FastAPI

from xora_chart.api.v1 import router as v1_router
from xora_chart.services.binance_ws import BinanceWSHub, ensure_hub


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the WebSocket hub and actively seed tickers when the stream is slow
    # to become ready. This avoids a freshly deployed UI showing zero symbols.
    hub = await ensure_hub()
    yield
    hub.stop()


app = FastAPI(
    title="XORA Chart AI",
    description="Reference-chart gated live scanner — Visual Compare · Analysis · Decision · Trade",
    version="0.4.0",
    lifespan=lifespan,
)

# Production is same-origin behind Nginx, so permissive browser CORS is not
# required. Keeping the API same-origin also avoids accidental cross-site use.
app.include_router(v1_router)


@app.get("/")
def root() -> dict:
    hub = BinanceWSHub.instance()
    return {
        "service": "xora-chart-ai",
        "phase": 4,
        "engines": ["reference-visual", "analysis", "decision", "trade"],
        "binance": "websocket+seed",
        "ws_tickers": hub.ticker_count(),
        "reference_gate": True,
        "port": 8030,
        "docs": "/docs",
        "opportunities": "/api/v1/opportunities",
        "positions": "/api/v1/positions",
        "run_cycle": "POST /api/v1/cycles/run",
    }
