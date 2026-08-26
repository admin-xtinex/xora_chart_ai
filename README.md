# XORA Chart AI

**Chart Pattern Recognition & Educational Intelligence** for the XORA Prediction Platform.

This service provides:

- Structured knowledge of classic price-action patterns
- Educational reference cards (the images in `chart_reference/`)
- A pluggable `chart_pattern` feature module compatible with `xora_trade_ai`
- Future vision / LLM pattern detection (Phase 2+)

It never executes trades. It only produces pattern features and explanations that the Prediction AI can consume.

---

## Phase 1 Status: **COMPLETE**

See [`docs/PHASE1.md`](docs/PHASE1.md) for the full definition and completion checklist.

### What Phase 1 delivers

| Deliverable | Status |
|-------------|--------|
| Project scaffolding & identity | ✅ |
| Complete pattern catalog (10 patterns) | ✅ |
| Structured pattern data (JSON + Python) | ✅ |
| FastAPI service (list / get patterns) | ✅ |
| Module contract skeleton for `xora_trade_ai` | ✅ |
| Documentation & architecture alignment | ✅ |

---

## Quick start

```bash
git clone https://github.com/admin-xtinex/xora_chart_ai.git
cd xora_chart_ai
pip install -e .
uvicorn src.xora_chart.main:app --reload
```

- API docs: http://localhost:8000/docs
- Patterns: http://localhost:8000/api/v1/patterns

---

## Pattern Library (Phase 1)

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

All patterns include Overview, Characteristics, Trading Setup (Entry / SL / Target), Key Points, and volume behaviour — matching the reference images in `chart_reference/`.

---

## Integration with xora_trade_ai

This repo will later export a drop-in module:

```
xora.modules.chart_pattern
```

that implements the exact `Analyzer` protocol defined in `xora_trade_ai`:

```python
def analyze(self, snapshot: MarketSnapshot, config: ModuleConfig) -> FeatureResult
```

Phase 1 only provides the skeleton + catalog. Detection logic (geometric + vision) lands in Phase 2.

---

## License

Private — XORA / Xtinex
