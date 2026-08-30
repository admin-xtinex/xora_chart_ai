# XORA Chart AI — Google Cloud Free Tier Deployment

## Target

Use one Compute Engine `e2-micro` VM in an eligible Free Tier US region. This deployment keeps the Binance WebSocket backend and scan worker continuously running while exposing only Nginx on port 80.

## VM recommendations

- Machine type: `e2-micro`
- Region: an eligible Google Cloud Free Tier US region
- Boot disk: Standard persistent disk, sized within the current Free Tier allowance
- OS: Ubuntu 24.04 LTS
- Firewall: allow HTTP (80); add HTTPS (443) after a domain is attached
- Do not open ports 8030 or 3030 publicly

Always verify current Google Cloud Free Tier terms before creating resources.

## Install

```bash
git clone https://github.com/admin-xtinex/xora_chart_ai.git
cd xora_chart_ai
git checkout deploy/gcp-free-tier
sudo bash deploy/gcp/setup-vm.sh
```

If Docker group membership was added, sign out and back in once.

## Configure

```bash
cp .env.production.example .env.production
nano .env.production
```

Keep `XORA_TRADE_MODE=demo` until you explicitly intend otherwise.

## Deploy

```bash
bash deploy/gcp/deploy.sh
```

The production topology is:

```text
Internet :80
   |
   v
Nginx frontend
   |-- /        -> React static app
   |-- /api/*   -> backend:8030
   |-- /docs    -> backend:8030/docs

backend
   |-- FastAPI
   `-- Binance WebSocket hub

worker
   `-- POST http://backend:8030/api/v1/cycles/run
```

## Verify

```bash
curl http://127.0.0.1/api/v1/health
curl http://127.0.0.1/
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend worker
```

Then open the VM external IP in a browser.

## Update

```bash
git pull --ff-only
bash deploy/gcp/deploy.sh
```

## Security notes

- Only expose ports 80/443 at the VM firewall.
- Do not commit `.env.production`.
- Restrict FastAPI CORS before exposing authenticated/private features.
- Add HTTPS before sending sensitive credentials or enabling any real trading integration.
- Consider a domain plus Certbot/Nginx after initial HTTP deployment is verified.

## e2-micro memory strategy

The production Compose file caps containers at roughly 896 MB total and the setup script creates a 1 GB swap file. These are safeguards for a small VM, not guarantees. Watch memory during live scans:

```bash
free -h
docker stats
```

If the backend is repeatedly OOM-killed, reduce scan load or move to a larger VM.
