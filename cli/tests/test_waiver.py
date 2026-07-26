from __future__ import annotations

from sleeper_agent.sleeper_client.trending import TrendingPlayer
from sleeper_agent.waiver.recommend import (
    PlayerValueRow,
    recommend_waivers,
    suggested_bid_range,
)


def test_suggested_bid_range_scales_with_value_fraction() -> None:
    low_value = suggested_bid_range(
        budget_remaining=100, weeks_remaining=10, value_fraction=0.1
    )
    high_value = suggested_bid_range(
        budget_remaining=100, weeks_remaining=10, value_fraction=1.0
    )

    assert low_value[0] <= low_value[1]
    assert high_value[0] <= high_value[1]
    assert high_value[1] > low_value[1]


def test_suggested_bid_range_is_zero_for_zero_value_fraction() -> None:
    low, high = suggested_bid_range(
        budget_remaining=100, weeks_remaining=10, value_fraction=0.0
    )

    assert (low, high) == (0, 0)


def test_suggested_bid_range_never_exceeds_budget_remaining() -> None:
    low, high = suggested_bid_range(
        budget_remaining=5, weeks_remaining=1, value_fraction=1.0
    )

    assert 0 <= low <= 5
    assert 0 <= high <= 5


def test_suggested_bid_range_handles_zero_weeks_remaining_without_dividing_by_zero() -> (
    None
):
    low, high = suggested_bid_range(
        budget_remaining=50, weeks_remaining=0, value_fraction=1.0
    )

    assert low >= 0
    assert high >= low


def test_recommend_waivers_excludes_already_rostered_players() -> None:
    trending = [
        TrendingPlayer(player_id="1", count=100),
        TrendingPlayer(player_id="2", count=50),
    ]
    value_by_id = {
        "1": PlayerValueRow(name="Rostered Guy", position="RB", vorp_season=10.0),
        "2": PlayerValueRow(name="Free Guy", position="WR", vorp_season=5.0),
    }

    targets = recommend_waivers(
        trending, {"1"}, value_by_id, budget_remaining=100, weeks_remaining=10
    )

    assert [t.player_id for t in targets] == ["2"]


def test_recommend_waivers_ranks_by_vorp_then_trending_count() -> None:
    trending = [
        TrendingPlayer(player_id="1", count=10),
        TrendingPlayer(player_id="2", count=100),
    ]
    value_by_id = {
        "1": PlayerValueRow(name="Better Player", position="RB", vorp_season=50.0),
        "2": PlayerValueRow(name="More Trending", position="RB", vorp_season=5.0),
    }

    targets = recommend_waivers(
        trending, set(), value_by_id, budget_remaining=100, weeks_remaining=10
    )

    assert [t.player_id for t in targets] == ["1", "2"]
    assert targets[0].bid_high > targets[1].bid_high


def test_recommend_waivers_handles_players_with_no_vorp_data() -> None:
    trending = [TrendingPlayer(player_id="1", count=10)]

    targets = recommend_waivers(
        trending, set(), {}, budget_remaining=100, weeks_remaining=10
    )

    assert targets[0].vorp_season is None
    assert targets[0].name == "1"
    assert targets[0].position == "?"
    assert targets[0].bid_low <= targets[0].bid_high


def test_recommend_waivers_respects_top_n() -> None:
    trending = [TrendingPlayer(player_id=str(i), count=i) for i in range(20)]

    targets = recommend_waivers(
        trending, set(), {}, budget_remaining=100, weeks_remaining=10, top_n=3
    )

    assert len(targets) == 3
