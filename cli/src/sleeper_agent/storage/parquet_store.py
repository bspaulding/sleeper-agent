"""Read/write helpers for the parquet data store, with schema versioning.

Every table written through `write_table` carries a `schema_version` column.
`read_table` fails loudly on an unexpected version instead of silently
returning data shaped for the wrong schema.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

SCHEMA_VERSION_COLUMN = "schema_version"


class SchemaVersionMismatchError(Exception):
    def __init__(self, path: Path, expected: int, found: int | None) -> None:
        self.path = path
        self.expected = expected
        self.found = found
        super().__init__(f"{path}: expected schema_version={expected}, found={found!r}")


def write_table(df: pl.DataFrame, path: Path, *, schema_version: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    versioned = df.with_columns(pl.lit(schema_version).alias(SCHEMA_VERSION_COLUMN))
    versioned.write_parquet(path)


def read_table(path: Path, *, expected_schema_version: int) -> pl.DataFrame:
    df = pl.read_parquet(path)
    if SCHEMA_VERSION_COLUMN not in df.columns:
        raise SchemaVersionMismatchError(path, expected_schema_version, None)
    found_versions = df.get_column(SCHEMA_VERSION_COLUMN).unique().to_list()
    if found_versions != [expected_schema_version]:
        found = found_versions[0] if len(found_versions) == 1 else None
        raise SchemaVersionMismatchError(path, expected_schema_version, found)
    return df.drop(SCHEMA_VERSION_COLUMN)
