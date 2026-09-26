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

Discovery scans four globally unique cohorts of 10 coins each: gainers,
losers, momentum movers, and high-volume candidates (40 total when available).

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
New demo positions use a fixed **10 USDT margin at 10x leverage** (100 USDT notional).
The current B1 deployment cap is **20 concurrent demo positions**, configurable
with `XORA_MAX_OPEN_POSITIONS`.

## Optional LLM explanations

Opportunity explanations can use Groq first and automatically fall back to
Gemini when Groq is unavailable or rate-limited. The LLM is read-only: the
deterministic Decision and Trade engines remain the only execution gate.

```bash
XORA_LLM_ENABLED=true
XORA_LLM_PROVIDERS=groq,gemini
GROQ_API_KEY=...
GEMINI_API_KEY=...
```

Keys belong on the backend only. Explanations are requested on demand through
the WebSocket action `opportunity.explain`, cached for 15 minutes by default,
and limited to five uncached requests per client per minute.

## Sign-in and users

The dashboard (`/charts`) requires a login; the landing page stays public.
Every WebSocket action except `auth.login`/`auth.resume` needs a signed-in user,
and user management plus global trade settings are admin-only.

- The first admin is created on startup from `XORA_ADMIN_USERNAME` /
  `XORA_ADMIN_PASSWORD` when no users exist. On Azure,
  `deploy/azure/setup-custom-domain.ps1` prompts for them; afterwards run it
  with `-RemoveBootstrapPassword`.
- Admins add users, reset passwords and delete users under **Settings → Users**.
- Passwords are salted scrypt hashes; sessions last 7 days and survive restarts;
  5 failed logins lock an account for 5 minutes.
