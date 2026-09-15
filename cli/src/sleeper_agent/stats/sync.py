"""Orchestrates a full nflverse stats sync for a season.

The `nflreadpy` calls themselves are injected (defaulting to the thin
wrappers in `stats/nflverse.py`) so this module is testable against fixture
polars DataFrames without touching the network — see `stats/nflverse.py`'s
docstring for why that's the seam here instead of `mock_http_server`.

`ids.meta.json`, written next to `ids.parquet`, records `fetched_at` for
the player-id crosswalk (mirroring `players.meta.json`'s pattern for the
Sleeper player dictionary in `sleeper_client/players.py`). Unlike that
file, this one is unconditional (no TTL/skip logic) — `stats sync` always
re-fetches — it exists purely so anyone reading `ids.parquet` can tell how
current it is, since the underlying DynastyProcess CSV is fetched from
`raw.githubusercontent.com` (see `stats/nflverse.py`) rather than the
same-second-fresh `github.com/.../raw/...` URL `nflreadpy` would otherwise
use, and is cached there for up to 5 minutes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl

from sleeper_agent.stats import nflverse
from sleeper_agent.storage.parquet_store import write_table

WEEKLY_SCHEMA_VERSION = 1
SNAPS_SCHEMA_VERSION = 1
SCHEDULES_SCHEMA_VERSION = 1
INJURIES_SCHEMA_VERSION = 1
IDS_SCHEMA_VERSION = 1
TEAM_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class StatsSyncResult:
    season: int
    weekly_rows: int
    snap_rows: int
    schedule_rows: int
    injury_rows: int
    id_crosswalk_rows: int
    id_crosswalk_fetched_at: datetime
    team_rows: int


def _write_ids_meta(meta_path: Path, fetched_at: datetime) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps({"fetched_at": fetched_at.isoformat()}))


def read_ids_fetched_at(meta_path: Path) -> datetime | None:
    """`fetched_at` from `ids.meta.json`, or `None` if it hasn't been synced yet."""
    if not meta_path.exists():
        return None
    return datetime.fromisoformat(json.loads(meta_path.read_text())["fetched_at"])


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
    fetch_team_stats: Callable[[list[int]], pl.DataFrame] = nflverse.fetch_team_stats,
    now: Callable[[], datetime] = datetime.now,
) -> StatsSyncResult:
    weekly_df = fetch_weekly_stats([season])
    snaps_df = fetch_snap_counts([season])
    schedules_df = fetch_schedules([season])
    injuries_df = fetch_injuries([season])
    ids_df = fetch_id_crosswalk()
    team_df = fetch_team_stats([season])

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
    ids_fetched_at = now()
    _write_ids_meta(stats_dir / "ids.meta.json", ids_fetched_at)
    write_table(
        team_df,
        stats_dir / "team" / f"{season}.parquet",
        schema_version=TEAM_SCHEMA_VERSION,
    )

    return StatsSyncResult(
        season=season,
        weekly_rows=weekly_df.height,
        snap_rows=snaps_df.height,
        schedule_rows=schedules_df.height,
        injury_rows=injuries_df.height,
        id_crosswalk_rows=ids_df.height,
        id_crosswalk_fetched_at=ids_fetched_at,
        team_rows=team_df.height,
    )
