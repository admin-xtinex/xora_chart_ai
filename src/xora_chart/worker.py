"""Background worker — triggers scan cycles on the API process so results share the same in-memory store."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

import httpx

from xora_chart.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("xora_chart.worker")

_shutdown = asyncio.Event()

API_BASE = os.getenv("XORA_API_BASE", "http://backend:8030")


def _handle_signal(*_: object) -> None:
    log.info("Shutdown signal received")
    _shutdown.set()


async def trigger_cycle() -> dict:
    url = f"{API_BASE}/api/v1/cycles/run"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url)
        r.raise_for_status()
        return r.json()


async def _loop() -> None:
    cfg = load_config().get("cycle", {})
    interval = int(cfg.get("interval_seconds", 60))
    enabled = bool(cfg.get("enabled", True))

    if not enabled:
        log.warning("Cycle disabled in config — worker idle")
        await _shutdown.wait()
        return

    log.info("Worker started — API=%s interval=%ss", API_BASE, interval)

    # small delay so API is fully up
    await asyncio.sleep(5)

    while not _shutdown.is_set():
        try:
            data = await trigger_cycle()
            opps = data.get("opportunities") or []
            scanned = data.get("symbols_scanned") or []
            log.info(
                "Cycle %s — opportunities=%d scanned=%d",
                data.get("cycle_id"),
                len(opps),
                len(scanned),
            )
        except Exception:
            log.exception("Cycle trigger failed")

        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass

    log.info("Worker stopped")


def main() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    try:
        asyncio.run(_loop())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
