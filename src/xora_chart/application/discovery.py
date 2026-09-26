from __future__ import annotations

from xora_chart.config import load_config
from xora_chart.domain.models import DiscoveredCoin
from xora_chart.services import binance


def configured_scan_limit() -> int:
    cfg = load_config().get("discovery", {})
    cohort_total = sum(
        max(0, int(cfg.get(key, 10)))
        for key in ("top_gainers", "top_losers", "trending", "top_volume")
    )
    return max(1, min(int(cfg.get("scan_limit", cohort_total or 40)), cohort_total or 40))


async def run_discovery() -> list[DiscoveredCoin]:
    cfg = load_config().get("discovery", {})
    coins = await binance.discover_coins(
        top_gainers=int(cfg.get("top_gainers", 10)),
        top_losers=int(cfg.get("top_losers", 10)),
        top_volume=int(cfg.get("top_volume", 10)),
        trending=int(cfg.get("trending", 10)),
        quote_asset=cfg.get("quote_asset", "USDT"),
        min_quote_volume=float(cfg.get("min_quote_volume", 500_000)),
    )
    # Four globally unique cohorts, capped by the configured total scan limit.
    return coins[:configured_scan_limit()]
