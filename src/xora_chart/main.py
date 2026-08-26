from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from xora_chart.api.v1 import router as v1_router

app = FastAPI(
    title="XORA Chart AI",
    description="Engine-based live scanner — Analysis · Decision · Trade (API-first for Web + Android)",
    version="0.3.0",
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
        "phase": 3,
        "engines": ["analysis", "decision", "trade"],
        "port": 8030,
        "docs": "/docs",
        "opportunities": "/api/v1/opportunities",
        "positions": "/api/v1/positions",
        "run_cycle": "POST /api/v1/cycles/run",
    }
