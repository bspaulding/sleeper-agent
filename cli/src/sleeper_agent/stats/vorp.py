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

Known v1 scope gap (see IMPLEMENTATION_PLAN.md deviation note): this covers
QB/RB/WR/TE only. Team defense (`DEF`) fantasy scoring depends on team-level
stats (points allowed, team sacks/INTs/fumble recoveries) that
`nflreadpy`'s per-player weekly stats don't carry — that needs a separate
team-defense stats source and is deferred, not silently wrong: `compute_vorp`
only ever returns rows for `CORE_POSITIONS`.
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
    return (
        scored_weekly.filter(pl.col("position").is_in(list(CORE_POSITIONS)))
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

        for row in rows:
            games_played = row["games_played"] or 0
            season_points = row["season_points"] or 0.0
            ppg = season_points / games_played if games_played else 0.0
            results.append(
                PlayerVorp(
                    sleeper_id=str(int(row["sleeper_id"])),
                    name=row["player_display_name"],
                    position=position,
                    games_played=games_played,
                    season_points=season_points,
                    points_per_game=ppg,
                    replacement_points=replacement_points,
                    vorp_season=season_points - replacement_points,
                    vorp_per_game=ppg - replacement_ppg,
                )
            )

    return results
