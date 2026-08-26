# XORA Chart AI — Architecture

**Version:** 0.3 · Engine layer  
**Clients:** Web dashboard (now) · Android / any mobile (same REST API)

---

## Design goals

1. **API-first** — all features exposed via stable `/api/v1/*` JSON. Web and Android share contracts.
2. **Engine separation** — Analysis ≠ Decision ≠ Trade. No engine owns another’s job.
3. **Pluggable execution** — Trade Engine demo today, live adapter later, same interface.
4. **Scan pipeline is orchestration only** — business logic lives in engines/domain.
5. **Forward-compatible** — auth, push notifications, multi-account can slot in without rewrite.

---

## High-level flow

```
Scheduler / POST /cycles/run
        │
        ▼
Discovery → Market Data → Pattern Matcher
        │
        ▼
┌───────────────────┐
│  Analysis Engine  │  volume, OI, funding, book, volatility, regime
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Decision Engine  │  WAIT / APPROVE / REJECT · confirmations · levels
└─────────┬─────────┘
          ▼
┌───────────────────┐
│   Trade Engine    │  demo (default) | live · size · leverage · orders
└─────────┬─────────┘
          ▼
Store → REST API → Web / Android
```

---

## Package layout

```
src/xora_chart/
  domain/           # pure models + enums (API contract source of truth)
  engines/
    analysis/       # Analysis Engine
    decision/       # Decision Engine
    trade/          # Trade Engine (demo + live interface)
  application/      # pipeline orchestration, discovery, matcher, explainer
  services/         # Binance & external I/O
  persistence/      # Store abstraction (memory now → Redis/Postgres later)
  api/v1.py         # versioned REST — mobile-safe
```

---

## Engines

### Analysis Engine
- **In:** CandleWindow, PatternMatch
- **Out:** `MarketAnalysis` (scores, signals, regime, bias)
- **Does not:** place trades or set entry/SL

### Decision Engine
- **In:** CandleWindow, PatternMatch, MarketAnalysis
- **Out:** `TradeDecision` (APPROVE | WAIT | REJECT, setup, confirmations)
- **Owns:** confirmation rules, structure-based levels, min RR

### Trade Engine
- **In:** approved TradeDecision / TradeSetup
- **Out:** `Position` / order results
- **Modes:** `demo` (default) | `live`
- **Owns:** sizing, leverage caps, margin checks, fill simulation

---

## API surface (shared by Web + Android)

| Method | Path | Purpose |
|--------|------|--------|
| GET | `/api/v1/health` | Liveness + cache stats |
| GET | `/api/v1/opportunities` | Ranked opportunities |
| GET | `/api/v1/opportunities/{id}` | Full detail + analysis + decision |
| POST | `/api/v1/cycles/run` | Trigger scan |
| GET | `/api/v1/positions` | Open positions (demo/live) |
| POST | `/api/v1/positions` | Execute approved setup (demo/live) |
| POST | `/api/v1/positions/{id}/close` | Close position |
| GET | `/api/v1/patterns` | Educational catalog |

All responses are plain JSON, no HTML. Auth (JWT/API key) can wrap the same routes later.

---

## Future upgrades (planned slots)

| Feature | How it fits |
|---------|-------------|
| Android app | Consume `/api/v1` only; push via FCM using opportunity events |
| Auth / multi-user | Middleware + user-scoped store |
| Redis / Postgres | Swap `persistence.Store` implementation |
| Live trading | `TradeEngine` live adapter + secrets |
| Multi-TF | Analysis Engine signal + Decision filter |
| Alerts | Event bus after Decision APPROVE |
| Outcome learning | Persist decision→fill→PnL; pattern stats job |

---

## Config

`config/default.yaml` sections: `cycle`, `discovery`, `market_data`, `matcher`, `analysis`, `decision`, `trade`, `ranking`, `ai`, `store`.

Trade mode: `trade.mode: demo | live` (env `XORA_TRADE_MODE` overrides).
