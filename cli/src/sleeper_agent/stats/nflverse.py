"""Thin wrappers around `nfl_data_py` calls.

Each function is a single line calling into `nfl_data_py`, per
PROJECT_PLAN.md §10.4's closing note: `nfl_data_py` makes its own HTTP calls
to hardcoded GitHub release URLs with no base-URL parameter to redirect, so
the `mock_http_server` pattern doesn't apply here. Everything downstream of
these calls is tested against a fixture DataFrame passed in directly; each
call site here is `# pragma: no cover`, validated instead by an occasional
manual run against the real library (see `stats/sync.py`'s docstring).
"""

from __future__ import annotations

import nfl_data_py as nfl
import pandas as pd


def fetch_weekly_stats(seasons: list[int]) -> pd.DataFrame:
    return nfl.import_weekly_data(seasons)  # pragma: no cover - live nflverse call


def fetch_snap_counts(seasons: list[int]) -> pd.DataFrame:
    return nfl.import_snap_counts(seasons)  # pragma: no cover - live nflverse call


def fetch_schedules(seasons: list[int]) -> pd.DataFrame:
    return nfl.import_schedules(seasons)  # pragma: no cover - live nflverse call


def fetch_injuries(seasons: list[int]) -> pd.DataFrame:
    return nfl.import_injuries(seasons)  # pragma: no cover - live nflverse call


def fetch_id_crosswalk() -> pd.DataFrame:
    return nfl.import_ids(  # pragma: no cover - live nflverse call
        columns=["name", "position", "gsis_id", "sleeper_id"]
    )
