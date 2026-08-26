# XORA Chart AI — Phase 2 (Pipeline Foundation)

**Status:** Structure complete — runnable end-to-end cycle  
**Date:** 2026-08-26

---

## What Phase 2 delivers

| Component | Status |
|-----------|--------|
| Full folder / service architecture | ✅ |
| Config (`config/default.yaml`, `patterns.yaml`) | ✅ |
| Domain models (Candle, Opportunity, TradeLevels, …) | ✅ |
| Discovery (Binance Futures gainers/losers/volume/trending) | ✅ |
| Market data (100 × 1m klines) | ✅ |
| Pattern matcher (heuristic skeleton) | ✅ |
| AI validator (placeholder, threshold-gated) | ✅ |
| Trade generator (entry / SL / TP1-3 / RR) | ✅ |
| Ranking engine | ✅ |
| In-memory store + cycle history | ✅ |
| Worker scheduler (calls API every 60s) | ✅ |
| API: `/opportunities`, `/cycles`, `POST /cycles/run` | ✅ |
| Docker: backend + worker + frontend | ✅ |
| Pattern repository folders | ✅ |

---

## How to run a cycle

```bash
# Full stack
docker compose up --build

# Or manually trigger one scan
curl -X POST http://localhost:8030/api/v1/cycles/run

# List ranked opportunities
curl http://localhost:8030/api/v1/opportunities
```

---

## Known Phase 2 limitations (intentional)

1. **Matcher is heuristic**, not vision/embedding similarity yet.
2. **AI validator is off** by default (`ai.enabled: false`).
3. **Store is in-memory** (resets on API restart). Redis/Postgres in Phase 3/4.
4. **Frontend** still shows the educational catalog; Opportunity Board UI is next.
5. **Reference image matching** not wired — `patterns/` folders are ready for examples.

---

## Next (Phase 2b / 3)

1. Opportunity Board on the React frontend
2. Real similarity engine (shape features or embeddings)
3. Enable AI validator for matches ≥ 80%
4. Persist cycles/opportunities
5. Grow `patterns/*/exampleN.png` library
