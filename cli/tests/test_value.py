from __future__ import annotations

from pathlib import Path

import polars as pl

from sleeper_agent.value.scoring import (
    InjuryReported,
    NoInjuryOnRecord,
    compute_injury,
    compute_trend,
    filter_rostered,
    find_player_wiki_page,
    gsis_id_for_sleeper_id,
    injury_statuses,
    recent_news_excerpt,
)


def test_compute_trend_computes_recent_vs_season_average_for_targets() -> None:
    weekly = pl.DataFrame(
        {
            "week": [1, 2, 3, 4, 5],
            "targets": [2.0, 4.0, 6.0, 8.0, 10.0],
        }
    )

    trend = compute_trend(weekly, "WR")

    assert trend is not None
    assert trend.metric == "targets"
    assert trend.last_n_games == 4
    # last 4 games (2..5) average = (4+6+8+10)/4 = 7; season average = 6
    assert trend.recent_avg == 7.0
    assert trend.season_avg == 6.0
    assert trend.delta == 1.0


def test_compute_trend_uses_fewer_than_4_games_when_that_is_all_there_is() -> None:
    weekly = pl.DataFrame({"week": [1, 2], "carries": [10.0, 20.0]})

    trend = compute_trend(weekly, "RB")

    assert trend is not None
    assert trend.last_n_games == 2
    assert trend.recent_avg == 15.0
    assert trend.season_avg == 15.0
    assert trend.delta == 0.0


def test_compute_trend_returns_none_for_unmapped_position() -> None:
    weekly = pl.DataFrame({"week": [1], "attempts": [10.0]})

    assert compute_trend(weekly, "DEF") is None


def test_compute_trend_returns_none_when_no_games_played() -> None:
    weekly = pl.DataFrame({"week": [], "targets": []})

    assert compute_trend(weekly, "WR") is None


def test_compute_trend_returns_none_when_usage_column_missing() -> None:
    weekly = pl.DataFrame({"week": [1]})

    assert compute_trend(weekly, "QB") is None


def test_compute_injury_returns_most_recent_report() -> None:
    injuries = pl.DataFrame(
        {
            "gsis_id": ["00-A", "00-A", "00-B"],
            "week": [3, 5, 5],
            "report_status": ["Questionable", "Out", "Out"],
            "report_primary_injury": ["Ankle", "Knee", "Hamstring"],
            "season": [2025, 2025, 2025],
        }
    )

    injury = compute_injury(injuries, "00-A")

    assert injury == InjuryReported(
        status="Out", primary_injury="Knee", as_of_week=5, season=2025
    )


def test_compute_injury_ignores_null_report_status_rows() -> None:
    injuries = pl.DataFrame(
        {
            "gsis_id": ["00-A"],
            "week": [1],
            "report_status": [None],
            "report_primary_injury": [None],
        }
    )

    assert compute_injury(injuries, "00-A") == NoInjuryOnRecord()


def test_compute_injury_returns_no_record_for_unknown_player() -> None:
    injuries = pl.DataFrame(
        {
            "gsis_id": ["00-A"],
            "week": [1],
            "report_status": ["Out"],
            "report_primary_injury": ["Ankle"],
        }
    )

    assert compute_injury(injuries, "00-ZZZ") == NoInjuryOnRecord()


def test_injury_statuses_returns_live_sleeper_designations() -> None:
    players = pl.DataFrame(
        {
            "player_id": ["1", "2", "3", "4", "5"],
            "injury_status": ["Questionable", "PUP", None, "", "NA"],
        }
    )

    statuses = injury_statuses(players)

    # null (no designation), empty, and Sleeper's `NA` placeholder for
    # non-players (coaches etc.) carry no information — only real flags come back.
    assert statuses == {"1": "Questionable", "2": "PUP"}


def test_injury_statuses_returns_empty_for_table_without_the_column() -> None:
    players = pl.DataFrame({"player_id": ["1"], "team": ["KC"]})

    assert injury_statuses(players) == {}


def test_gsis_id_for_sleeper_id_casts_float_sleeper_id_column() -> None:
    ids = pl.DataFrame({"sleeper_id": [7564.0, None], "gsis_id": ["00-0036900", None]})

    assert gsis_id_for_sleeper_id(ids, "7564") == "00-0036900"


def test_gsis_id_for_sleeper_id_returns_none_when_not_found() -> None:
    ids = pl.DataFrame({"sleeper_id": [1.0], "gsis_id": ["00-1"]})

    assert gsis_id_for_sleeper_id(ids, "999") is None


def test_find_player_wiki_page_matches_by_sleeper_id_prefix(tmp_path: Path) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    page = players_dir / "7564-ja-marr-chase.md"
    page.write_text("---\n---\n")

    assert find_player_wiki_page(tmp_path, "7564") == page


def test_find_player_wiki_page_returns_none_when_absent(tmp_path: Path) -> None:
    assert find_player_wiki_page(tmp_path, "999") is None


def test_recent_news_excerpt_returns_up_to_limit_bulleted_lines(tmp_path: Path) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    (players_dir / "1-a.md").write_text(
        "---\n\n---\n## News\n\n- entry one\n- entry two\n- entry three\n- entry four\n"
    )

    excerpt = recent_news_excerpt(tmp_path, "1", limit=2)

    assert excerpt == ["- entry one", "- entry two"]


def test_recent_news_excerpt_returns_empty_when_page_missing(tmp_path: Path) -> None:
    assert recent_news_excerpt(tmp_path, "999") == []


def test_filter_rostered_drops_players_with_null_or_empty_team() -> None:
    vorp = pl.DataFrame(
        {
            "sleeper_id": ["1", "2", "3", "4"],
            "name": ["Rostered", "Null Team", "Empty Team", "Unknown To Players"],
            "position": ["RB", "RB", "RB", "RB"],
            "vorp_season": [10.0, 20.0, 30.0, 40.0],
        }
    )
    players = pl.DataFrame(
        {
            "player_id": ["1", "2", "3"],
            "team": ["KC", None, ""],
        }
    )

    result = filter_rostered(vorp, players)

    assert set(result["sleeper_id"].to_list()) == {"1", "4"}


def test_filter_rostered_keeps_everyone_when_no_players_are_off_roster() -> None:
    vorp = pl.DataFrame(
        {
            "sleeper_id": ["1", "2"],
            "name": ["A", "B"],
            "position": ["RB", "WR"],
            "vorp_season": [10.0, 20.0],
        }
    )
    players = pl.DataFrame({"player_id": ["1", "2"], "team": ["KC", "BUF"]})

    result = filter_rostered(vorp, players)

    assert set(result["sleeper_id"].to_list()) == {"1", "2"}
