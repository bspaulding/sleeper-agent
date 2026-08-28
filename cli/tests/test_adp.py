from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from sleeper_agent.adp.draftsharks import (
    AdpBlobNotFoundError,
    AdpBlobShapeError,
    AdpEntry,
    parse_adp_html,
)
from sleeper_agent.adp.sync import (
    latest_adp_snapshot,
    match_entries_to_sleeper_ids,
    sync_adp,
)


def make_fixture_html(vue_app_data_json: str) -> str:
    return (
        "<html><body>"
        "<script>var dsCurrentWeek = 1;\n"
        f"vueAppData = {vue_app_data_json};\n"
        "</script>"
        "</body></html>"
    )


FIXTURE_JSON = """{
    "selected": {"scoring": "ppr", "sources": ["sleeper"], "size": 12},
    "seed": {
        "players": {
            "9963": {"fn": "Sam", "ln": "Darnold", "tm": "SEA", "pos": "QB"},
            "12512": {"fn": "Quinshon", "ln": "Judkins", "tm": "CLE", "pos": "RB"},
            "99999": {"fn": "Nobody", "ln": "Special}", "tm": "SF", "pos": "WR"}
        },
        "adpSets": {
            "11::107::12": [
                {"id": 9963, "pick": 175, "dsRank": 206, "posAdp": 20, "marketIndex": -31},
                {"id": 12512, "pick": 54, "dsRank": 72, "posAdp": 23, "marketIndex": -18},
                {"id": 99999, "pick": 300, "dsRank": 310, "posAdp": 90, "marketIndex": 0}
            ]
        }
    }
}"""


def test_parse_adp_html_extracts_entries_across_a_brace_in_a_string() -> None:
    html = make_fixture_html(FIXTURE_JSON)

    entries = parse_adp_html(html)

    assert len(entries) == 3
    # "Special}" embeds a literal '}' inside a JSON string value — proves the
    # brace-matcher is string-aware and didn't stop early there.
    nobody = next(e for e in entries if e.first_name == "Nobody")
    assert nobody.last_name == "Special}"

    darnold = next(e for e in entries if e.last_name == "Darnold")
    assert darnold == AdpEntry(
        ds_player_id=9963,
        first_name="Sam",
        last_name="Darnold",
        team="SEA",
        position="QB",
        adp_pick=175,
        ds_rank=206,
        pos_adp=20,
        market_index=-31,
    )


def test_parse_adp_html_raises_when_var_missing() -> None:
    with pytest.raises(AdpBlobNotFoundError):
        parse_adp_html("<html><body>no data here</body></html>")


def test_parse_adp_html_raises_on_multiple_adp_sets() -> None:
    html = make_fixture_html(
        '{"seed": {"players": {}, "adpSets": {"a": [], "b": []}}}'
    )

    with pytest.raises(AdpBlobShapeError):
        parse_adp_html(html)


def test_parse_adp_html_skips_rows_with_no_matching_player() -> None:
    html = make_fixture_html(
        '{"seed": {"players": {}, "adpSets": {"k": ['
        '{"id": 1, "pick": 1, "dsRank": 1, "posAdp": 1, "marketIndex": 0}'
        "]}}}"
    )

    assert parse_adp_html(html) == []


def _players_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "player_id": ["4943", "12512", "1"],
            "name": ["Sam Darnold", "Quinshon Judkins", "A.J. Brown"],
            "position": ["QB", "RB", "WR"],
        }
    )


def test_match_entries_to_sleeper_ids_joins_on_normalized_name_and_position() -> None:
    entries = [
        AdpEntry(9963, "Sam", "Darnold", "SEA", "QB", 175, 206, 20, -31),
        AdpEntry(20000, "Unknown", "Player", "NE", "TE", 400, 400, 40, 0),
    ]

    matched = match_entries_to_sleeper_ids(entries, _players_df())

    rows = {row["full_name"]: row["sleeper_id"] for row in matched.to_dicts()}
    assert rows["Sam Darnold"] == "4943"
    assert rows["Unknown Player"] is None


def test_match_entries_to_sleeper_ids_strips_periods_and_apostrophes() -> None:
    entries = [AdpEntry(1, "A.J.", "Brown", "NE", "WR", 18, 18, 8, 5)]

    matched = match_entries_to_sleeper_ids(entries, _players_df())

    assert matched.to_dicts()[0]["sleeper_id"] == "1"


def test_sync_adp_writes_snapshot_and_reports_unmatched(tmp_path: Path) -> None:
    adp_dir = tmp_path / "adp"

    result = sync_adp(
        adp_dir,
        _players_df(),
        retrieved_date="2026-08-28",
        fetch_html=lambda: make_fixture_html(FIXTURE_JSON),
    )

    assert result.retrieved_date == "2026-08-28"
    assert result.total_rows == 3
    assert result.matched_rows == 2
    assert result.unmatched_names == ["Nobody Special}"]

    date_str, df = latest_adp_snapshot(adp_dir)
    assert date_str == "2026-08-28"
    assert set(df["sleeper_id"].drop_nulls().to_list()) == {"4943", "12512"}


def test_latest_adp_snapshot_picks_the_max_date(tmp_path: Path) -> None:
    adp_dir = tmp_path / "adp"
    sync_adp(
        adp_dir,
        _players_df(),
        retrieved_date="2026-08-20",
        fetch_html=lambda: make_fixture_html(FIXTURE_JSON),
    )
    sync_adp(
        adp_dir,
        _players_df(),
        retrieved_date="2026-08-28",
        fetch_html=lambda: make_fixture_html(FIXTURE_JSON),
    )

    date_str, _df = latest_adp_snapshot(adp_dir)
    assert date_str == "2026-08-28"


def test_latest_adp_snapshot_returns_none_when_unsynced(tmp_path: Path) -> None:
    assert latest_adp_snapshot(tmp_path / "adp") is None
