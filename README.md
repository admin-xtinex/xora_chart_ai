# XORA Chart AI

API-first live chart-pattern scanner for Binance Futures.

**Clients:** Web dashboard · **Android app** (same `/api/v1` JSON)  
**Market data:** Binance **WebSocket only** (no REST)

---

## Engines

| Engine | Role |
|--------|------|
| **Analysis** | Volume, order book, funding, volatility, regime |
| **Decision** | APPROVE / WAIT / REJECT + confirmations + levels |
| **Trade** | Demo positions, sizing, leverage caps, auto-trade |

```
WS hub → Discovery → Pattern match → Analysis → Decision → Trade (optional) → API
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Quick start (Docker)

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3030 |
| API | http://localhost:8030 |
| Docs | http://localhost:8030/docs |

First scan may need a short **WS warm-up** while candle buffers fill.

---

## Android APK

Project: [`android/`](android/)

**CI:** Actions workflow builds debug APK and uploads artifact **`xora-chart-ai-debug-apk`**.

- Trigger: push to `main` (android paths) or manual **Run workflow**
- Download: GitHub → Actions → run → Artifacts

Default API in emulator: `http://10.0.2.2:8030` (editable in-app).

---

## API highlights

```bash
curl -X POST http://localhost:8030/api/v1/cycles/run
curl http://localhost:8030/api/v1/opportunities
curl -X PATCH http://localhost:8030/api/v1/settings -H 'Content-Type: application/json' -d '{"auto_trade":true}'
curl http://localhost:8030/api/v1/positions/history/summary
```

Trade mode: `XORA_TRADE_MODE=demo` (default).
