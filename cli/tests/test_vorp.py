from __future__ import annotations

import polars as pl

from sleeper_agent.stats.vorp import (
    DEFAULT_FLEX_WEIGHTS,
    add_fantasy_points_column,
    compute_replacement_ranks,
    compute_vorp,
)

REAL_LEAGUE_ROSTER_POSITIONS = [
    "QB",
    "RB",
    "RB",
    "WR",
    "WR",
    "TE",
    "FLEX",
    "FLEX",
    "DEF",
    "BN",
    "BN",
    "BN",
    "BN",
    "BN",
    "BN",
]


def test_add_fantasy_points_column_matches_known_stat_line() -> None:
    df = pl.DataFrame(
        {
            "receptions": [5],
            "receiving_yards": [80],
            "receiving_tds": [1],
            "rushing_yards": [0],
        }
    )
    scoring_settings = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "rush_yd": 0.1}

    result = add_fantasy_points_column(df, scoring_settings)

    # 5 rec * 1.0 + 80 yd * 0.1 + 1 td * 6.0 = 5 + 8 + 6 = 19
    assert result["fantasy_points"].to_list() == [19.0]


def test_add_fantasy_points_column_sums_multiple_columns_into_shared_key() -> None:
    df = pl.DataFrame(
        {
            "sack_fumbles_lost": [1],
            "rushing_fumbles_lost": [1],
            "receiving_fumbles_lost": [0],
        }
    )
    scoring_settings = {"fum_lost": -1.0}

    result = add_fantasy_points_column(df, scoring_settings)

    assert result["fantasy_points"].to_list() == [-2.0]


def test_add_fantasy_points_column_ignores_columns_absent_from_scoring_settings() -> (
    None
):
    df = pl.DataFrame({"passing_yards": [300]})

    result = add_fantasy_points_column(df, {})

    assert result["fantasy_points"].to_list() == [0.0]


def test_compute_replacement_ranks_real_league_roster() -> None:
    ranks = compute_replacement_ranks(REAL_LEAGUE_ROSTER_POSITIONS, num_teams=12)

    assert ranks["QB"] == 12
    assert ranks["RB"] == 35
    assert ranks["WR"] == 35
    assert ranks["TE"] == 14


def test_compute_replacement_ranks_no_flex_slot() -> None:
    roster = ["QB", "RB", "RB", "WR", "WR", "TE", "DEF", "BN", "BN"]

    ranks = compute_replacement_ranks(roster, num_teams=10)

    assert ranks == {"QB": 10, "RB": 20, "WR": 20, "TE": 10}


def test_compute_replacement_ranks_super_flex_only_distributes_to_flex_weighted_positions() -> (
    None
):
    roster = ["QB", "RB", "WR", "TE", "SUPER_FLEX", "BN"]

    ranks = compute_replacement_ranks(
        roster, num_teams=10, flex_weights=DEFAULT_FLEX_WEIGHTS
    )

    # SUPER_FLEX isn't in DEFAULT_FLEX_WEIGHTS (RB/WR/TE only), so QB stays
    # at its literal count only — a documented v1 limitation, not a bug.
    assert ranks["QB"] == 10
    assert ranks["RB"] > 10
    assert ranks["WR"] > 10
    assert ranks["TE"] > 10


def test_compute_replacement_ranks_ignores_flex_weight_keys_outside_core_positions() -> (
    None
):
    roster = ["QB", "RB", "WR", "TE", "FLEX", "BN"]

    ranks = compute_replacement_ranks(
        roster, num_teams=10, flex_weights={"RB": 0.5, "K": 0.5}
    )

    # "K" isn't a core position, so its share of the FLEX slot is silently
    # dropped rather than crashing or inventing a K entry.
    assert set(ranks) == {"QB", "RB", "WR", "TE"}
    assert ranks["RB"] == 15  # (1 + 1*0.5) * 10 = 15


