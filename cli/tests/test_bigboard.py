from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Literal

import polars as pl
import pytest

from sleeper_agent.draft_tools.bigboard import (
    BigboardMalformedError,
    BigboardNotBuiltError,
    BigboardRow,
    BigboardUnresolvedRowError,
    filter_off_roster,
    is_unresolved,
    load_bigboard,
    load_bigboard_for_build,
    merge_bigboard,
    save_bigboard,
)
from sleeper_agent.draft_tools.rookies import TriagedRookie
from sleeper_agent.models.sleeper import parse_player


def _row(
    *,
    rank: int = 1,
    player_id: str = "7547",
    name: str = "Amon-Ra St. Brown",
    position: str = "WR",
    source: Literal["vorp", "rookie"] = "vorp",
    vorp: float | None = 145.0,
    draft_round: int | None = None,
    rationale: str = "",
    log_ref: str | None = None,
) -> BigboardRow:
    return BigboardRow(
        rank=rank,
        player_id=player_id,
        name=name,
        position=position,
        source=source,
        vorp=vorp,
        draft_round=draft_round,
        rationale=rationale,
        log_ref=log_ref,
    )


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


# --- schema-invariant validation (spec §1) ---------------------------------


def _write_raw_csv(tmp_path: Path, season: str, body: str) -> None:
    """Write a bigboard CSV by hand, so a test can produce a value
    `save_bigboard` can't (e.g. a `source` outside the two valid literals)."""
    path = tmp_path / "data" / "bigboard" / f"{season}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "rank,player_id,name,position,source,vorp,draft_round,rationale,log_ref\n"
        + body
    )


def test_load_bigboard_raises_on_duplicate_rank(tmp_path: Path) -> None:
    # The most likely hand-edit mistake: promote a row to rank 1 and forget
    # to renumber the row that already held it.
    save_bigboard(
        tmp_path,
        "2026",
        [_row(rank=1, player_id="a"), _row(rank=1, player_id="b", name="Other Guy")],
    )
    with pytest.raises(BigboardMalformedError) as exc_info:
        load_bigboard(tmp_path, "2026")
    assert "duplicate rank(s)" in str(exc_info.value)
    assert "Other Guy" in str(exc_info.value)


def test_load_bigboard_raises_on_rank_gap(tmp_path: Path) -> None:
    save_bigboard(
        tmp_path, "2026", [_row(rank=1, player_id="a"), _row(rank=3, player_id="b")]
    )
    with pytest.raises(BigboardMalformedError) as exc_info:
        load_bigboard(tmp_path, "2026")
    assert "[2, 3]" in str(exc_info.value)


def test_load_bigboard_raises_on_unknown_source(tmp_path: Path) -> None:
    _write_raw_csv(tmp_path, "2026", "1,7547,Amon-Ra St. Brown,WR,vorpp,145.0,,,\n")
    with pytest.raises(BigboardMalformedError) as exc_info:
        load_bigboard(tmp_path, "2026")
    assert "unknown source 'vorpp'" in str(exc_info.value)
    assert "line 2" in str(exc_info.value)


def test_load_bigboard_accepts_a_well_formed_ordinal_board(tmp_path: Path) -> None:
    rows = [
        _row(rank=1, player_id="a"),
        _row(rank=2, player_id="b", source="rookie", vorp=None, draft_round=1),
        _row(rank=3, player_id="c"),
    ]
    save_bigboard(tmp_path, "2026", rows)
    assert load_bigboard(tmp_path, "2026") == rows


def test_load_bigboard_for_build_tolerates_non_ordinal_ranks(tmp_path: Path) -> None:
    # A file mid-review can transiently have duplicate/gapped ranks; `bigboard
    # build` has to be able to read it anyway, unlike the live loader.
    save_bigboard(
        tmp_path, "2026", [_row(rank=1, player_id="a"), _row(rank=1, player_id="b")]
    )
    assert [r.player_id for r in load_bigboard_for_build(tmp_path, "2026")] == [
        "a",
        "b",
    ]


def test_load_bigboard_for_build_still_raises_on_unknown_source(tmp_path: Path) -> None:
    # Unlike a mid-renumber rank, an unknown `source` isn't a transient
    # review state — there's no valid row to hand back, and merge_bigboard
    # would re-add the player as a duplicate `source="vorp"` row.
    _write_raw_csv(tmp_path, "2026", "1,7547,Amon-Ra St. Brown,WR,nonsense,145.0,,,\n")
    with pytest.raises(BigboardMalformedError):
        load_bigboard_for_build(tmp_path, "2026")


