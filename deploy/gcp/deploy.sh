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

# The self-hosted runner user cannot normally traverse /etc/letsencrypt/live,
# while Docker can still mount it through the daemon. Use sudo only for the
# existence check so CI does not incorrectly redeploy the site as HTTP-only.
if sudo test -f "$TLS_CERT" && sudo test -f "$TLS_KEY"; then
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
echo "Backend readiness check (hybrid REST-history + WebSocket-live):"
for i in {1..24}; do
  if docker compose "${COMPOSE_ARGS[@]}" exec -T backend \
    python - <<'PY'
import json
import sys
import urllib.error
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8030/readyz", timeout=8) as response:
        data = json.load(response)
except urllib.error.HTTPError as exc:
    try:
        data = json.load(exc)
    except Exception:
        data = {"status": "degraded", "http_status": exc.code}
    print(json.dumps(data, indent=2))
    sys.exit(1)
except Exception as exc:
    print(f"readiness request failed: {exc}", file=sys.stderr)
    sys.exit(1)

print(json.dumps(data, indent=2))
ok = (
    data.get("ready") is True
    and data.get("transport") == "websocket-rpc"
    and data.get("market_data") == "binance-rest-history-websocket-live"
    and data.get("rest_market_data") is True
    and data.get("reference_gate") is True
    and data.get("reference_ready") is True
    and int(data.get("reference_images") or 0) >= 10
    and data.get("market_live") is True
    and data.get("ws_connected") is True
    and int(data.get("ws_tickers") or 0) > 0
)
if not ok:
    print("Backend has not reached production readiness yet", file=sys.stderr)
    sys.exit(1)
PY
  then
    if [[ "$TLS_ENABLED" == true ]]; then
      HOME_CODE="$(curl --silent --insecure --output /dev/null --write-out '%{http_code}' --max-time 10 \
        --resolve xora.xtinex.com:443:127.0.0.1 https://xora.xtinex.com/ || true)"
      CHARTS_CODE="$(curl --silent --insecure --output /dev/null --write-out '%{http_code}' --max-time 10 \
        --resolve xora.xtinex.com:443:127.0.0.1 https://xora.xtinex.com/charts || true)"
    else
      HOME_CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 http://127.0.0.1/ || true)"
      CHARTS_CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 http://127.0.0.1/charts || true)"
    fi
    if [[ "$HOME_CODE" == "200" && "$CHARTS_CODE" == "200" ]]; then
      echo "Backend ready and both landing + Charts AI routes are healthy."
      exit 0
    fi
    echo "Frontend warming: landing=$HOME_CODE charts=$CHARTS_CODE"
  fi
  sleep 5
done

echo "Production readiness check failed."
echo "Inspect logs with:"
printf 'docker compose'
printf ' %q' "${COMPOSE_ARGS[@]}"
echo ' logs --tail=200'
exit 1
