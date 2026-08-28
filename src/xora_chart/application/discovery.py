from __future__ import annotations

from math import sqrt

from xora_chart.config import load_config
from xora_chart.domain.models import DiscoveredCoin
from xora_chart.services import binance


def _cohort_plan(coins: list[DiscoveredCoin], size: int = 5) -> list[DiscoveredCoin]:
    """Return gainers, losers, movers, volume cohorts with no repeated symbol.

    The market-data service already returns a globally unique candidate universe.
    This final application-layer pass makes the product contract explicit: up to
    five symbols per cohort, chosen sequentially from the same candidate universe,
    and never repeated across cohorts.
    """
    unique: dict[str, DiscoveredCoin] = {}
    for coin in coins:
        symbol = coin.symbol.upper()
        if symbol and symbol not in unique:
            unique[symbol] = coin.model_copy(update={"symbol": symbol})
    universe = list(unique.values())
    used: set[str] = set()
    result: list[DiscoveredCoin] = []

    def pct(coin: DiscoveredCoin) -> float:
        return float(coin.price_change_pct or 0.0)

    def volume(coin: DiscoveredCoin) -> float:
        return max(0.0, float(coin.quote_volume or 0.0))

    rankings = [
        ("gainer", sorted(universe, key=pct, reverse=True)),
        ("loser", sorted(universe, key=pct)),
        (
            "trending",
            sorted(universe, key=lambda c: abs(pct(c)) * sqrt(max(volume(c), 1.0)), reverse=True),
        ),
        ("volume", sorted(universe, key=volume, reverse=True)),
    ]

    for source, ranked in rankings:
        rank = 0
        for coin in ranked:
            if coin.symbol in used:
                continue
            rank += 1
            result.append(coin.model_copy(update={"source": source, "rank_in_source": rank}))
            used.add(coin.symbol)
            if rank >= size:
                break

    return result


async def run_discovery() -> list[DiscoveredCoin]:
    cfg = load_config().get("discovery", {})
    cohort_size = 5
    scan_limit = max(1, int(cfg.get("scan_limit", 20)))

    # Ask the live service for the configured candidate universe, then enforce
    # the four-cohort product contract here so presentation never has to invent
    # category membership or deduplicate symbols itself.
    coins = await binance.discover_coins(
        top_gainers=int(cfg.get("top_gainers", cohort_size)),
        top_losers=int(cfg.get("top_losers", cohort_size)),
        top_volume=int(cfg.get("top_volume", cohort_size)),
        trending=int(cfg.get("trending", cohort_size)),
        quote_asset=cfg.get("quote_asset", "USDT"),
        min_quote_volume=float(cfg.get("min_quote_volume", 500_000)),
    )
    planned = _cohort_plan(coins, size=cohort_size)
    return planned[:scan_limit]
