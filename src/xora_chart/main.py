from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from xora_chart.api.v1 import router as v1_router

app = FastAPI(
    title="XORA Chart AI",
    description="Live chart-pattern scanner for Binance Futures — Phase 2",
    version="0.2.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/")
def root() -> dict:
    return {
        "service": "xora-chart-ai",
        "phase": 2,
        "status": "live-candles",
        "port": 8030,
        "docs": "/docs",
        "patterns": "/api/v1/patterns",
        "opportunities": "/api/v1/opportunities",
        "run_cycle": "POST /api/v1/cycles/run",
    }
