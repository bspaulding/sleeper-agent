from __future__ import annotations

from pathlib import Path

import polars as pl

from sleeper_agent.stats.sync import sync_stats
from sleeper_agent.storage.parquet_store import read_table


def make_df(rows: list[dict[str, object]]) -> pl.DataFrame:
    return pl.DataFrame(rows)


def test_sync_stats_writes_every_table(tmp_path: Path) -> None:
    weekly = make_df([{"player_id": "00-1", "week": 1, "fantasy_points": 12.5}])
    snaps = make_df([{"player_id": "00-1", "week": 1, "snaps": 60}])
    schedules = make_df([{"game_id": "2025_01_A_B"}])
    injuries = make_df([{"player_id": "00-1", "report_status": "Questionable"}])
    ids = make_df([{"gsis_id": "00-1", "sleeper_id": "7564", "name": "Test Player"}])

    result = sync_stats(
        2025,
        tmp_path,
        fetch_weekly_stats=lambda seasons: weekly,
        fetch_snap_counts=lambda seasons: snaps,
        fetch_schedules=lambda seasons: schedules,
        fetch_injuries=lambda seasons: injuries,
        fetch_id_crosswalk=lambda: ids,
    )

    assert result.season == 2025
    assert result.weekly_rows == 1
    assert result.snap_rows == 1
    assert result.schedule_rows == 1
    assert result.injury_rows == 1
    assert result.id_crosswalk_rows == 1

    weekly_out = read_table(
        tmp_path / "weekly" / "2025.parquet", expected_schema_version=1
    )
    assert weekly_out["player_id"].to_list() == ["00-1"]

    ids_out = read_table(tmp_path / "ids.parquet", expected_schema_version=1)
    assert ids_out["sleeper_id"].to_list() == ["7564"]
