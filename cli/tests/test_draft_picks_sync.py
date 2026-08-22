from __future__ import annotations

from pathlib import Path

import polars as pl

from sleeper_agent.stats.draft_picks_sync import sync_draft_picks
from sleeper_agent.storage.parquet_store import read_table


def _draft_picks_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "season": [2026, 2026],
            "round": [1, 7],
            "pick": [1, 250],
            "position": ["QB", "LS"],
            "pfr_player_name": ["Fernando Mendoza", "No Match Guy"],
            "gsis_id": ["MEN516487", "ZZZ000000"],
        }
    )


def _ff_playerids_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "name": ["Fernando Mendoza"],
            "position": ["QB"],
            "gsis_id": ["00-0041562"],
            "sleeper_id": [13269],
            "draft_year": [2026],
        }
    )


def test_sync_draft_picks_writes_crosswalked_table(tmp_path: Path) -> None:
    result = sync_draft_picks(
        2026,
        tmp_path,
        fetch_draft_picks=lambda seasons: _draft_picks_df(),
        fetch_ff_playerids=lambda: _ff_playerids_df(),
    )

    assert result.season == 2026
    assert result.draft_pick_rows == 2

    out = read_table(tmp_path / "draft_picks.parquet", expected_schema_version=1)
    by_name = {row["pfr_player_name"]: row["sleeper_id"] for row in out.to_dicts()}
    assert by_name["Fernando Mendoza"] == "13269"
    assert by_name["No Match Guy"] is None
