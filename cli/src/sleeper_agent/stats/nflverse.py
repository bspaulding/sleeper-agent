"""Thin wrappers around `nflreadpy` calls.

Each function is a thin wrapper calling into `nflreadpy` (the actively
maintained successor to the now-deprecated `nfl_data_py`), per
PROJECT_PLAN.md §10.4's closing note: `nflreadpy` makes its own HTTP calls
to hardcoded nflverse release URLs with no base-URL parameter to redirect,
so the `mock_http_server` pattern doesn't apply here. Everything downstream
of these calls is tested against a fixture DataFrame passed in directly;
each call site here is `# pragma: no cover`, validated instead by an
occasional manual run against the real library (see `stats/sync.py`'s
docstring).

`fetch_weekly_stats` renames the `passing_interceptions` column back to
`interceptions` (its name under the old `nfl_data_py`/`player_stats`
release) so `vorp.py`'s `STAT_COLUMN_TO_SCORING_KEY` mapping doesn't need to
know about the nflverse rename.

`fetch_id_crosswalk` is *not* an `nflreadpy` wrapper: `nflreadpy`'s
`load_ff_playerids` reads the same DynastyProcess `db_playerids.csv` this
previously came from via `nfl_data_py.import_ids`, so it's used directly
rather than reimplemented.
"""

from __future__ import annotations

import nflreadpy as nfl
import polars as pl


def fetch_weekly_stats(  # pragma: no cover - live nflverse call
    seasons: list[int],
) -> pl.DataFrame:
    return nfl.load_player_stats(seasons).rename(
        {"passing_interceptions": "interceptions"}
    )


def fetch_snap_counts(seasons: list[int]) -> pl.DataFrame:
    return nfl.load_snap_counts(seasons)  # pragma: no cover - live nflverse call


def fetch_schedules(seasons: list[int]) -> pl.DataFrame:
    return nfl.load_schedules(seasons)  # pragma: no cover - live nflverse call


def fetch_injuries(seasons: list[int]) -> pl.DataFrame:
    return nfl.load_injuries(seasons)  # pragma: no cover - live nflverse call


def fetch_id_crosswalk() -> pl.DataFrame:  # pragma: no cover - live nflverse call
    return nfl.load_ff_playerids().select(["name", "position", "gsis_id", "sleeper_id"])
