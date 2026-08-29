from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from sleeper_agent.draft_tools.bigboard import BigboardRow, save_bigboard
from sleeper_agent.draft_tools.bigboard_print import (
    _appendix_worthy,
    _parse_confirmed_keepers_section,
    generate_bigboard_print,
)
from sleeper_agent.sleeper_client.sync import ROSTERS_SCHEMA_VERSION, USERS_SCHEMA_VERSION


def _row(
    *,
    rank: int,
    name: str,
    position: str = "RB",
    vorp: float | None = 10.0,
    draft_round: int | None = None,
    rationale: str = "",
) -> BigboardRow:
    return BigboardRow(
        rank=rank,
        player_id=str(rank),
        name=name,
        position=position,
        source="vorp" if vorp is not None else "rookie",
        vorp=vorp,
        draft_round=draft_round,
        rationale=rationale,
        log_ref=None,
    )


def test_appendix_worthy_strips_pure_mechanical_marker() -> None:
    mechanical = (
        "[VORP RECALIBRATED 2026-08-29: shrunk to reflect position reliability; "
        "mechanically re-sorted by the new value, see some-slug.]"
    )
    assert _appendix_worthy(mechanical) == ""


def test_appendix_worthy_keeps_text_beyond_the_marker() -> None:
    mixed = (
        "[INJURY REVIEW 2026-08-27: moved up.] "
        "[VORP RECALIBRATED 2026-08-29: shrunk; mechanically re-sorted, see slug.]"
    )
    assert _appendix_worthy(mixed) == "[INJURY REVIEW 2026-08-27: moved up.]"


def test_appendix_worthy_passes_through_plain_text() -> None:
    assert _appendix_worthy("R1 rookie, clear starter.") == "R1 rookie, clear starter."


def test_parse_confirmed_keepers_section_extracts_rows() -> None:
    text = """
## Confirmed real keepers (2026-08-28)

| Roster | Kept | Cost | vs. projection |
|---|---|---|---|
| 1 | Drake Maye, Bhayshul Tuten | R7, R5 | Maye locked |
| 9 | Romeo Doubs (only) | — | **ineligible** — see caveat |
| 10 | *(none)* | — | Confirmed real pass |

## Original projection (2026-08-23), for reference

| Roster | Projected keeps |
|---|---|
| 1 | Someone else |
"""
    result = _parse_confirmed_keepers_section(text)
    assert result == {
        1: (["Drake Maye", "Bhayshul Tuten"], False),
        9: (["Romeo Doubs"], True),
    }


def test_parse_confirmed_keepers_section_missing_returns_empty() -> None:
    assert _parse_confirmed_keepers_section("# no such section here") == {}


def test_parse_confirmed_keepers_section_tolerates_annotated_roster_cell() -> None:
    # The "our own roster" row is annotated e.g. "5 (us)", not a bare number —
    # regression test for a bug where that annotation silently dropped the
    # whole row instead of just being ignored.
    text = """
## Confirmed real keepers (2026-08-28)

| Roster | Kept | Cost | vs. projection |
|---|---|---|---|
| 5 (us) | Stefon Diggs, Quinshon Judkins | R7, R8 | exact match |
"""
    result = _parse_confirmed_keepers_section(text)
    assert result == {5: (["Stefon Diggs", "Quinshon Judkins"], False)}


def _write_roster_and_user_parquet(root: Path, season: str) -> None:
    sleeper_dir = root / "data" / "sleeper"
    (sleeper_dir / "rosters").mkdir(parents=True, exist_ok=True)
    (sleeper_dir / "users").mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "roster_id": [1, 2],
            "owner_id": ["u1", "u2"],
            "schema_version": [ROSTERS_SCHEMA_VERSION, ROSTERS_SCHEMA_VERSION],
        }
    ).write_parquet(sleeper_dir / "rosters" / f"{season}.parquet")
    pl.DataFrame(
        {
            "user_id": ["u1", "u2"],
            "display_name": ["owner1", "owner2"],
            "team_name": ["Team One", None],
            "schema_version": [USERS_SCHEMA_VERSION, USERS_SCHEMA_VERSION],
        }
    ).write_parquet(sleeper_dir / "users" / f"{season}.parquet")


def test_generate_bigboard_print_end_to_end(tmp_path: Path) -> None:
    rows = [
        _row(rank=1, name="Bijan Robinson", vorp=200.0),
        _row(rank=2, name="Kept Guy", vorp=190.0, rationale=""),
        _row(
            rank=3,
            name="Reviewed Guy",
            vorp=50.0,
            rationale="[INJURY REVIEW 2026-08-27: moved up, back healthy.]",
        ),
        _row(
            rank=4,
            name="Mechanically Resorted Guy",
            vorp=40.0,
            rationale=(
                "[VORP RECALIBRATED 2026-08-29: shrunk; mechanically re-sorted, "
                "see slug.]"
            ),
        ),
        _row(rank=5, name="Rookie Guy", vorp=None, draft_round=1),
    ]
    save_bigboard(tmp_path, "2025", rows)

    wiki_dir = tmp_path / "wiki" / "league"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "projected-keepers-2026.md").write_text(
        """
## Confirmed real keepers (2026-08-28)

| Roster | Kept | Cost | vs. projection |
|---|---|---|---|
| 1 | Kept Guy | R7 | locked |
""",
        encoding="utf-8",
    )
    _write_roster_and_user_parquet(tmp_path, "2026")

    result = generate_bigboard_print(tmp_path, "2025", cutoff=10)

    assert result.out_path == tmp_path / "reports" / "bigboard-print-2026.html"
    assert result.out_path.exists()
    assert result.total_rows == 5
    assert result.printed_rows == 5
    assert result.appendix_rows == 1  # only the INJURY REVIEW row
    assert result.unmatched_keepers == []

    html = result.out_path.read_text(encoding="utf-8")
    assert '<tr class="kept">' in html
    assert "KEPT — Team One" in html
    assert "Reviewed Guy*" in html
    assert "Mechanically Resorted Guy</td>" in html  # not starred
    assert "Rd1" in html  # rookie with no vorp
    assert "Appendix: Rationale notes" in html
    assert "moved up, back healthy" in html
    # the mechanical-only rationale must not leak into the appendix
    assert "mechanically re-sorted" not in html.split("Appendix")[1]


def test_generate_bigboard_print_reports_unmatched_keeper(tmp_path: Path) -> None:
    save_bigboard(tmp_path, "2025", [_row(rank=1, name="Someone Else")])
    wiki_dir = tmp_path / "wiki" / "league"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "projected-keepers-2026.md").write_text(
        """
## Confirmed real keepers (2026-08-28)

| Roster | Kept | Cost | vs. projection |
|---|---|---|---|
| 1 | Nowhere Man | R7 | locked |
""",
        encoding="utf-8",
    )
    _write_roster_and_user_parquet(tmp_path, "2026")

    result = generate_bigboard_print(tmp_path, "2025", cutoff=10)

    assert result.unmatched_keepers == ["Nowhere Man"]


def test_generate_bigboard_print_missing_keepers_page_has_no_kept_rows(
    tmp_path: Path,
) -> None:
    save_bigboard(tmp_path, "2025", [_row(rank=1, name="Anyone")])
    result = generate_bigboard_print(tmp_path, "2025", cutoff=10)
    assert result.unmatched_keepers == []
    html = result.out_path.read_text(encoding="utf-8")
    assert 'class="kept"' not in html
    assert '<span class="kept-note">' not in html
