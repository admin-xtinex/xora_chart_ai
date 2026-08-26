# XORA Chart AI — Target Architecture

**Status:** Pipeline structure expanded (Phase 2 foundation)  
**Date:** 2026-08-26

---

## Core Concept

The system continuously scans **Binance Futures**, identifies the best opportunities, compares them against a curated library of known winning chart patterns, and presents only the highest-probability trades.

- User does **not** upload charts.
- System scans automatically every cycle.

---

## Overall Flow

```
Scheduler (every 1 minute)
        │
        ▼
Discovery Service          → 20 coins (gainers / losers / volume / trending)
        │
        ▼
Market Data Service        → 100 × 1m candles per coin
        │
        ▼
Normalize Candles
        │
        ▼
Pattern Matcher            → similarity vs Pattern Repository
        │
        ▼
Rank Matches
        │
        ▼
AI Validator               → only if similarity ≥ threshold (e.g. 80%)
        │
        ▼
Trade Generator            → Entry / SL / TP1-3 / RR / confidence
        │
        ▼
Ranking Engine             → top opportunities only
        │
        ▼
Store Results
        │
        ▼
API  →  Web Dashboard (Opportunity Board)
```

---

## Services

| Service | Responsibility |
|---------|----------------|
| **Scheduler / Worker** | Runs the full cycle on a fixed interval |
| **Discovery** | Top gainers (5) + losers (5) + volume movers (5) + trending (5) → 20 symbols |
| **Market Data** | Fetch OHLCV from Binance Futures |
| **Pattern Repository** | Curated reference patterns + example charts |
| **Similarity Engine** | Deterministic match scores (not LLM-first) |
| **AI Validator** | Confirm / reject high-similarity candidates |
| **Trade Generator** | Entry, SL, targets, RR, confidence |
| **Ranking Engine** | Order opportunities by quality |
| **API** | Read models for dashboard |
| **Frontend** | Opportunity board + detail view |

---

## Why this order

- **Lower AI cost** — AI only runs on strong matches
- **Consistency** — same chart → same reference matches
- **Explainability** — every setup points to a concrete reference example
- **Scalability** — add strategies by adding reference patterns, not rewriting prompts
- **Continuous** — platform surfaces opportunities; user does not upload

---

## Folder layout (target)

```
xora_chart_ai/
  config/
    default.yaml
    patterns.yaml
  data/
    patterns.json              # educational catalog (Phase 1)
  patterns/                    # reference image repository
    bull_flag/
    bear_flag/
    ...
  chart_reference/             # original educational cards (kept)
  src/xora_chart/
    main.py                    # FastAPI process
    worker.py                  # scheduler / cycle runner
    domain/
      models.py
      enums.py
    application/
      pipeline.py              # orchestrates one full cycle
      discovery.py
      market_data.py
      matcher.py
      validator.py
      trade_generator.py
      ranking.py
    services/
      binance.py
    persistence/
      store.py
    api/
      v1.py
    catalog.py                 # Phase 1 catalog loader
    modules/
  frontend/
  docs/
```

---

## Phase map

| Phase | Scope |
|-------|--------|
| **1** | Educational catalog + React UI + Docker (done) |
| **2** | Pipeline structure, Discovery, Market Data, Matcher skeleton, Opportunity API, Worker |
| **3** | Real similarity engine + AI Validator + Trade Generator quality |
| **4** | Pattern Repository management, learning loop, production hardening |
