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
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import polars as pl

from sleeper_agent.config import data_dir

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
