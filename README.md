# XORA Chart AI

**Chart Pattern Recognition & Educational Intelligence** for the XORA Prediction Platform.

This service provides:

- Structured knowledge of classic price-action patterns
- Educational reference cards (the images in `chart_reference/`)
- A modern React frontend to browse patterns
- A pluggable `chart_pattern` feature module compatible with `xora_trade_ai`
- Future vision / LLM pattern detection (Phase 2+)

It never executes trades. It only produces pattern features and explanations that the Prediction AI can consume.

---

## Quick start (Docker — recommended)

```bash
git clone https://github.com/admin-xtinex/xora_chart_ai.git
cd xora_chart_ai
docker compose up --build
```

| Service  | URL |
|----------|-----|
| **Frontend** | http://localhost:3030 |
| **Backend API** | http://localhost:8030 |
| API docs | http://localhost:8030/docs |
| Health | http://localhost:8030/api/v1/health |
| Patterns | http://localhost:8030/api/v1/patterns |

Port **8030** is used for the API (8000 is commonly taken by other XORA services).

---

## Local development (without Docker)

### Backend

```bash
pip install -e .
uvicorn xora_chart.main:app --host 0.0.0.0 --port 8030 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3030 (proxies /api → :8030)
```

---

## Phase 1 Status: **COMPLETE**

See [`docs/PHASE1.md`](docs/PHASE1.md).

| Deliverable | Status |
|-------------|--------|
| Project scaffolding & identity | ✅ |
| Complete pattern catalog (10 patterns) | ✅ |
| Structured pattern data (JSON + Python) | ✅ |
| FastAPI backend on **port 8030** | ✅ |
| React + Tailwind frontend | ✅ |
| Docker + docker-compose (backend + frontend) | ✅ |
| Module contract skeleton for `xora_trade_ai` | ✅ |

---

## Pattern Library

| Pattern | Direction | Type |
|---------|-----------|------|
| Breakout + Retest | Bullish | Continuation |
| Breakdown + Retest | Bearish | Continuation |
| Head and Shoulders | Bearish | Reversal |
| Double Top | Bearish | Reversal |
| Double Bottom | Bullish | Reversal |
| Cup and Handle | Bullish | Continuation |
| Bull Flag | Bullish | Continuation |
| Bear Flag | Bearish | Continuation |
| Bull Pennant | Bullish | Continuation |
| Bear Pennant | Bearish | Continuation |

---

## Architecture (Phase 1)

```
┌─────────────────┐     ┌──────────────────────┐
│  React Frontend │────▶│  FastAPI Backend     │
│  :3030 (nginx)  │     │  :8030               │
└─────────────────┘     │  /api/v1/patterns    │
                        │  /references/*       │
                        └──────────────────────┘
```

---

## Integration with xora_trade_ai

This repo will later export a drop-in module `chart_pattern` that implements the `Analyzer` protocol. Phase 1 only provides the skeleton + catalog. Detection logic lands in Phase 2.

---

## License

Private — XORA / Xtinex
