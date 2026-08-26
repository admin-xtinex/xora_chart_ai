from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from xora_chart.api.v1 import router as v1_router

app = FastAPI(
    title="XORA Chart AI",
    description="Chart Pattern Recognition & Educational Intelligence — Phase 1",
    version="0.1.0",
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
        "phase": 1,
        "status": "complete",
        "docs": "/docs",
        "patterns": "/api/v1/patterns",
    }
