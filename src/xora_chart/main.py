from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

# Serve reference images so the frontend can display them
_REF_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "chart_reference",
    Path(__file__).resolve().parents[3] / "chart_reference",
    Path.cwd() / "chart_reference",
]
for _ref in _REF_CANDIDATES:
    if _ref.exists() and _ref.is_dir():
        app.mount("/references", StaticFiles(directory=str(_ref)), name="references")
        break


@app.get("/")
def root() -> dict:
    return {
        "service": "xora-chart-ai",
        "phase": 1,
        "status": "complete",
        "port": 8030,
        "docs": "/docs",
        "patterns": "/api/v1/patterns",
        "references": "/references/",
    }