def _weekly_row(
    player_id: str,
    name: str,
    position: str,
    week: int,
    rushing_yards: float,
    rushing_tds: float,
) -> dict[str, object]:
    return {
        "player_id": player_id,
        "player_display_name": name,
        "position": position,
        "week": week,
        "rushing_yards": rushing_yards,
        "rushing_tds": rushing_tds,
    }


def test_compute_vorp_ranks_and_scores_against_replacement_level() -> None:
    weekly = pl.DataFrame(
        [
            _weekly_row("00-A", "Runner A", "RB", 1, 100, 1),
            _weekly_row("00-A", "Runner A", "RB", 2, 100, 1),
            _weekly_row("00-B", "Runner B", "RB", 1, 50, 0),
            _weekly_row("00-B", "Runner B", "RB", 2, 50, 0),
            _weekly_row("00-C", "Runner C", "RB", 1, 20, 0),
            _weekly_row("00-C", "Runner C", "RB", 2, 20, 0),
            _weekly_row("00-W", "Only Receiver", "WR", 1, 0, 0),
        ]
    )
    ids = pl.DataFrame(
        {
            "gsis_id": ["00-A", "00-B", "00-C", "00-W", "00-UNMAPPED"],
            "sleeper_id": ["101", "102", "103", "104", None],
        }
    )
    scoring_settings = {"rush_yd": 0.1, "rush_td": 6.0}
    roster_positions = ["QB", "RB", "RB", "WR", "WR", "TE"]

    results = compute_vorp(weekly, ids, scoring_settings, roster_positions, num_teams=1)

    by_id = {r.sleeper_id: r for r in results}

    assert by_id["101"].season_points == 32.0
    assert by_id["101"].vorp_season == 22.0
    assert by_id["101"].vorp_per_game == 11.0

    assert by_id["102"].season_points == 10.0
    assert by_id["102"].vorp_season == 0.0

    assert by_id["103"].season_points == 4.0
    assert by_id["103"].vorp_season == -6.0
    assert by_id["103"].vorp_per_game == -3.0

    # WR has only one player but a replacement rank of 2 (2 * 1 team):
    # clamped to the only available player, so their own points are the
    # replacement level and their VORP is zero.
    assert by_id["104"].vorp_season == 0.0

    # Positions with zero rows (QB, TE here) and unmapped gsis_ids
    # (00-UNMAPPED never appears in the weekly stats) don't blow up and
    # simply produce no rows.
    assert all(r.position != "QB" for r in results)
    assert all(r.position != "TE" for r in results)
    assert "00-UNMAPPED" not in {r.sleeper_id for r in results}


def test_compute_vorp_excludes_postseason_rows() -> None:
    """nflreadpy's weekly file mixes REG and POST rows with no filtering of
    its own — a deep playoff run must not inflate a player's season total
    with games a 12-team redraft league never plays."""
    weekly = pl.DataFrame(
        [
            {**_weekly_row("00-A", "Runner A", "RB", 1, 100, 1), "season_type": "REG"},
            {**_weekly_row("00-A", "Runner A", "RB", 2, 100, 1), "season_type": "REG"},
            {**_weekly_row("00-A", "Runner A", "RB", 3, 100, 1), "season_type": "POST"},
            {**_weekly_row("00-B", "Runner B", "RB", 1, 50, 0), "season_type": "REG"},
            {**_weekly_row("00-B", "Runner B", "RB", 2, 50, 0), "season_type": "REG"},
        ]
    )
    ids = pl.DataFrame({"gsis_id": ["00-A", "00-B"], "sleeper_id": ["101", "102"]})
    scoring_settings = {"rush_yd": 0.1, "rush_td": 6.0}
    roster_positions = ["QB", "RB", "RB", "WR", "WR", "TE"]

    results = compute_vorp(weekly, ids, scoring_settings, roster_positions, num_teams=1)

    by_id = {r.sleeper_id: r for r in results}
    assert by_id["101"].games_played == 2
    assert by_id["101"].season_points == 32.0
