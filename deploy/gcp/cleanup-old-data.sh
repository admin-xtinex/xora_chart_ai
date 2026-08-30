#!/usr/bin/env bash
set -euo pipefail

# Conservative cleanup for the small GCP VM.
# NEVER prunes Docker volumes, XORA state, or the persisted WS candle cache.

LOCK=/var/lock/xora-cleanup.lock
exec 9>"$LOCK"
flock -n 9 || exit 0

log() { printf '[xora-cleanup] %s\n' "$*"; }

log "starting"

# Avoid interfering with an active GitHub Actions job.
if pgrep -f 'Runner.Worker' >/dev/null 2>&1; then
  log "GitHub Actions job active; skipping Docker/runner workspace cleanup"
else
  if command -v docker >/dev/null 2>&1; then
    # Disposable resources only. Volumes are intentionally untouched.
    docker container prune -f --filter 'until=168h' || true
    docker image prune -af --filter 'until=168h' || true
    docker builder prune -af --filter 'until=168h' || true
    docker network prune -f --filter 'until=168h' || true
  fi

  RUNNER_DIR="${RUNNER_DIR:-/home/info/actions-runner}"
  if [[ -d "$RUNNER_DIR/_work/_temp" ]]; then
    find "$RUNNER_DIR/_work/_temp" -mindepth 1 -mtime +2 -delete || true
  fi
  if [[ -d "$RUNNER_DIR/_diag" ]]; then
    find "$RUNNER_DIR/_diag" -type f -mtime +14 -delete || true
  fi
fi

# Bound system logs and package cache without touching app state.
if command -v journalctl >/dev/null 2>&1; then
  journalctl --vacuum-time=7d >/dev/null 2>&1 || true
fi
apt-get clean >/dev/null 2>&1 || true

# Truncate oversized Docker JSON logs in-place; keep current containers alive.
find /var/lib/docker/containers -name '*-json.log' -type f -size +100M -exec truncate -s 0 {} \; 2>/dev/null || true

log "finished"
