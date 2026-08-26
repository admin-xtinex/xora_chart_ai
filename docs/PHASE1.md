# XORA Chart AI — Phase 1

**Status: COMPLETE**  
**Date:** 2026-08-26  
**Repo:** `admin-xtinex/xora_chart_ai`

---

## Goal of Phase 1

Establish the foundational identity, knowledge base, UI, and integration contract for Chart Pattern AI so that:

1. The 10 reference educational cards are turned into structured, queryable data.
2. A clean FastAPI surface exists for pattern education (port **8030**).
3. A polished React frontend lets users browse every pattern + reference image.
4. Everything is dockerised (`docker compose up --build`).
5. A module skeleton is ready to plug into `xora_trade_ai` as the `chart_pattern` analyzer.

---

## Deliverables Checklist

| # | Item | Status |
|---|------|--------|
| 1 | Project README with clear product boundary | ✅ |
| 2 | Full pattern catalog (10 patterns) extracted from reference images | ✅ |
| 3 | Structured JSON + Python data model for every pattern | ✅ |
| 4 | FastAPI service on **port 8030** (`/api/v1/patterns`, health, static references) | ✅ |
| 5 | React + Vite + Tailwind frontend (pattern browser + detail view) | ✅ |
| 6 | Docker + docker-compose (backend :8030, frontend :3030) | ✅ |
| 7 | Module contract skeleton matching `xora_trade_ai` Analyzer protocol | ✅ |
| 8 | This Phase 1 document | ✅ |

---

## Ports

| Service | Host port | Container |
|---------|-----------|-----------|
| Backend API | **8030** | 8030 |
| Frontend UI | **3030** | 80 (nginx) |

8000 is intentionally avoided (commonly used by other XORA services).

---

## Architecture (Phase 1)

```
+------------------ Frontend -----------------+
|  React (Vite) + Tailwind                    |
|  Pattern list · filters · detail · images   |
|  Port 3030                                  |
+-------------------- API --------------------+
|  FastAPI  /api/v1/patterns                  |
|  Static /references/* (chart_reference PNGs)|
|  Port 8030                                  |
+--------------- Application -----------------+
|  PatternCatalog service                     |
+---------------- Domain ---------------------+
|  Pattern, TradingSetup, Direction enums     |
+------------- Infrastructure ----------------+
|  Static JSON catalog (data/patterns.json)   |
+---------------------------------------------+
```

No database, no market data, no worker yet.

---

## Pattern Inventory

| Key | Name | Bias | Type |
|-----|------|------|------|
| `breakout_retest` | Breakout + Retest | Bullish | Continuation |
| `breakdown_retest` | Breakdown + Retest | Bearish | Continuation |
| `head_and_shoulders` | Head and Shoulders | Bearish | Reversal |
| `double_top` | Double Top | Bearish | Reversal |
| `double_bottom` | Double Bottom | Bullish | Reversal |
| `cup_and_handle` | Cup and Handle | Bullish | Continuation |
| `bull_flag` | Bull Flag | Bullish | Continuation |
| `bear_flag` | Bear Flag | Bearish | Continuation |
| `bull_pennant` | Bull Pennant | Bullish | Continuation |
| `bear_pennant` | Bear Pennant | Bearish | Continuation |

---

## Run

```bash
docker compose up --build
```

- UI → http://localhost:3030  
- API → http://localhost:8030  
- Docs → http://localhost:8030/docs

---

## What is out of scope for Phase 1

- Geometric pattern detection on OHLCV
- Vision model (image → pattern)
- LLM explanation generation
- Live market data connection
- PostgreSQL / persistence
- Worker / scheduling
- Any trading or prediction logic

These belong to **Phase 2** (Detection) and **Phase 3** (Vision + LLM).

---

## Completion Statement

Phase 1 is **complete**: catalog, backend (8030), frontend, Docker, and module skeleton are all in place.

**Next:** Phase 2 — Geometric Pattern Detector + FeatureResult generation for `xora_trade_ai`.
