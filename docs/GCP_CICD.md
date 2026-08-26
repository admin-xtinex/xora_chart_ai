# GCP GitHub Actions Deployment

This workflow deploys XORA Chart AI to the production Compute Engine VM whenever `main` changes, and can also be run manually.

## One-time VM preparation

SSH to the VM and run the bootstrap script once:

```bash
gcloud compute ssh xora-chart-ai --zone=us-central1-a
curl -fsSL https://raw.githubusercontent.com/admin-xtinex/xora_chart_ai/main/deploy/gcp/setup-vm.sh | bash
```

Then create an SSH key pair for GitHub Actions on your local machine or in Cloud Shell:

```bash
ssh-keygen -t ed25519 -C "github-actions-xora" -f ~/.ssh/xora_github_actions -N ""
```

Add the public key to the VM user's `~/.ssh/authorized_keys`:

```bash
cat ~/.ssh/xora_github_actions.pub
```

Copy that single public-key line, SSH to the VM, and append it to `~/.ssh/authorized_keys` for the deployment user.

## GitHub Actions secrets

Repository: **Settings → Secrets and variables → Actions → New repository secret**.

Required secrets:

- `GCP_VM_HOST` — public VM IP or DNS name. Current initial VM IP: `35.209.66.225`.
- `GCP_VM_USER` — Linux user that owns/runs the deployment.
- `GCP_SSH_PRIVATE_KEY` — complete contents of `~/.ssh/xora_github_actions` including BEGIN/END lines.

Optional:

- `GCP_DEPLOY_PATH` — path under the remote user's home, default `xora_chart_ai`. An absolute path is also accepted.

Do **not** commit the private key or `.env.production`.

## First deployment

After the secrets are configured, open **Actions → Deploy to Google Cloud VM → Run workflow**.

The workflow will:

1. validate deployment secrets;
2. establish SSH to the VM;
3. clone the repository on first use or reset it to `origin/main`;
4. create `.env.production` from the safe example if missing;
5. build and restart `docker-compose.prod.yml`;
6. run the internal health check from `deploy/gcp/deploy.sh`;
7. verify the public `/api/v1/health` endpoint.

## Production environment

The real `.env.production` stays on the VM and is not overwritten by later deployments. Edit it directly on the VM when production settings or secrets are required.

Trade mode remains `demo` by default. Do not enable live trading until credentials, risk limits, authentication, and monitoring are intentionally configured.
