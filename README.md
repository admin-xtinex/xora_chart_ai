# XORA Chart AI

**Live chart-pattern scanner** for Binance Futures.

The system continuously discovers active coins, matches them against a curated pattern library, ranks the best setups, and surfaces them on a dashboard. Users do not upload charts — the platform scans automatically.

---

## Quick start

```bash
git clone https://github.com/admin-xtinex/xora_chart_ai.git
cd xora_chart_ai
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3030 |
| Backend API | http://localhost:8030 |
| API docs | http://localhost:8030/docs |
| Trigger scan | `POST http://localhost:8030/api/v1/cycles/run` |
| Opportunities | http://localhost:8030/api/v1/opportunities |

---

## Pipeline

```
Scheduler (1 min)
  → Discovery (≈20 coins)
  → 100 × 1m candles
  → Pattern Matcher
  → AI Validator (threshold-gated)
  → Trade Generator (Entry / SL / TP / RR)
  → Ranking
  → API → Dashboard
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Local development

**Backend**

```bash
pip install -e .
uvicorn xora_chart.main:app --host 0.0.0.0 --port 8030 --reload
```

**Worker** (optional — or just `POST /api/v1/cycles/run`)

```bash
XORA_API_BASE=http://localhost:8030 python -m xora_chart.worker
```

**Frontend**

```bash
cd frontend && npm install && npm run dev
```

---

## Phase status

| Phase | Scope | Status |
|-------|--------|--------|
| 1 | Educational catalog + React UI + Docker | ✅ Complete |
| 2 | Full pipeline structure, discovery, matcher skeleton, worker, opportunity API | ✅ Structure complete |
| 3 | Real similarity + AI validator + Opportunity Board UI | Pending |
| 4 | Persistence, learning loop, production hardening | Pending |

---

## Pattern library (seed)

Breakout/Retest, Breakdown/Retest, Head & Shoulders, Double Top/Bottom, Cup & Handle, Bull/Bear Flag, Bull/Bear Pennant.

Reference image folders live under `patterns/` (see `patterns/README.md`).

---

## License

Private — XORA / Xtinex
