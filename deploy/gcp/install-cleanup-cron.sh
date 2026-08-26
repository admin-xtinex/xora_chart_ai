#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run with sudo: sudo bash deploy/gcp/install-cleanup-cron.sh" >&2
  exit 1
fi

REPO_DIR="${REPO_DIR:-/home/info/xora_chart_ai}"
SCRIPT="$REPO_DIR/deploy/gcp/cleanup-old-data.sh"

if [[ ! -f "$SCRIPT" ]]; then
  echo "Cleanup script not found: $SCRIPT" >&2
  exit 1
fi

chmod +x "$SCRIPT"
install -d -m 0755 /var/log/xora

cat >/etc/cron.d/xora-cleanup <<EOF
# XORA VM cleanup: daily at 03:20 server local time.
# Persistent Docker volumes and XORA WebSocket/state data are never pruned.
20 3 * * * root $SCRIPT >> /var/log/xora/cleanup.log 2>&1
EOF
chmod 0644 /etc/cron.d/xora-cleanup

if command -v systemctl >/dev/null 2>&1; then
  systemctl enable --now cron
fi

echo "Installed /etc/cron.d/xora-cleanup"
cat /etc/cron.d/xora-cleanup
