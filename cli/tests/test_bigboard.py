from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from sleeper_agent.draft_tools.bigboard import (
    BigboardNotBuiltError,
    BigboardRow,
    BigboardUnresolvedRowError,
    filter_off_roster,
    load_bigboard,
    load_bigboard_for_build,
    save_bigboard,
)


def _row(**overrides) -> BigboardRow:
    base = dict(
        rank=1,
        player_id="7547",
        name="Amon-Ra St. Brown",
        position="WR",
        source="vorp",
        vorp=145.0,
        draft_round=None,
        rationale="",
        log_ref=None,
    )
    base.update(overrides)
    return BigboardRow(**base)


def test_load_bigboard_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(BigboardNotBuiltError):
        load_bigboard(tmp_path, "2026")


def test_load_bigboard_for_build_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_bigboard_for_build(tmp_path, "2026") == []


def test_save_then_load_round_trips_all_fields(tmp_path: Path) -> None:
    rows = [
        _row(rank=1, source="vorp", vorp=145.0, draft_round=None),
        _row(
            rank=2,
            player_id="9999",
            name="Rookie Player",
            position="RB",
            source="rookie",
            vorp=None,
            draft_round=2,
            rationale="placed R2",
            log_ref="2026-08-23-bigboard-initial-build",
        ),
    ]
    save_bigboard(tmp_path, "2026", rows)
    loaded = load_bigboard(tmp_path, "2026")
    assert loaded == rows


def test_load_bigboard_raises_on_needs_review_marker(tmp_path: Path) -> None:
    rows = [_row(rationale="[NEEDS REVIEW: new rookie placement]")]
    save_bigboard(tmp_path, "2026", rows)
    with pytest.raises(BigboardUnresolvedRowError) as exc_info:
        load_bigboard(tmp_path, "2026")
    assert exc_info.value.unresolved == rows


def test_load_bigboard_raises_on_vorp_changed_marker(tmp_path: Path) -> None:
    rows = [_row(rationale="[VORP CHANGED: 100.0 -> 120.0]")]
    save_bigboard(tmp_path, "2026", rows)
    with pytest.raises(BigboardUnresolvedRowError):
        load_bigboard(tmp_path, "2026")


def test_load_bigboard_for_build_does_not_raise_on_unresolved_rows(
    tmp_path: Path,
) -> None:
    rows = [_row(rationale="[NEEDS REVIEW: new rookie placement]")]
    save_bigboard(tmp_path, "2026", rows)
    assert load_bigboard_for_build(tmp_path, "2026") == rows


def test_load_bigboard_sorts_by_rank(tmp_path: Path) -> None:
    rows = [_row(rank=2, player_id="a"), _row(rank=1, player_id="b")]
    save_bigboard(tmp_path, "2026", rows)
    loaded = load_bigboard(tmp_path, "2026")
    assert [r.player_id for r in loaded] == ["b", "a"]


def test_filter_off_roster_drops_vorp_rows_with_no_nfl_team() -> None:
    rows = [
        _row(player_id="7547", source="vorp"),
        _row(player_id="9999", source="vorp"),
    ]
    players_df = pl.DataFrame(
        {"player_id": ["7547", "9999"], "team": ["DET", None]}
    )
    filtered = filter_off_roster(rows, players_df)
    assert [r.player_id for r in filtered] == ["7547"]


def test_filter_off_roster_never_drops_rookie_rows() -> None:
    rows = [_row(player_id="9999", source="rookie", vorp=None)]
    players_df = pl.DataFrame({"player_id": ["9999"], "team": [None]})
    filtered = filter_off_roster(rows, players_df)
    assert [r.player_id for r in filtered] == ["9999"]