def test_bigboard_malformed_error_truncates_a_long_problem_list(
    tmp_path: Path,
) -> None:
    body = "".join(f"{i},{i},Player {i},WR,bogus,1.0,,,\n" for i in range(1, 8))
    _write_raw_csv(tmp_path, "2026", body)
    with pytest.raises(BigboardMalformedError) as exc_info:
        load_bigboard(tmp_path, "2026")
    assert "and 2 more" in str(exc_info.value)


def test_is_unresolved_matches_both_review_markers() -> None:
    assert is_unresolved(_row(rationale="[NEEDS REVIEW: new rookie placement]"))
    assert is_unresolved(_row(rationale="placed R2 [VORP CHANGED: 1.0 -> 2.0]"))
    assert not is_unresolved(_row(rationale="reviewed 2026-08-23, no change"))


def test_filter_off_roster_drops_vorp_rows_with_no_nfl_team() -> None:
    rows = [
        _row(player_id="7547", source="vorp"),
        _row(player_id="9999", source="vorp"),
    ]
    players_df = pl.DataFrame({"player_id": ["7547", "9999"], "team": ["DET", None]})
    filtered = filter_off_roster(rows, players_df)
    assert [r.player_id for r in filtered] == ["7547"]


def test_filter_off_roster_never_drops_rookie_rows() -> None:
    rows = [_row(player_id="9999", source="rookie", vorp=None)]
    players_df = pl.DataFrame({"player_id": ["9999"], "team": [None]})
    filtered = filter_off_roster(rows, players_df)
    assert [r.player_id for r in filtered] == ["9999"]


# Tests for merge_bigboard (Task 3)


def _vorp_df(*rows: tuple[str, str, str, float]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "sleeper_id": [r[0] for r in rows],
            "name": [r[1] for r in rows],
            "position": [r[2] for r in rows],
            "vorp_season": [r[3] for r in rows],
        }
    )


def _rookie(
    player_id: str, name: str, position: str, draft_round: int
) -> TriagedRookie:
    player = parse_player(
        player_id,
        {
            "player_id": player_id,
            "full_name": name,
            "position": position,
            "team": "DET",
        },
    )
    return TriagedRookie(player=player, draft_round=draft_round)


def test_merge_bigboard_inserts_new_vorp_players_by_value_order() -> None:
    vorp_df = _vorp_df(
        ("1", "Player One", "RB", 100.0),
        ("2", "Player Two", "RB", 80.0),
        ("3", "Player Three", "RB", 60.0),
    )
    merged = merge_bigboard([], vorp_df, [])
    assert [r.player_id for r in merged] == ["1", "2", "3"]
    assert [r.rank for r in merged] == [1, 2, 3]
    assert all(r.source == "vorp" for r in merged)


def test_merge_bigboard_never_touches_existing_row_rank_or_rationale() -> None:
    existing = [
        BigboardRow(
            rank=1,
            player_id="2",
            name="Player Two",
            position="RB",
            source="vorp",
            vorp=80.0,
            draft_round=None,
            rationale="existing rationale to preserve",
            log_ref="2026-08-01-bigboard-initial",
        )
    ]
    # Only update vorp for existing player, no new players
    vorp_df = _vorp_df(("2", "Player Two", "RB", 80.0))
    merged = merge_bigboard(existing, vorp_df, [])
    kept = next(r for r in merged if r.player_id == "2")
    assert kept.rank == 1
    assert kept.rationale == "existing rationale to preserve"
    assert kept.log_ref == "2026-08-01-bigboard-initial"


def test_merge_bigboard_flags_material_vorp_change_without_reordering() -> None:
    existing = [
        BigboardRow(
            rank=1,
            player_id="1",
            name="Player One",
            position="RB",
            source="vorp",
            vorp=100.0,
            draft_round=None,
            rationale="",
            log_ref=None,
        )
    ]
    vorp_df = _vorp_df(("1", "Player One", "RB", 60.0))
    merged = merge_bigboard(existing, vorp_df, [])
    assert merged[0].rank == 1
    assert "[VORP CHANGED: 100.0 -> 60.0]" in merged[0].rationale


def test_merge_bigboard_does_not_flag_unchanged_vorp() -> None:
    existing = [
        BigboardRow(
            rank=1,
            player_id="1",
            name="Player One",
            position="RB",
            source="vorp",
            vorp=100.0,
            draft_round=None,
            rationale="",
            log_ref=None,
        )
    ]
    vorp_df = _vorp_df(("1", "Player One", "RB", 100.0))
    merged = merge_bigboard(existing, vorp_df, [])
    assert merged[0].rationale == ""


