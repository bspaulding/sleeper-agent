"""Role-changer (FA/trade) detection: a full VORP row that silently assumes
team/role continuity that may no longer hold.

Sibling gap to `draft_tools/rookies.py`, but a different failure mode: a
rookie is *missing* from `stats vorp` entirely; a role-changer has a full
VORP row, computed correctly from last season's stats -- the row just
assumes the team/scheme context that produced it still applies. Unlike the
rookie pipeline, no new data source is needed here -- everything read below
is already synced by `stats sync`/`sleeper players sync`. See
docs/superpowers/specs/2026-08-22-role-changer-visibility.md and
wiki/team/role-changers.md for the full research/design trail.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from sleeper_agent.stats.vorp import CORE_POSITIONS

# nflverse codes the Rams `LA`; Sleeper codes them `LAR` -- confirmed by
# diffing every team code on both sides live, this is the *only* mismatch
# across all 32 teams, not a general fuzzy-matching problem.
TEAM_CODE_ALIASES: dict[str, str] = {"LA": "LAR"}

# "Had a real role somewhere" floor on prior-season touches/targets combined
# (carries + targets) -- not a quality signal, just excludes the long tail of
# roster churn nobody should spend research time on. Mirrors
# `draft_tools/board.py`'s `_is_tier_break` threshold: simple and testable
# now, tune later against real results.
MIN_PRIOR_SEASON_TOUCHES = 50


@dataclass(frozen=True)
class TeamChange:
    sleeper_id: str
    name: str
    position: str
    old_team: str
    new_team: str
    total_touches: int


def detect_team_changes(
    weekly_stats: pl.DataFrame,
    players_df: pl.DataFrame,
    id_crosswalk: pl.DataFrame,
) -> list[TeamChange]:
    """Diff each player's last-known prior-season team against their
    current Sleeper-listed team.

    `weekly_stats` is a season of `data/stats/weekly/{season}.parquet` --
    the last row per player (sorted by week) gives their most recent
    prior-season team and the season's total touches/targets.
    `players_df` (`data/sleeper/players.parquet`) supplies the current
    team. Both join through `id_crosswalk` (`data/stats/ids.parquet`), the
    same `gsis_id`<->`sleeper_id` crosswalk `compute_vorp` already uses.

    Scoped to `CORE_POSITIONS` (QB/RB/WR/TE), matching `compute_vorp`'s own
    scope -- team churn at other positions isn't a fantasy-relevant signal
    here. A player missing a crosswalk match, missing from `players_df`, or
    with no current team on record is skipped rather than erroring, same
    skip-not-error contract as `draft_tools/rookies.py::triage_rookies`.
    """
    per_player = (
        weekly_stats.filter(pl.col("position").is_in(list(CORE_POSITIONS)))
        .sort("week")
        .group_by("player_id")
        .agg(
            [
                pl.col("team").last().alias("old_team"),
                pl.col("position").last().alias("position"),
                (pl.col("carries").fill_null(0) + pl.col("targets").fill_null(0))
                .sum()
                .alias("total_touches"),
            ]
        )
    )

    crosswalk = id_crosswalk.filter(pl.col("sleeper_id").is_not_null()).with_columns(
        pl.col("sleeper_id").cast(pl.Int64).cast(pl.Utf8).alias("sleeper_id")
    )

    joined = per_player.join(
        crosswalk.select(["gsis_id", "sleeper_id"]),
        left_on="player_id",
        right_on="gsis_id",
        how="inner",
    )

    current = players_df.select(
        [
            pl.col("player_id").cast(pl.Utf8).alias("sleeper_id"),
            pl.col("name"),
            pl.col("team").alias("new_team"),
        ]
    )

    merged = joined.join(current, on="sleeper_id", how="inner")

    changes: list[TeamChange] = []
    for row in merged.to_dicts():
        old_team = row["old_team"]
        new_team = row["new_team"]
        if not old_team or not new_team:
            continue
        normalized_old = TEAM_CODE_ALIASES.get(old_team, old_team)
        if normalized_old == new_team:
            continue
        changes.append(
            TeamChange(
                sleeper_id=row["sleeper_id"],
                name=row["name"],
                position=row["position"],
                old_team=old_team,
                new_team=new_team,
                total_touches=int(row["total_touches"]),
            )
        )
    return changes


def triage_team_changes(
    changes: list[TeamChange], *, min_touches: int = MIN_PRIOR_SEASON_TOUCHES
) -> list[TeamChange]:
    """Filter to team-changers with a "had a real role somewhere" floor of
    prior-season touches/targets -- not a quality bar, just narrows out the
    long tail of roster churn (a fourth-string RB bouncing practice squads)
    with no more fantasy relevance than the deep rookie classes
    `triage_rookies` already excludes.
    """
    return [change for change in changes if change.total_touches >= min_touches]
