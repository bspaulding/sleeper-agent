"""Orchestrates a full nflverse stats sync for a season.

The `nflreadpy` calls themselves are injected (defaulting to the thin
wrappers in `stats/nflverse.py`) so this module is testable against fixture
polars DataFrames without touching the network — see `stats/nflverse.py`'s
docstring for why that's the seam here instead of `mock_http_server`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sleeper_agent.stats import nflverse
from sleeper_agent.storage.parquet_store import write_table

WEEKLY_SCHEMA_VERSION = 1
SNAPS_SCHEMA_VERSION = 1
SCHEDULES_SCHEMA_VERSION = 1
INJURIES_SCHEMA_VERSION = 1
IDS_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class StatsSyncResult:
    season: int
    weekly_rows: int
    snap_rows: int
    schedule_rows: int
    injury_rows: int
    id_crosswalk_rows: int


def sync_stats(
    season: int,
    stats_dir: Path,
    *,
    fetch_weekly_stats: Callable[
        [list[int]], pl.DataFrame
    ] = nflverse.fetch_weekly_stats,
    fetch_snap_counts: Callable[[list[int]], pl.DataFrame] = nflverse.fetch_snap_counts,
    fetch_schedules: Callable[[list[int]], pl.DataFrame] = nflverse.fetch_schedules,
    fetch_injuries: Callable[[list[int]], pl.DataFrame] = nflverse.fetch_injuries,
    fetch_id_crosswalk: Callable[[], pl.DataFrame] = nflverse.fetch_id_crosswalk,
) -> StatsSyncResult:
    weekly_df = fetch_weekly_stats([season])
    snaps_df = fetch_snap_counts([season])
    schedules_df = fetch_schedules([season])
    injuries_df = fetch_injuries([season])
    ids_df = fetch_id_crosswalk()

    write_table(
        weekly_df,
        stats_dir / "weekly" / f"{season}.parquet",
        schema_version=WEEKLY_SCHEMA_VERSION,
    )
    write_table(
        snaps_df,
        stats_dir / "snaps" / f"{season}.parquet",
        schema_version=SNAPS_SCHEMA_VERSION,
    )
    write_table(
        schedules_df,
        stats_dir / "schedules" / f"{season}.parquet",
        schema_version=SCHEDULES_SCHEMA_VERSION,
    )
    write_table(
        injuries_df,
        stats_dir / "injuries" / f"{season}.parquet",
        schema_version=INJURIES_SCHEMA_VERSION,
    )
    write_table(ids_df, stats_dir / "ids.parquet", schema_version=IDS_SCHEMA_VERSION)

    return StatsSyncResult(
        season=season,
        weekly_rows=weekly_df.height,
        snap_rows=snaps_df.height,
        schedule_rows=schedules_df.height,
        injury_rows=injuries_df.height,
        id_crosswalk_rows=ids_df.height,
    )
