#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   sudo -u info RUNNER_TOKEN='<ephemeral token from GitHub>' \
#     bash deploy/gcp/setup-self-hosted-runner.sh
#
# The registration token is intentionally NOT stored in this repository.

REPO_URL="${REPO_URL:-https://github.com/admin-xtinex/xora_chart_ai}"
RUNNER_NAME="${RUNNER_NAME:-xora-gcp-prod}"
RUNNER_LABELS="${RUNNER_LABELS:-xora-gcp,gcp,production}"
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"
RUNNER_VERSION="${RUNNER_VERSION:-2.335.1}"

if [[ -z "${RUNNER_TOKEN:-}" ]]; then
  echo "RUNNER_TOKEN is required. Generate it in GitHub: Settings > Actions > Runners > New self-hosted runner." >&2
  exit 1
fi

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this script as the normal VM user (info), not root." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y ca-certificates curl tar gzip libicu-dev

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

if [[ ! -x ./config.sh ]]; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) PKG_ARCH="x64" ;;
    aarch64|arm64) PKG_ARCH="arm64" ;;
    *) echo "Unsupported runner architecture: $ARCH" >&2; exit 1 ;;
  esac

  PACKAGE="actions-runner-linux-${PKG_ARCH}-${RUNNER_VERSION}.tar.gz"
  curl -fL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${PACKAGE}" -o "$PACKAGE"
  tar xzf "$PACKAGE"
  rm -f "$PACKAGE"
fi

# Reconfiguration is blocked if an existing runner is already registered.
if [[ -f .runner ]]; then
  echo "Runner is already configured in $RUNNER_DIR"
else
  ./config.sh \
    --url "$REPO_URL" \
    --token "$RUNNER_TOKEN" \
    --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABELS" \
    --work _work \
    --unattended \
    --replace
fi

sudo ./svc.sh install "$USER" || true
sudo ./svc.sh start
sudo ./svc.sh status

echo
printf 'Self-hosted runner ready: %s labels=%s\n' "$RUNNER_NAME" "$RUNNER_LABELS"
echo "Verify in GitHub: Settings > Actions > Runners"