def test_merge_bigboard_inserts_new_rookie_flagged_for_review() -> None:
    vorp_df = _vorp_df(
        ("1", "Vet One", "RB", 100.0),
        ("2", "Vet Two", "RB", 80.0),
        ("3", "Vet Three", "RB", 60.0),
        ("4", "Vet Four", "RB", 40.0),
        ("5", "Vet Five", "RB", 20.0),
    )
    merged = merge_bigboard([], vorp_df, [_rookie("99", "Rookie RB", "RB", 1)])
    rookie_row = next(r for r in merged if r.player_id == "99")
    assert rookie_row.source == "rookie"
    assert rookie_row.vorp is None
    assert rookie_row.draft_round == 1
    assert rookie_row.rationale == "[NEEDS REVIEW: new rookie placement]"
    # Round-1 heuristic places it near the top of its position group, not at the end.
    assert rookie_row.rank < len(merged)


def test_merge_bigboard_appends_rookie_whose_position_has_no_vorp_rows() -> None:
    # No `source="vorp"` DEF row exists to anchor the round/percentile
    # heuristic against, so the rookie must still land on the board (at the
    # end) rather than crashing or being dropped.
    vorp_df = _vorp_df(("1", "Vet One", "RB", 100.0), ("2", "Vet Two", "WR", 80.0))
    merged = merge_bigboard([], vorp_df, [_rookie("99", "Rookie DEF", "DEF", 1)])
    assert [r.player_id for r in merged] == ["1", "2", "99"]
    rookie_row = merged[-1]
    assert rookie_row.rank == 3
    assert rookie_row.position == "DEF"
    assert rookie_row.rationale == "[NEEDS REVIEW: new rookie placement]"


def test_merge_bigboard_skips_rookie_with_no_position() -> None:
    # The board is positional; there's no group to place a position-less
    # player relative to. `triage_rookies` already filters these out, so this
    # only guards a hand-built caller.
    player = parse_player("99", {"player_id": "99", "full_name": "No Position"})
    vorp_df = _vorp_df(("1", "Vet One", "RB", 100.0))
    merged = merge_bigboard([], vorp_df, [TriagedRookie(player=player, draft_round=1)])
    assert [r.player_id for r in merged] == ["1"]


def test_merge_bigboard_is_idempotent_on_rookie_already_present() -> None:
    vorp_df = _vorp_df(("1", "Vet One", "RB", 100.0))
    first = merge_bigboard([], vorp_df, [_rookie("99", "Rookie RB", "RB", 1)])
    reviewed = [
        r if r.player_id != "99" else replace(r, rationale="reviewed: kept at rank 2")
        for r in first
    ]
    second = merge_bigboard(reviewed, vorp_df, [_rookie("99", "Rookie RB", "RB", 1)])
    kept = next(r for r in second if r.player_id == "99")
    assert kept.rationale == "reviewed: kept at rank 2"


def test_merge_bigboard_renumbers_ranks_contiguously_from_one() -> None:
    vorp_df = _vorp_df(("1", "A", "RB", 100.0), ("2", "B", "RB", 80.0))
    merged = merge_bigboard([], vorp_df, [])
    assert [r.rank for r in merged] == [1, 2]


def test_merge_bigboard_shifts_existing_row_rank_when_new_row_inserted_above_it() -> (
    None
):
    existing = [
        BigboardRow(
            rank=1,
            player_id="2",
            name="Player Two",
            position="RB",
            source="vorp",
            vorp=80.0,
            draft_round=None,
            rationale="kept here deliberately, see log",
            log_ref="2026-08-01-bigboard-initial",
        )
    ]
    # New player "1" has higher vorp (100.0) than existing player "2" (80.0),
    # so it must be inserted ABOVE it -- pushing "2" from rank 1 to rank 2.
    vorp_df = _vorp_df(
        ("1", "Player One", "RB", 100.0), ("2", "Player Two", "RB", 80.0)
    )
    merged = merge_bigboard(existing, vorp_df, [])

    new_row = next(r for r in merged if r.player_id == "1")
    assert new_row.rank == 1

    shifted = next(r for r in merged if r.player_id == "2")
    assert (
        shifted.rank == 2
    )  # relabeled for contiguity, but never reordered past a neighbor
    assert shifted.rationale == "kept here deliberately, see log"  # untouched
    assert shifted.log_ref == "2026-08-01-bigboard-initial"  # untouched
    assert shifted.vorp == 80.0  # untouched (no VORP change in this test)
