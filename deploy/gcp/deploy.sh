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

docker compose --env-file .env.production -f docker-compose.prod.yml build --pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --remove-orphans

echo
echo "Deployment status:"
docker compose --env-file .env.production -f docker-compose.prod.yml ps

echo
echo "Health check:"
for i in {1..12}; do
  if curl -fsS http://127.0.0.1/api/v1/health >/dev/null; then
    curl -fsS http://127.0.0.1/api/v1/health
    echo
    exit 0
  fi
  sleep 5
done

echo "Health check did not become ready. Inspect logs with:"
echo "docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200"
exit 1
