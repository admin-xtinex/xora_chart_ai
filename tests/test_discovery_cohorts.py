from xora_chart.application.discovery import _cohort_plan
from xora_chart.domain.models import DiscoveredCoin


def test_cohort_plan_returns_four_unique_five_coin_groups():
    coins = [
        DiscoveredCoin(
            symbol=f"COIN{i:02d}USDT",
            source="candidate",
            price_change_pct=float(i - 10),
            quote_volume=float((21 - i) * 1_000_000),
        )
        for i in range(1, 21)
    ]

    planned = _cohort_plan(coins)

    assert len(planned) == 20
    assert len({coin.symbol for coin in planned}) == 20
    assert [coin.source for coin in planned].count("gainer") == 5
    assert [coin.source for coin in planned].count("loser") == 5
    assert [coin.source for coin in planned].count("trending") == 5
    assert [coin.source for coin in planned].count("volume") == 5

    for source in ("gainer", "loser", "trending", "volume"):
        ranks = [coin.rank_in_source for coin in planned if coin.source == source]
        assert ranks == [1, 2, 3, 4, 5]


def test_cohort_plan_never_duplicates_input_symbols():
    coins = [
        DiscoveredCoin(symbol="BTCUSDT", source="gainer", price_change_pct=8, quote_volume=5_000_000),
        DiscoveredCoin(symbol="BTCUSDT", source="volume", price_change_pct=8, quote_volume=5_000_000),
        DiscoveredCoin(symbol="ETHUSDT", source="gainer", price_change_pct=5, quote_volume=4_000_000),
        DiscoveredCoin(symbol="SOLUSDT", source="loser", price_change_pct=-4, quote_volume=3_000_000),
    ]

    planned = _cohort_plan(coins)
    assert len({coin.symbol for coin in planned}) == len(planned)
