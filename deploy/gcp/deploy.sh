#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env.production ]]; then
  cp .env.production.example .env.production
  echo "Created .env.production from example. Review it before production trading use."
fi

set -a
source .env.production
set +a

COMPOSE_ARGS=(--env-file .env.production -f docker-compose.prod.yml)
TLS_CERT="/etc/letsencrypt/live/xora.xtinex.com/fullchain.pem"
TLS_KEY="/etc/letsencrypt/live/xora.xtinex.com/privkey.pem"
TLS_ENABLED=false

if [[ -f "$TLS_CERT" && -f "$TLS_KEY" ]]; then
  COMPOSE_ARGS+=(-f docker-compose.tls.yml)
  TLS_ENABLED=true
  echo "TLS certificate detected; enabling HTTPS for xora.xtinex.com."
else
  echo "TLS certificate not present; deploying HTTP-only."
fi

docker compose "${COMPOSE_ARGS[@]}" build --pull
docker compose "${COMPOSE_ARGS[@]}" up -d --remove-orphans

echo
echo "Deployment status:"
docker compose "${COMPOSE_ARGS[@]}" ps

echo
echo "WebSocket health check:"
for i in {1..18}; do
  if docker compose "${COMPOSE_ARGS[@]}" exec -T backend \
    python - <<'PY'
import asyncio
import json
import sys
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8030/ws", open_timeout=5) as ws:
        await ws.recv()  # ready frame
        await ws.send(json.dumps({"id": "deploy-health", "action": "health", "payload": {}}))
        msg = json.loads(await ws.recv())
        data = msg.get("data") or {}
        ticker_count = int(data.get("ws_tickers") or 0)
        last_age = data.get("ws_last_message_age_seconds")
        market_live = (
            data.get("ws_connected") is True
            and ticker_count > 0
            and last_age is not None
            and float(last_age) < 30.0
        )
        ok = (
            msg.get("ok") is True
            and data.get("transport") == "websocket-only"
            and data.get("market_data") == "binance-websocket-only"
            and data.get("rest_market_data") is False
            and data.get("reference_gate") is True
            and int(data.get("reference_images") or 0) >= 10
            and market_live
        )
        print(json.dumps(data, indent=2))
        if not ok:
            print(
                f"Market data is not healthy: connected={data.get('ws_connected')} "
                f"tickers={ticker_count} last_age={last_age}",
                file=sys.stderr,
            )
            sys.exit(1)

asyncio.run(main())
PY
  then
    if [[ "$TLS_ENABLED" == true ]]; then
      HOME_CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 https://127.0.0.1/ --resolve xora.xtinex.com:443:127.0.0.1 -H 'Host: xora.xtinex.com' || true)"
    else
      HOME_CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 http://127.0.0.1/ || true)"
    fi
    if [[ "$HOME_CODE" == "200" ]]; then
      echo "Backend market WebSocket and frontend are healthy."
      exit 0
    fi
  fi
  sleep 5
done

echo "Production health check failed: frontend may be serving, but live market data is not usable."
echo "Inspect logs with:"
printf 'docker compose'
printf ' %q' "${COMPOSE_ARGS[@]}"
echo ' logs --tail=200'
exit 1
