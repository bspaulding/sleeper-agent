from __future__ import annotations

import polars as pl

from sleeper_agent.stats.vorp import (
    DEFAULT_FLEX_WEIGHTS,
    POSITION_YOY_RELIABILITY,
    add_fantasy_points_column,
    compute_def_vorp,
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


def test_compute_vorp_shrinks_by_position_reliability() -> None:
    """`vorp_season_shrunk` = position's own year-over-year reliability (r)
    times raw `vorp_season` -- QB's lower reliability should shrink a QB's
    vorp harder than an RB's identical raw vorp gets shrunk, since that's
    the whole point of feeding the bigboard a cross-position-comparable
    value instead of the raw one."""
    weekly = pl.DataFrame(
        [
            _weekly_row("00-A", "Runner A", "RB", 1, 100, 1),
            _weekly_row("00-A", "Runner A", "RB", 2, 100, 1),
            _weekly_row("00-B", "Runner B", "RB", 1, 0, 0),
            {
                "player_id": "00-Q",
                "player_display_name": "Passer Q",
                "position": "QB",
                "week": 1,
                "passing_yards": 3000,
                "passing_tds": 10,
                "rushing_yards": 0,
                "rushing_tds": 0,
            },
            {
                "player_id": "00-R",
                "player_display_name": "Passer R",
                "position": "QB",
                "week": 1,
                "passing_yards": 0,
                "passing_tds": 0,
                "rushing_yards": 0,
                "rushing_tds": 0,
            },
        ]
    )
    ids = pl.DataFrame(
        {
            "gsis_id": ["00-A", "00-B", "00-Q", "00-R"],
            "sleeper_id": ["101", "102", "201", "202"],
        }
    )
    scoring_settings = {"rush_yd": 0.1, "rush_td": 6.0, "pass_yd": 0.1, "pass_td": 6.0}
    roster_positions = ["QB", "RB", "RB", "WR", "WR", "TE"]

    # num_teams=2 so each position's replacement rank (slots * num_teams) is
    # 2, not 1 -- otherwise the single best player at each position would be
    # its own replacement level, making vorp_season (and this test) trivially
    # zero.
    results = compute_vorp(weekly, ids, scoring_settings, roster_positions, num_teams=2)

    by_id = {r.sleeper_id: r for r in results}
    rb = by_id["101"]
    qb = by_id["201"]
    assert rb.vorp_season_shrunk == POSITION_YOY_RELIABILITY["RB"] * rb.vorp_season
    assert qb.vorp_season_shrunk == POSITION_YOY_RELIABILITY["QB"] * qb.vorp_season
    # Same underlying replacement-relative shape (one clear starter, one at
    # replacement level) but QB's lower reliability (0.40 vs RB's 0.67)
    # shrinks its vorp harder in relative terms.
    assert (
        qb.vorp_season_shrunk / qb.vorp_season < rb.vorp_season_shrunk / rb.vorp_season
    )


DEF_SCORING_SETTINGS = {
    "sack": 1.0,
    "int": 2.0,
    "fum_rec": 2.0,
    "def_td": 6.0,
    "safe": 2.0,
    "blk_kick": 2.0,
    "pts_allow_0": 10.0,
    "pts_allow_1_6": 7.0,
    "pts_allow_7_13": 4.0,
    "pts_allow_14_20": 1.0,
    "pts_allow_21_27": 0.0,
    "pts_allow_28_34": -1.0,
    "pts_allow_35p": -4.0,
}


def test_compute_def_vorp_scores_real_stat_line_and_aliases_la_to_lar() -> None:
    team_stats = pl.DataFrame(
        [
            {
                "team": "SEA",
                "season_type": "REG",
                "game_id": "2025_01_SEA_LA",
                "def_sacks": 3,
                "def_interceptions": 1,
                "fumble_recovery_opp": 0,
                "def_tds": 0,
                "def_safeties": 0,
                "def_fg_blocks": 0,
                "def_pat_blocks": 0,
                "def_punt_blocks": 0,
            },
            {
                "team": "LA",
                "season_type": "REG",
                "game_id": "2025_01_SEA_LA",
                "def_sacks": 1,
                "def_interceptions": 0,
                "fumble_recovery_opp": 1,
                "def_tds": 1,
                "def_safeties": 0,
                "def_fg_blocks": 1,
                "def_pat_blocks": 0,
                "def_punt_blocks": 0,
            },
            # Postseason game — should be excluded even though it would
            # otherwise change both teams' totals.
            {
                "team": "SEA",
                "season_type": "POST",
                "game_id": "2025_20_SEA_LA",
                "def_sacks": 9,
                "def_interceptions": 9,
                "fumble_recovery_opp": 9,
                "def_tds": 9,
                "def_safeties": 9,
                "def_fg_blocks": 9,
                "def_pat_blocks": 9,
                "def_punt_blocks": 9,
            },
        ]
    )
    schedules = pl.DataFrame(
        [
            {
                "game_id": "2025_01_SEA_LA",
                "game_type": "REG",
                "home_team": "LA",
                "away_team": "SEA",
                "home_score": 10,
                "away_score": 20,
            },
            {
                "game_id": "2025_20_SEA_LA",
                "game_type": "POST",
                "home_team": "LA",
                "away_team": "SEA",
                "home_score": 0,
                "away_score": 0,
            },
        ]
    )
    def_players = pl.DataFrame(
        {
            "player_id": ["SEA", "LAR"],
            "name": ["Seattle Seahawks", "Los Angeles Rams"],
        }
    )
    roster_positions = ["QB", "RB", "WR", "TE", "DEF"]

    results = compute_def_vorp(
        team_stats,
        schedules,
        def_players,
        DEF_SCORING_SETTINGS,
        roster_positions,
        num_teams=1,
    )

    by_id = {r.sleeper_id: r for r in results}
    assert set(by_id) == {"SEA", "LAR"}
    assert all(r.position == "DEF" for r in results)
    assert all(r.games_played == 1 for r in results)

    # SEA: 3 sacks * 1 + 1 int * 2 = 5 stat points; allowed 10 (LA's home
    # score) -> pts_allow_7_13 tier = 4. Total 9.
    assert by_id["SEA"].season_points == 9.0
    assert by_id["SEA"].name == "Seattle Seahawks"

    # LA (aliased to Sleeper's "LAR"): 1 sack + 1 fum_rec*2 + 1 def_td*6 +
    # 1 blocked FG*2 = 11 stat points; allowed 20 (SEA's away score) ->
    # pts_allow_14_20 tier = 1. Total 12.
    assert by_id["LAR"].season_points == 12.0
    assert by_id["LAR"].name == "Los Angeles Rams"

    # One DEF slot, one team in the league -> replacement rank 1, so the
    # top-scoring defense (LAR) sets replacement level and has zero VORP.
    assert by_id["LAR"].vorp_season == 0.0
    assert by_id["SEA"].vorp_season == -3.0
    assert by_id["SEA"].vorp_season_shrunk == POSITION_YOY_RELIABILITY["DEF"] * -3.0


def test_compute_def_vorp_falls_back_to_team_code_when_name_unresolved() -> None:
    team_stats = pl.DataFrame(
        [
            {
                "team": "KC",
                "season_type": "REG",
                "game_id": "2025_01_KC_DEN",
                "def_sacks": 0,
                "def_interceptions": 0,
                "fumble_recovery_opp": 0,
                "def_tds": 0,
                "def_safeties": 0,
            }
        ]
    )
    schedules = pl.DataFrame(
        [
            {
                "game_id": "2025_01_KC_DEN",
                "game_type": "REG",
                "home_team": "KC",
                "away_team": "DEN",
                "home_score": 0,
                "away_score": 0,
            }
        ]
    )
    def_players = pl.DataFrame({"player_id": [], "name": []})

    results = compute_def_vorp(
        team_stats, schedules, def_players, DEF_SCORING_SETTINGS, ["DEF"], num_teams=1
    )

    assert results[0].name == "KC"
