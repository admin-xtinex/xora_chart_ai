"""Background worker that runs the scan pipeline on a fixed interval."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from xora_chart.application.pipeline import run_cycle
from xora_chart.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("xora_chart.worker")

_shutdown = asyncio.Event()


def _handle_signal(*_: object) -> None:
    log.info("Shutdown signal received")
    _shutdown.set()


async def main() -> None:
    cfg = load_config().get("cycle", {})
    interval = int(cfg.get("interval_seconds", 60))
    enabled = bool(cfg.get("enabled", True))

    if not enabled:
        log.warning("Cycle disabled in config — worker idle")
        await _shutdown.wait()
        return

    log.info("Worker started — interval=%ss", interval)

    while not _shutdown.is_set():
        try:
            result = await run_cycle()
            log.info(
                "Cycle complete: %d opportunities from %d symbols",
                len(result.opportunities),
                len(result.symbols_scanned),
            )
        except Exception:
            log.exception("Cycle crashed")

        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass

    log.info("Worker stopped")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
