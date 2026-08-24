"""The pre-draft big board: one materialized, hand-reviewed ordinal ranking
merging VORP-ranked veterans and triaged rookies.

See docs/superpowers/specs/2026-08-23-draft-bigboard-design.md. Deliberately
CSV, not parquet like the rest of `data/` — this file is meant to be
reviewed and edited by an LLM (with human sign-off) between builds, so it
needs to stay plain-text and git-diffable.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

import polars as pl

from sleeper_agent.config import data_dir
from sleeper_agent.draft_tools.rookies import TriagedRookie

BIGBOARD_FIELDS = [
    "rank",
    "player_id",
    "name",
    "position",
    "source",
    "vorp",
    "draft_round",
    "rationale",
    "log_ref",
]

# A row carrying either marker is an unreviewed judgment gap — see the
# hard-stop rule in docs/superpowers/specs/2026-08-23-draft-bigboard-
# design.md §4. Whole-file, not just the top of the board.
REVIEW_MARKERS = ("[NEEDS REVIEW", "[VORP CHANGED")


@dataclass(frozen=True)
class BigboardRow:
    rank: int
    player_id: str
    name: str
    position: str
    source: Literal["vorp", "rookie"]
    vorp: float | None
    draft_round: int | None
    rationale: str
    log_ref: str | None


class BigboardNotBuiltError(Exception):
    def __init__(self, season: str) -> None:
        self.season = season
        super().__init__(
            f"data/bigboard/{season}.csv not found — run the bigboard skill "
            f"(or `sleeper-agent value bigboard build --season {season}`) first"
        )


class BigboardUnresolvedRowError(Exception):
    def __init__(self, season: str, unresolved: list[BigboardRow]) -> None:
        self.season = season
        self.unresolved = unresolved
        names = ", ".join(f"{row.name} (rank {row.rank})" for row in unresolved[:5])
        more = f" and {len(unresolved) - 5} more" if len(unresolved) > 5 else ""
        super().__init__(
            f"data/bigboard/{season}.csv has {len(unresolved)} unresolved row(s) "
            f"still flagged for review: {names}{more} — finish the bigboard "
            "skill's review pass before drafting"
        )


def _bigboard_path(root: Path, season: str) -> Path:
    return data_dir(root) / "bigboard" / f"{season}.csv"


def _is_unresolved(row: BigboardRow) -> bool:
    return any(marker in row.rationale for marker in REVIEW_MARKERS)


def _read_rows(path: Path) -> list[BigboardRow]:
    rows: list[BigboardRow] = []
    with path.open(newline="") as fh:
        for raw in csv.DictReader(fh):
            rows.append(
                BigboardRow(
                    rank=int(raw["rank"]),
                    player_id=raw["player_id"],
                    name=raw["name"],
                    position=raw["position"],
                    source=raw["source"],  # type: ignore[arg-type]
                    vorp=float(raw["vorp"]) if raw["vorp"] else None,
                    draft_round=int(raw["draft_round"])
                    if raw["draft_round"]
                    else None,
                    rationale=raw["rationale"],
                    log_ref=raw["log_ref"] or None,
                )
            )
    rows.sort(key=lambda r: r.rank)
    return rows


def load_bigboard_for_build(root: Path, season: str) -> list[BigboardRow]:
    """Raw load for `bigboard build`: empty (not an error) when no file
    exists yet (first-ever build), and never raises on unresolved rows —
    the whole point of a build run is to work with rows still flagged."""
    path = _bigboard_path(root, season)
    if not path.exists():
        return []
    return _read_rows(path)


def load_bigboard(root: Path, season: str) -> list[BigboardRow]:
    """Load for live consumption (`draft board`/`watch-picks`): hard-stops
    on a missing file or any unresolved row anywhere in it."""
    path = _bigboard_path(root, season)
    if not path.exists():
        raise BigboardNotBuiltError(season)
    rows = _read_rows(path)
    unresolved = [row for row in rows if _is_unresolved(row)]
    if unresolved:
        raise BigboardUnresolvedRowError(season, unresolved)
    return rows


def save_bigboard(root: Path, season: str, rows: Sequence[BigboardRow]) -> None:
    path = _bigboard_path(root, season)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=BIGBOARD_FIELDS)
        writer.writeheader()
        for row in rows:
            d = asdict(row)
            d["vorp"] = "" if row.vorp is None else row.vorp
            d["draft_round"] = "" if row.draft_round is None else row.draft_round
            d["log_ref"] = row.log_ref or ""
            writer.writerow(d)


# Rough starting point only — flagged [NEEDS REVIEW] every time, so
# precision doesn't matter much. Maps a rookie's real NFL draft round to
# how far into their position's VORP-ranked group to insert them, per
# wiki/team/rookie-evaluation.md's round/position hit-rate table (round 1
# rookies are the strongest bets, so they land higher).
_ROOKIE_ROUND_PERCENTILE: dict[int, float] = {1: 0.2, 2: 0.45, 3: 0.7}
_DEFAULT_ROOKIE_PERCENTILE = 0.7


def _insert_index_by_vorp(rows: list[BigboardRow], vorp: float) -> int:
    for i, row in enumerate(rows):
        if row.source == "vorp" and row.vorp is not None and row.vorp < vorp:
            return i
    return len(rows)


def _rookie_insert_index(rows: list[BigboardRow], rookie: TriagedRookie) -> int:
    position_indices = [
        i
        for i, row in enumerate(rows)
        if row.source == "vorp" and row.position == rookie.player.position
    ]
    if not position_indices:
        return len(rows)
    percentile = _ROOKIE_ROUND_PERCENTILE.get(
        rookie.draft_round, _DEFAULT_ROOKIE_PERCENTILE
    )
    offset = min(int(len(position_indices) * percentile), len(position_indices) - 1)
    return position_indices[offset]


def _renumber(rows: list[BigboardRow]) -> list[BigboardRow]:
    return [replace(row, rank=i) for i, row in enumerate(rows, start=1)]


def merge_bigboard(
    existing_rows: list[BigboardRow],
    vorp_df: pl.DataFrame,
    triaged_rookies: Sequence[TriagedRookie],
) -> list[BigboardRow]:
    """Mechanical half of `bigboard build` (spec §2). Never reorders or
    edits an existing row's `rank`/`rationale`/`log_ref` beyond appending a
    `[VORP CHANGED...]` flag — placement judgment (resolving that flag,
    positioning a `[NEEDS REVIEW...]` rookie) is the LLM's job, done via the
    `bigboard` skill, not this function.
    """
    existing_ids = {row.player_id for row in existing_rows}
    rows = list(existing_rows)

    vorp_by_id = {r["sleeper_id"]: r["vorp_season"] for r in vorp_df.to_dicts()}
    for i, row in enumerate(rows):
        if row.source != "vorp":
            continue
        new_vorp = vorp_by_id.get(row.player_id)
        if new_vorp is not None and row.vorp is not None and new_vorp != row.vorp:
            flag = f"[VORP CHANGED: {row.vorp:.1f} -> {new_vorp:.1f}]"
            rationale = f"{row.rationale} {flag}".strip()
            rows[i] = replace(row, vorp=new_vorp, rationale=rationale)

    new_vorp_rows = [
        r
        for r in vorp_df.sort("vorp_season", descending=True).to_dicts()
        if r["sleeper_id"] not in existing_ids
    ]
    for r in new_vorp_rows:
        insert_at = _insert_index_by_vorp(rows, r["vorp_season"])
        rows.insert(
            insert_at,
            BigboardRow(
                rank=0,
                player_id=r["sleeper_id"],
                name=r["name"],
                position=r["position"],
                source="vorp",
                vorp=r["vorp_season"],
                draft_round=None,
                rationale="",
                log_ref=None,
            ),
        )
        existing_ids.add(r["sleeper_id"])

    for rookie in triaged_rookies:
        if rookie.player.player_id in existing_ids:
            continue
        insert_at = _rookie_insert_index(rows, rookie)
        rows.insert(
            insert_at,
            BigboardRow(
                rank=0,
                player_id=rookie.player.player_id,
                name=rookie.player.name,
                position=rookie.player.position,
                source="rookie",
                vorp=None,
                draft_round=rookie.draft_round,
                rationale="[NEEDS REVIEW: new rookie placement]",
                log_ref=None,
            ),
        )
        existing_ids.add(rookie.player.player_id)

    return _renumber(rows)


def filter_off_roster(
    rows: Sequence[BigboardRow], players_df: pl.DataFrame
) -> list[BigboardRow]:
    """Drop `source="vorp"` rows for players with no current NFL team on
    record — same signal as `value.scoring.filter_rostered`, reimplemented
    here against `BigboardRow` instead of a VORP DataFrame. Never applied to
    `source="rookie"` rows: a rookie's `team` field is sourced differently
    (from the draft-picks crosswalk) and this filter was never applied to
    the old Rookie watch population either.
    """
    off_roster_ids = set(
        players_df.filter(pl.col("team").is_null() | (pl.col("team") == ""))[
            "player_id"
        ].to_list()
    )
    return [
        row
        for row in rows
        if row.source == "rookie" or row.player_id not in off_roster_ids
    ]
