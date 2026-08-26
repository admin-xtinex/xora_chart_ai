from __future__ import annotations

from xora_chart.config import load_config
from xora_chart.domain.models import DiscoveredCoin
from xora_chart.services import binance


async def run_discovery() -> list[DiscoveredCoin]:
    cfg = load_config().get("discovery", {})
    return await binance.discover_coins(
        top_gainers=int(cfg.get("top_gainers", 5)),
        top_losers=int(cfg.get("top_losers", 5)),
        top_volume=int(cfg.get("top_volume", 5)),
        trending=int(cfg.get("trending", 5)),
        quote_asset=cfg.get("quote_asset", "USDT"),
        min_quote_volume=float(cfg.get("min_quote_volume", 500_000)),
    )
