# XORA Chart AI — Phase 1

**Status: COMPLETE**  
**Date:** 2026-08-26  
**Repo:** `admin-xtinex/xora_chart_ai`

---

## Goal of Phase 1

Establish the foundational identity, knowledge base, and integration contract for Chart Pattern AI so that:

1. The 10 reference educational cards are turned into structured, queryable data.
2. A clean FastAPI surface exists for pattern education.
3. A module skeleton is ready to plug into `xora_trade_ai` as the `chart_pattern` analyzer (currently listed as future in trade_ai Phase 1).
4. No detection / vision / LLM logic is required yet — that is Phase 2+.

Phase 1 deliberately stays lightweight and documentation-first, following the same discipline used in `xora_trade_ai`.

---

## Deliverables Checklist

| # | Item | Status |
|---|------|--------|
| 1 | Project README with clear product boundary | ✅ |
| 2 | Full pattern catalog (10 patterns) extracted from reference images | ✅ |
| 3 | Structured JSON + Python data model for every pattern | ✅ |
| 4 | FastAPI service (`/api/v1/patterns`, `/patterns/{id}`) | ✅ |
| 5 | Module contract skeleton matching `xora_trade_ai` Analyzer protocol | ✅ |
| 6 | Folder structure aligned with future growth | ✅ |
| 7 | pyproject.toml + basic package | ✅ |
| 8 | This Phase 1 document | ✅ |

---

## Architecture (Phase 1)

```
+------------------ API -------------------+
|  FastAPI  /api/v1/patterns               |
+--------------- Application --------------+
|  PatternCatalog service                  |
+---------------- Domain ------------------+
|  Pattern, TradingSetup, Direction enums  |
+------------- Infrastructure -------------+
|  Static JSON catalog (patterns.json)     |
+------------------------------------------+
```

No database, no market data, no worker yet.

The only runtime dependency is FastAPI + the static catalog.

---

## Pattern Inventory (from chart_reference/)

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

Each entry contains:

- overview
- characteristics (list)
- trading_setup (entry / stop_loss / target)
- key_points
- volume_behaviour
- example steps

---

## Integration Contract (for xora_trade_ai)

Future module location (Phase 2):

```
src/xora_chart/modules/chart_pattern/
    __init__.py
    module.py          # implements Analyzer protocol
```

Expected interface (copied from trade_ai):

```python
class Analyzer(Protocol):
    key: str
    version: str

    def analyze(self, snapshot: MarketSnapshot, config: ModuleConfig) -> FeatureResult:
        ...
```

Phase 1 only ships the empty package + a note that detection arrives in Phase 2.

---

## What is explicitly out of scope for Phase 1

- Geometric pattern detection on OHLCV
- Vision model (image → pattern)
- LLM explanation generation
- Live market data connection
- PostgreSQL / persistence
- Worker / scheduling
- Any trading or prediction logic

These belong to Phase 2 (Detection) and Phase 3 (Vision + LLM).

---

## Completion Statement

Phase 1 is considered **complete** when:

- All 10 patterns are structured and queryable via the API
- The README and this document accurately describe the system
- The module skeleton exists and matches the trade_ai contract
- The repository is no longer an empty image dump

All of the above are true as of this commit.

**Next:** Phase 2 — Geometric Pattern Detector + FeatureResult generation.
