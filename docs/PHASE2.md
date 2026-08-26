# XORA Chart AI — Phase 2

**Status:** Pipeline + Opportunity Board + geometric matcher + AI validation  
**Date:** 2026-08-26

---

## Delivered

| Component | Status |
|-----------|--------|
| Discovery + market data + ranking + worker | ✅ |
| **Geometric similarity engine** (per-pattern detectors) | ✅ |
| **AI validation** (LLM if key present, else rule-based) | ✅ |
| **Opportunity Board** (React) | ✅ |
| Pattern Library tab retained | ✅ |
| Docker: backend + worker + frontend | ✅ |

---

## Similarity engine

Dedicated detectors for:

- Bull / Bear Flag  
- Bull / Bear Pennant  
- Double Top / Bottom  
- Head & Shoulders  
- Breakout + Retest / Breakdown + Retest  
- Cup & Handle  

Each returns a 0–100 score plus feature breakdown (impulse, converge, retest, etc.).

---

## AI validation

1. Similarity ≥ `matcher.ai_threshold` (default 70)  
2. If `ai.enabled` and `OPENAI_API_KEY` (or `XORA_AI_API_KEY`) → OpenAI-compatible chat completion  
3. Else → structured rule-based checks (direction alignment, feature quality)  

---

## Frontend

- **Opportunities** tab — ranked live setups, Run scan, detail (levels, AI reason, matches, reference image)  
- **Pattern Library** tab — educational catalog  

---

## Run

```bash
docker compose up --build
# UI http://localhost:3030
# Scan: button in UI or POST /api/v1/cycles/run
```

Optional LLM:

```bash
export OPENAI_API_KEY=sk-...
# rebuild / restart backend
```
