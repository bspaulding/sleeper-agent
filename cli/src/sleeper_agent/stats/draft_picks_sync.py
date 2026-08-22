"""Sync `data/nfl/draft_picks.parquet` — NFL draft-capital data for rookie triage.

Mirrors `stats/sync.py`'s injectable-fetch shape (testable against fixture
polars DataFrames without touching the network). Unlike `stats/sync.py`'s
tables, the written table already carries the rookie-crosswalk `sleeper_id`
column (see `draft_tools/rookies.py::crosswalk_draft_picks_to_sleeper_ids`)
rather than a raw fetch — `triage_rookies` reads it directly with no
further join required.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sleeper_agent.draft_tools.rookies import crosswalk_draft_picks_to_sleeper_ids
from sleeper_agent.stats import nflverse
from sleeper_agent.storage.parquet_store import write_table

DRAFT_PICKS_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DraftPicksSyncResult:
    season: int
    draft_pick_rows: int


def sync_draft_picks(
    season: int,
    nfl_dir: Path,
    *,
    fetch_draft_picks: Callable[[list[int]], pl.DataFrame] = nflverse.fetch_draft_picks,
    fetch_ff_playerids: Callable[[], pl.DataFrame] = nflverse.fetch_ff_playerids,
) -> DraftPicksSyncResult:
    draft_picks_df = fetch_draft_picks([season])
    ff_playerids_df = fetch_ff_playerids()
    crosswalked = crosswalk_draft_picks_to_sleeper_ids(
        draft_picks_df, ff_playerids_df, season
    )

    write_table(
        crosswalked,
        nfl_dir / "draft_picks.parquet",
        schema_version=DRAFT_PICKS_SCHEMA_VERSION,
    )

    return DraftPicksSyncResult(season=season, draft_pick_rows=crosswalked.height)
