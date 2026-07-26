"""Combine VORP + recent-usage trend + injury status + wiki News excerpt into
a player value view (PROJECT_PLAN.md §6.3).

VORP is the quantitative backbone (`stats/vorp.py`); trend and injury are
additional CLI-computed signals from `data/stats/`; the wiki News excerpt is
where qualitative/LLM judgment plugs in — this module surfaces it, it
doesn't try to score it.

Trend uses a recent-usage metric (pass attempts / carries / targets) from
nflverse weekly stats rather than snap-count share: snap counts join via a
different ID space (`pfr_id`), and usage volume from the same weekly-stats
table already joined for VORP is a reasonably equivalent, simpler signal for
v1 — see IMPLEMENTATION_PLAN.md's Phase D deviation note.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sleeper_agent.wiki_tools.frontmatter import parse_page

POSITION_USAGE_COLUMN: dict[str, str] = {
    "QB": "attempts",
    "RB": "carries",
    "WR": "targets",
    "TE": "targets",
}

RECENT_GAMES_WINDOW = 4


@dataclass(frozen=True)
class TrendSignal:
    metric: str
    last_n_games: int
    recent_avg: float
    season_avg: float
    delta: float


@dataclass(frozen=True)
class InjuryReported:
    status: str
    primary_injury: str | None
    as_of_week: int


@dataclass(frozen=True)
class NoInjuryOnRecord:
    pass


InjuryInfo = InjuryReported | NoInjuryOnRecord


def compute_trend(player_weekly: pl.DataFrame, position: str) -> TrendSignal | None:
    metric = POSITION_USAGE_COLUMN.get(position)
    if (
        metric is None
        or metric not in player_weekly.columns
        or player_weekly.height == 0
    ):
        return None

    sorted_games = player_weekly.sort("week")
    values = sorted_games[metric].fill_null(0.0).to_list()
    season_avg = sum(values) / len(values)

    recent_n = min(RECENT_GAMES_WINDOW, len(values))
    recent_values = values[-recent_n:]
    recent_avg = sum(recent_values) / recent_n

    return TrendSignal(
        metric=metric,
        last_n_games=recent_n,
        recent_avg=recent_avg,
        season_avg=season_avg,
        delta=recent_avg - season_avg,
    )


def compute_injury(injuries: pl.DataFrame, gsis_id: str) -> InjuryInfo:
    player_reports = injuries.filter(
        (pl.col("gsis_id") == gsis_id) & pl.col("report_status").is_not_null()
    ).sort("week", descending=True)
    if player_reports.height == 0:
        return NoInjuryOnRecord()
    row = player_reports.row(0, named=True)
    return InjuryReported(
        status=row["report_status"],
        primary_injury=row.get("report_primary_injury"),
        as_of_week=row["week"],
    )


def gsis_id_for_sleeper_id(ids: pl.DataFrame, sleeper_id: str) -> str | None:
    """Reverse-lookup a gsis_id from a sleeper_id via the nflverse id crosswalk.

    `sleeper_id` is stored as a float column in nflverse's `import_ids()`
    output (it ships as a numeric ID there, unlike Sleeper's own string
    IDs) — cast explicitly rather than comparing strings to floats.
    """
    matches = ids.filter(
        pl.col("sleeper_id").is_not_null()
        & (pl.col("sleeper_id").cast(pl.Int64) == int(sleeper_id))
    )
    if matches.height == 0:
        return None
    gsis_id = matches.row(0, named=True)["gsis_id"]
    return gsis_id if gsis_id is not None else None


def find_player_wiki_page(wiki_dir: Path, sleeper_id: str) -> Path | None:
    matches = sorted((wiki_dir / "players").glob(f"{sleeper_id}-*.md"))
    return matches[0] if matches else None


def recent_news_excerpt(
    wiki_dir: Path, sleeper_id: str, *, limit: int = 3
) -> list[str]:
    page_path = find_player_wiki_page(wiki_dir, sleeper_id)
    if page_path is None or not page_path.exists():
        return []
    page = parse_page(page_path.read_text())
    lines = [
        line.strip() for line in page.body.splitlines() if line.strip().startswith("- ")
    ]
    return lines[:limit]
