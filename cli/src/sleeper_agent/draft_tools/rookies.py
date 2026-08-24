"""Rookie triage: which incoming-draft-class rookies are worth surfacing.

`stats vorp` (`stats/vorp.py`) only produces a row for a player present in
the prior season's nflverse weekly-stats table, so every rookie with no
prior-NFL-season stats is structurally invisible to `stats vorp`,
`draft board`, and `value rank`/`value roster` alike — not stale, just never
present. `wiki/team/rookie-evaluation.md`'s draft-capital hit-rate table
gives a triage cutoff that makes "research every rookie" the wrong default:
most rookies picked outside these windows have single-digit-percent
historical fantasy relevance. See
docs/superpowers/specs/2026-08-22-rookie-and-new-outlook-player-visibility.md
§§1-2 for the full research/design trail.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sleeper_agent.config import data_dir
from sleeper_agent.models.sleeper import Player, parse_player
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table

# Position -> highest NFL-draft round (inclusive) worth surfacing, per
# wiki/team/rookie-evaluation.md's draft-capital table.
TRIAGE_CUTOFFS: dict[str, int] = {"TE": 1, "QB": 1, "WR": 2, "RB": 3}


@dataclass(frozen=True)
class TriagedRookie:
    player: Player
    draft_round: int


def crosswalk_draft_picks_to_sleeper_ids(
    draft_picks: pl.DataFrame, ff_playerids: pl.DataFrame, season: int
) -> pl.DataFrame:
    """Join nflverse's draft-picks table to Sleeper player IDs.

    `draft_picks`'s own `gsis_id` column is *not* a usable nflverse GSIS id
    for the current draft class — confirmed live against the 2026 class,
    it's some other PFR-derived scheme (e.g. "MEN516487" vs. the real
    "00-0041562" format) that only shows up for players with no accumulated
    NFL stats yet. Joining on it the way
    `value/scoring.py::gsis_id_for_sleeper_id` does produces zero matches,
    not partial ones. The working fallback: join on normalized (name,
    position) against `ff_playerids` (nflreadpy's `load_ff_playerids()`)
    filtered to `draft_year == season` instead.

    Picks with no match get a null `sleeper_id`, not an error — most day-3
    picks never get a Sleeper id assigned in the first place, and callers
    (`triage_rookies`) are expected to skip those rows.
    """
    picks_for_season = draft_picks.filter(pl.col("season") == season)
    ids_for_class = ff_playerids.filter(pl.col("draft_year") == season)

    picks_normalized = picks_for_season.with_columns(
        pl.col("pfr_player_name")
        .str.to_lowercase()
        .str.strip_chars()
        .alias("_join_name"),
        pl.col("position").str.to_lowercase().alias("_join_position"),
    )
    ids_normalized = ids_for_class.with_columns(
        pl.col("name").str.to_lowercase().str.strip_chars().alias("_join_name"),
        pl.col("position").str.to_lowercase().alias("_join_position"),
        pl.col("sleeper_id").cast(pl.Utf8).alias("sleeper_id"),
    ).select(["_join_name", "_join_position", "sleeper_id"])

    return picks_normalized.join(
        ids_normalized, on=["_join_name", "_join_position"], how="left"
    ).drop(["_join_name", "_join_position"])


def triage_rookies(
    draft_picks_df: pl.DataFrame, players_df: pl.DataFrame
) -> list[TriagedRookie]:
    """Filter a crosswalked draft-picks table down to fantasy-relevant rookies.

    `draft_picks_df` is expected to already carry a `sleeper_id` column
    (see `crosswalk_draft_picks_to_sleeper_ids`) — rows with no match, or a
    `sleeper_id` absent from `players_df` (the Sleeper player dictionary,
    `data/sleeper/players.parquet`), are skipped rather than erroring, per
    the crosswalk's own skip-not-error contract. Results are ordered by
    overall pick number.
    """
    players_by_id = {row["player_id"]: row for row in players_df.to_dicts()}
    rookies: list[TriagedRookie] = []
    for pick in draft_picks_df.sort("pick").to_dicts():
        position = pick.get("position")
        cutoff = TRIAGE_CUTOFFS.get(position) if position is not None else None
        if cutoff is None or pick["round"] > cutoff:
            continue
        sleeper_id = pick.get("sleeper_id")
        if sleeper_id is None:
            continue
        player_row = players_by_id.get(sleeper_id)
        if player_row is None:
            continue
        player = parse_player(
            sleeper_id,
            {
                "player_id": sleeper_id,
                "full_name": player_row["name"],
                # Coalesce with the draft pick's own position: a row only
                # survives the `cutoff`/`continue` check above when
                # `pick["position"]` is non-null (line 94), so this fallback
                # guarantees a triaged rookie's `Player.position` is never
                # None even when the Sleeper player dictionary hasn't been
                # assigned one yet for a very recently drafted rookie.
                "position": player_row["position"] or pick.get("position"),
                "team": player_row["team"],
                "status": player_row.get("status"),
                "injury_status": player_row.get("injury_status"),
                "fantasy_positions": player_row.get("fantasy_positions"),
                "years_exp": player_row.get("years_exp"),
            },
        )
        rookies.append(TriagedRookie(player=player, draft_round=pick["round"]))
    return rookies


def load_triaged_rookies(root: Path, season: str) -> list[TriagedRookie]:
    """Load + triage rookies for `season`, best-effort empty (not an error)
    when `data/nfl/draft_picks.parquet` or `data/sleeper/players.parquet`
    hasn't been synced yet — the sole caller is `value bigboard build`,
    which folds these rookies into the big board. (`draft board`'s old
    "Rookie watch" section was the other caller; it was removed once rookies
    started appearing inline in the big board's ranked order.)

    `DRAFT_PICKS_SCHEMA_VERSION` is imported locally, not at module level:
    `stats.draft_picks_sync` already imports
    `crosswalk_draft_picks_to_sleeper_ids` from this module at import time,
    so a top-level import here would form an import cycle.
    """
    from sleeper_agent.stats.draft_picks_sync import DRAFT_PICKS_SCHEMA_VERSION

    draft_picks_path = data_dir(root) / "nfl" / "draft_picks.parquet"
    players_path = data_dir(root) / "sleeper" / "players.parquet"
    if not draft_picks_path.exists() or not players_path.exists():
        return []
    draft_picks_df = read_table(
        draft_picks_path, expected_schema_version=DRAFT_PICKS_SCHEMA_VERSION
    ).filter(pl.col("season") == int(season))
    players_df = read_table(
        players_path, expected_schema_version=PLAYERS_SCHEMA_VERSION
    )
    return triage_rookies(draft_picks_df, players_df)
