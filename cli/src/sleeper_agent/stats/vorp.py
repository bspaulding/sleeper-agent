"""Fantasy points + VORP from nflverse weekly stats and live league scoring.

Two generalizations vs. the `bspaulding/nfl-vorp` methodology this is ported
from (see IMPLEMENTATION_PLAN.md §3):

1. Fantasy points are computed from the league's live `scoring_settings`
   (`STAT_COLUMN_TO_SCORING_KEY` maps nflverse weekly columns to Sleeper
   scoring keys) rather than a hardcoded scoring table.
2. Replacement level is derived from `roster_positions`, distributing each
   FLEX-family slot across its eligible positions by a configurable weight
   (default RB 0.45 / WR 0.45 / TE 0.10 — tunable, not derived from anything
   fancier for v1) rather than assuming one hardcoded FLEX split.

`compute_vorp` covers QB/RB/WR/TE only (`CORE_POSITIONS`) — team defense
(`DEF`) fantasy scoring depends on team-level stats (points allowed, team
sacks/INTs/fumble recoveries) that `nflreadpy`'s per-player weekly stats
don't carry. `compute_def_vorp` below fills that gap from a separate
team-level source (`nflreadpy.load_team_stats` + `load_schedules`), scored
against the same live `scoring_settings` rather than a hardcoded table —
same principle as (1) above, different input shape, so it's a sibling
function rather than a `CORE_POSITIONS` addition.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

CORE_POSITIONS: tuple[str, ...] = ("QB", "RB", "WR", "TE")
FLEX_SLOT_NAMES = frozenset({"FLEX", "WRRB_FLEX", "REC_FLEX", "SUPER_FLEX"})
DEFAULT_FLEX_WEIGHTS: dict[str, float] = {"RB": 0.45, "WR": 0.45, "TE": 0.10}

# nflverse weekly-stats column -> Sleeper scoring_settings key. Multiple
# columns may map to the same key (e.g. the three fumbles-lost columns all
# feed `fum_lost`); each is summed independently and multiplied by that
# key's rate.
STAT_COLUMN_TO_SCORING_KEY: dict[str, str] = {
    "passing_yards": "pass_yd",
    "passing_tds": "pass_td",
    "interceptions": "pass_int",
    "passing_2pt_conversions": "pass_2pt",
    "rushing_yards": "rush_yd",
    "rushing_tds": "rush_td",
    "rushing_2pt_conversions": "rush_2pt",
    "receptions": "rec",
    "receiving_yards": "rec_yd",
    "receiving_tds": "rec_td",
    "receiving_2pt_conversions": "rec_2pt",
    "sack_fumbles_lost": "fum_lost",
    "rushing_fumbles_lost": "fum_lost",
    "receiving_fumbles_lost": "fum_lost",
    "special_teams_tds": "st_td",
}


# Year-over-year vorp_season reliability per position (Pearson r, players with
# >=8 games played in both years of a season pair, pooled 2018-2025 -- see
# decisions/2026/2026-08-28-bigboard-qb-vorp-reliability-research.md). DEF
# uses its pooled full-population r instead (2026-08-28-bigboard-def-vorp-
# research-streaming-recommended.md): a team defense doesn't have the
# "backup who never plays" issue a >=8-games filter exists to correct for,
# since all 32 teams play essentially every scheduled game every year.
#
# Used to shrink vorp_season toward replacement level
# (`vorp_season_shrunk = r * vorp_season`) before cross-position ordinal
# comparison on the big board: a position whose raw season total carries
# over to next year less reliably shouldn't get full credit for an extreme
# value on the shared scale (see `bigboard.merge_bigboard`, which sorts and
# inserts new rows by `vorp_season_shrunk`, not raw `vorp_season`). A
# position missing from this map (there are none among CORE_POSITIONS/DEF
# today) would fall back to no shrinkage (factor 1.0) rather than error.
# Not derived from anything fancier for v1 -- same hardcoded-but-documented,
# tunable convention as DEFAULT_FLEX_WEIGHTS above.
POSITION_YOY_RELIABILITY: dict[str, float] = {
    "QB": 0.40,
    "RB": 0.67,
    "WR": 0.71,
    "TE": 0.68,
    "DEF": 0.31,
}


@dataclass(frozen=True)
class PlayerVorp:
    sleeper_id: str
    name: str
    position: str
    games_played: int
    season_points: float
    points_per_game: float
    replacement_points: float
    vorp_season: float
    vorp_per_game: float
    vorp_season_shrunk: float


def add_fantasy_points_column(
    df: pl.DataFrame, scoring_settings: dict[str, float]
) -> pl.DataFrame:
    expr = pl.lit(0.0)
    for column, scoring_key in STAT_COLUMN_TO_SCORING_KEY.items():
        if column not in df.columns:
            continue
        rate = scoring_settings.get(scoring_key, 0.0)
        expr = expr + pl.col(column).fill_null(0.0) * rate
    return df.with_columns(expr.alias("fantasy_points"))


def compute_replacement_ranks(
    roster_positions: Sequence[str],
    num_teams: int,
    *,
    flex_weights: dict[str, float] = DEFAULT_FLEX_WEIGHTS,
) -> dict[str, int]:
    """Starter-slot count per core position, times league size, as an integer rank.

    Counts each literal position slot, then distributes each FLEX-family
    slot across `flex_weights`' eligible positions.
    """
    literal_counts: dict[str, float] = dict.fromkeys(CORE_POSITIONS, 0.0)
    flex_count = 0
    for slot in roster_positions:
        if slot in literal_counts:
            literal_counts[slot] += 1.0
        elif slot in FLEX_SLOT_NAMES:
            flex_count += 1

    for position, weight in flex_weights.items():
        if position in literal_counts:
            literal_counts[position] += flex_count * weight

    return {
        position: max(1, round(literal_counts[position] * num_teams))
        for position in CORE_POSITIONS
    }


def _season_totals(scored_weekly: pl.DataFrame) -> pl.DataFrame:
    """Sum to one row per player. Regular-season games only: `nflreadpy`'s
    weekly file mixes `REG` and `POST` rows with no filtering of its own
    (confirmed 2026-08-27 — `stats_player_week_<season>.parquet` carries
    both), so an unfiltered sum silently credits deep playoff teams' players
    with games a 12-team redraft league never plays. `games_played` above 17
    in `data/vorp/<season>.parquet` was the tell (see
    `decisions/2026/2026-08-27-bigboard-external-consensus-comparison.md`).
    Only filtered when the column exists, so fixture DataFrames without it
    (all pre-existing tests) still work unchanged.
    """
    regular_season = (
        scored_weekly.filter(pl.col("season_type") == "REG")
        if "season_type" in scored_weekly.columns
        else scored_weekly
    )
    return (
        regular_season.filter(pl.col("position").is_in(list(CORE_POSITIONS)))
        .group_by(["player_id", "player_display_name", "position"])
        .agg(
            [
                pl.col("fantasy_points").sum().alias("season_points"),
                pl.len().alias("games_played"),
            ]
        )
    )


def compute_vorp(
    weekly_stats: pl.DataFrame,
    id_crosswalk: pl.DataFrame,
    scoring_settings: dict[str, float],
    roster_positions: Sequence[str],
    num_teams: int,
    *,
    flex_weights: dict[str, float] = DEFAULT_FLEX_WEIGHTS,
) -> list[PlayerVorp]:
    scored = add_fantasy_points_column(weekly_stats, scoring_settings)
    season_totals = _season_totals(scored)

    joined = season_totals.join(
        id_crosswalk.select(["gsis_id", "sleeper_id"]),
        left_on="player_id",
        right_on="gsis_id",
        how="left",
    ).filter(pl.col("sleeper_id").is_not_null())

    replacement_ranks = compute_replacement_ranks(
        roster_positions, num_teams, flex_weights=flex_weights
    )

    results: list[PlayerVorp] = []
    for position in CORE_POSITIONS:
        position_rows = joined.filter(pl.col("position") == position).sort(
            "season_points", descending=True
        )
        rank = replacement_ranks[position]
        rows = position_rows.to_dicts()
        if rows:
            replacement_row = rows[min(rank, len(rows)) - 1]
            replacement_points = replacement_row["season_points"]
            replacement_games = replacement_row["games_played"] or 1
            replacement_ppg = replacement_points / replacement_games
        else:
            replacement_points = 0.0
            replacement_ppg = 0.0

        reliability = POSITION_YOY_RELIABILITY.get(position, 1.0)
        for row in rows:
            games_played = row["games_played"] or 0
            season_points = row["season_points"] or 0.0
            ppg = season_points / games_played if games_played else 0.0
            vorp_season = season_points - replacement_points
            results.append(
                PlayerVorp(
                    sleeper_id=str(int(row["sleeper_id"])),
                    name=row["player_display_name"],
                    position=position,
                    games_played=games_played,
                    season_points=season_points,
                    points_per_game=ppg,
                    replacement_points=replacement_points,
                    vorp_season=vorp_season,
                    vorp_per_game=ppg - replacement_ppg,
                    vorp_season_shrunk=reliability * vorp_season,
                )
            )

    return results


# nflverse `team_stats` column -> Sleeper scoring_settings key, for the
# team-defense counting stats that carry directly (one column, one rate).
# Blocked kicks are handled separately below since Sleeper scores all three
# nflverse block columns (FG/PAT/punt) under the single `blk_kick` key.
DEF_STAT_COLUMN_TO_SCORING_KEY: dict[str, str] = {
    "def_sacks": "sack",
    "def_interceptions": "int",
    "fumble_recovery_opp": "fum_rec",
    "def_tds": "def_td",
    "def_safeties": "safe",
}
DEF_BLOCKED_KICK_COLUMNS: tuple[str, ...] = (
    "def_fg_blocks",
    "def_pat_blocks",
    "def_punt_blocks",
)

# Sleeper's points-allowed scoring is tiered per game, not on the season
# total — each tuple is (inclusive upper bound, scoring_settings key);
# anything above the last bound falls to `DEF_POINTS_ALLOWED_35P_KEY`.
DEF_POINTS_ALLOWED_TIERS: tuple[tuple[int, str], ...] = (
    (0, "pts_allow_0"),
    (6, "pts_allow_1_6"),
    (13, "pts_allow_7_13"),
    (20, "pts_allow_14_20"),
    (27, "pts_allow_21_27"),
    (34, "pts_allow_28_34"),
)
DEF_POINTS_ALLOWED_35P_KEY = "pts_allow_35p"

# Sleeper's DEF `player_id` is the team's own roster code, which matches
# nflverse's `team` column for every franchise except the Rams (nflverse
# "LA" vs Sleeper "LAR").
DEF_TEAM_CODE_ALIASES: dict[str, str] = {"LA": "LAR"}


def _points_allowed_expr(scoring_settings: dict[str, float]) -> pl.Expr:
    points_allowed = pl.col("points_allowed")
    ceiling, key = DEF_POINTS_ALLOWED_TIERS[0]
    expr = pl.when(points_allowed <= ceiling).then(
        pl.lit(scoring_settings.get(key, 0.0))
    )
    for ceiling, key in DEF_POINTS_ALLOWED_TIERS[1:]:
        expr = expr.when(points_allowed <= ceiling).then(
            pl.lit(scoring_settings.get(key, 0.0))
        )
    return expr.otherwise(pl.lit(scoring_settings.get(DEF_POINTS_ALLOWED_35P_KEY, 0.0)))


def _def_season_totals(
    team_stats: pl.DataFrame,
    schedules: pl.DataFrame,
    scoring_settings: dict[str, float],
) -> pl.DataFrame:
    """One row per team (`sleeper_id`, `season_points`, `games_played`),
    regular season only — same REG-only convention as `_season_totals`, for
    the same reason (nflverse's team-stats and schedules files both mix
    `REG`/postseason rows with no filtering of their own)."""
    reg_team_stats = (
        team_stats.filter(pl.col("season_type") == "REG")
        if "season_type" in team_stats.columns
        else team_stats
    )
    reg_schedules = (
        schedules.filter(pl.col("game_type") == "REG")
        if "game_type" in schedules.columns
        else schedules
    )

    stat_points = pl.lit(0.0)
    for column, scoring_key in DEF_STAT_COLUMN_TO_SCORING_KEY.items():
        if column not in reg_team_stats.columns:
            continue
        rate = scoring_settings.get(scoring_key, 0.0)
        stat_points = stat_points + pl.col(column).fill_null(0.0) * rate

    blocked_kick_columns = [
        c for c in DEF_BLOCKED_KICK_COLUMNS if c in reg_team_stats.columns
    ]
    if blocked_kick_columns:
        blk_rate = scoring_settings.get("blk_kick", 0.0)
        stat_points = (
            stat_points
            + pl.sum_horizontal(
                [pl.col(c).fill_null(0.0) for c in blocked_kick_columns]
            )
            * blk_rate
        )

    scored = reg_team_stats.with_columns(stat_points.alias("stat_points"))

    points_allowed = pl.concat(
        [
            reg_schedules.select(
                pl.col("game_id"),
                pl.col("home_team").alias("team"),
                pl.col("away_score").alias("points_allowed"),
            ),
            reg_schedules.select(
                pl.col("game_id"),
                pl.col("away_team").alias("team"),
                pl.col("home_score").alias("points_allowed"),
            ),
        ]
    )

    joined = scored.join(
        points_allowed, on=["game_id", "team"], how="left"
    ).with_columns(_points_allowed_expr(scoring_settings).alias("points_allowed_score"))
    scored_games = joined.with_columns(
        (pl.col("stat_points") + pl.col("points_allowed_score").fill_null(0.0)).alias(
            "fantasy_points"
        )
    )

    return (
        scored_games.with_columns(
            pl.col("team").replace(DEF_TEAM_CODE_ALIASES).alias("sleeper_id")
        )
        .group_by("sleeper_id")
        .agg(
            [
                pl.col("fantasy_points").sum().alias("season_points"),
                pl.len().alias("games_played"),
            ]
        )
    )


def compute_def_vorp(
    team_stats: pl.DataFrame,
    schedules: pl.DataFrame,
    def_players: pl.DataFrame,
    scoring_settings: dict[str, float],
    roster_positions: Sequence[str],
    num_teams: int,
) -> list[PlayerVorp]:
    """Team-defense VORP from real per-game defensive stats and points
    allowed, scored against the league's live `scoring_settings` — the
    `DEF` counterpart to `compute_vorp`. `def_players` is
    `data/sleeper/players.parquet` filtered to `position == "DEF"`, used
    only to resolve a display name for each team code.

    Replacement level is the last literal `DEF` roster slot across the
    league (`num_teams` times however many `DEF` slots `roster_positions`
    carries) — DEF has no FLEX-family slot to distribute, unlike
    `compute_replacement_ranks`'s core positions.
    """
    season_totals = _def_season_totals(team_stats, schedules, scoring_settings)
    names_by_id = dict(
        zip(def_players["player_id"].to_list(), def_players["name"].to_list())
    )

    def_slots = sum(1 for slot in roster_positions if slot == "DEF")
    rank = max(1, def_slots * num_teams)
    rows = season_totals.sort("season_points", descending=True).to_dicts()
    if rows:
        replacement_row = rows[min(rank, len(rows)) - 1]
        replacement_points = replacement_row["season_points"]
        replacement_games = replacement_row["games_played"] or 1
        replacement_ppg = replacement_points / replacement_games
    else:
        replacement_points = 0.0
        replacement_ppg = 0.0

    reliability = POSITION_YOY_RELIABILITY.get("DEF", 1.0)
    results: list[PlayerVorp] = []
    for row in rows:
        games_played = row["games_played"] or 0
        season_points = row["season_points"] or 0.0
        ppg = season_points / games_played if games_played else 0.0
        sleeper_id = row["sleeper_id"]
        vorp_season = season_points - replacement_points
        results.append(
            PlayerVorp(
                sleeper_id=sleeper_id,
                name=names_by_id.get(sleeper_id, sleeper_id),
                position="DEF",
                games_played=games_played,
                season_points=season_points,
                points_per_game=ppg,
                replacement_points=replacement_points,
                vorp_season=vorp_season,
                vorp_per_game=ppg - replacement_ppg,
                vorp_season_shrunk=reliability * vorp_season,
            )
        )
    return results
