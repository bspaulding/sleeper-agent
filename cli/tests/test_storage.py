from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from sleeper_agent.storage.parquet_store import (
    SchemaVersionMismatchError,
    read_table,
    write_table,
)


def test_write_then_read_round_trips_data(tmp_path: Path) -> None:
    df = pl.DataFrame({"player_id": ["1", "2"], "points": [10.5, 3.0]})
    path = tmp_path / "sub" / "table.parquet"

    write_table(df, path, schema_version=1)
    result = read_table(path, expected_schema_version=1)

    assert result.sort("player_id").to_dicts() == [
        {"player_id": "1", "points": 10.5},
        {"player_id": "2", "points": 3.0},
    ]


def test_read_fails_loudly_on_missing_schema_version_column(tmp_path: Path) -> None:
    path = tmp_path / "table.parquet"
    pl.DataFrame({"player_id": ["1"]}).write_parquet(path)

    with pytest.raises(SchemaVersionMismatchError):
        read_table(path, expected_schema_version=1)


def test_read_fails_loudly_on_mismatched_schema_version(tmp_path: Path) -> None:
    df = pl.DataFrame({"player_id": ["1"]})
    path = tmp_path / "table.parquet"
    write_table(df, path, schema_version=2)

    with pytest.raises(SchemaVersionMismatchError) as excinfo:
        read_table(path, expected_schema_version=1)

    assert excinfo.value.expected == 1
    assert excinfo.value.found == 2
