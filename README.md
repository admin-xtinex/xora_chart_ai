# XORA Chart AI

API-first live chart-pattern scanner for Binance Futures.

**Clients:** Web dashboard · future Android (same `/api/v1` JSON)

---

## Engines

| Engine | Role |
|--------|------|
| **Analysis** | Volume, order book, funding, OI, volatility, regime |
| **Decision** | APPROVE / WAIT / REJECT + confirmations + entry/SL/TP |
| **Trade** | Demo positions (default), sizing, leverage caps |

```
Pattern match → Analysis → Decision → Trade (optional) → API
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Quick start

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3030 |
| API | http://localhost:8030 |
| Docs | http://localhost:8030/docs |

```bash
# Scan
curl -X POST http://localhost:8030/api/v1/cycles/run

# Opportunities (includes market_analysis + decision)
curl http://localhost:8030/api/v1/opportunities

# Open demo trade from approved opportunity
curl -X POST http://localhost:8030/api/v1/positions \
  -H 'Content-Type: application/json' \
  -d '{"opportunity_id":"<id>"}'
```

Trade mode: `XORA_TRADE_MODE=demo` (default). Live is disabled until explicitly enabled.

---

## Phase status

| Phase | Scope | Status |
|-------|--------|--------|
| 1 | Catalog + UI | ✅ |
| 2 | Scanner + charts + overlays | ✅ |
| 3 | Analysis · Decision · Trade engines | ✅ Foundation |
| 4 | Persist store, multi-TF, live adapter, Android | Planned |
