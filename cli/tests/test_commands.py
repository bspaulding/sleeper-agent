from __future__ import annotations

import argparse
import contextlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import pytest

from sleeper_agent.commands import (
    decisions_cmd,
    draft_cmd,
    freeagent_cmd,
    sleeper_cmd,
    stats_cmd,
    value_cmd,
    waiver_cmd,
    wiki_cmd,
)
from sleeper_agent.main import main
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.storage.parquet_store import read_table
from tests.support.mock_http import Request, Response, mock_http_server

FIXTURES = Path(__file__).parent / "fixtures" / "sleeper"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_bytes())


def json_response(payload: object) -> Response:
    return Response(
        status=200,
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload).encode(),
    )


def make_repo_root(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


# --- argparse wiring -----------------------------------------------------


def test_sleeper_and_stats_subcommands_are_registered() -> None:
    from sleeper_agent.main import build_parser

    parser = build_parser()
    args = parser.parse_args(["sleeper", "league", "resolve", "--season", "2026"])

    assert args.func is sleeper_cmd.cmd_league_resolve
    assert args.season == "2026"
    assert args.user == sleeper_cmd.DEFAULT_USERNAME


def test_stats_vorp_subcommand_is_registered() -> None:
    from sleeper_agent.main import build_parser

    parser = build_parser()
    args = parser.parse_args(["stats", "vorp", "--season", "2025"])

    assert args.func is stats_cmd.cmd_stats_vorp
    assert args.season == 2025


# --- sleeper league resolve ----------------------------------------------


def test_cmd_league_resolve_prints_resolved_league(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def handler(request: Request) -> Response:
        if request.path == "/user/yellldarb":
            return json_response({"user_id": "u1"})
        return json_response([{"league_id": "abc"}])

    args = argparse.Namespace(season="2026", user="yellldarb")
    with mock_http_server(handler) as base_url:
        exit_code = sleeper_cmd.cmd_league_resolve(args, base_url=base_url)

    assert exit_code == 0
    assert "league_id=abc season=2026" in capsys.readouterr().out


def test_cmd_league_resolve_prints_fallback_notice(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def handler(request: Request) -> Response:
        if request.path == "/user/yellldarb":
            return json_response({"user_id": "u1"})
        if request.path == "/user/u1/leagues/nfl/2026":
            return json_response([])
        return json_response([{"league_id": "prior"}])

    args = argparse.Namespace(season="2026", user="yellldarb")
    with mock_http_server(handler) as base_url:
        exit_code = sleeper_cmd.cmd_league_resolve(args, base_url=base_url)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "fell back to season 2025" in out
    assert "league_id=prior" in out


# --- sleeper league sync ---------------------------------------------------


def test_cmd_league_sync_writes_tables_and_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    league_payload = load_fixture("league.json")
    rosters_payload = load_fixture("rosters.json")
    users_payload = load_fixture("users.json")
    draft_picks_payload = load_fixture("draft_picks.json")

    def handler(request: Request) -> Response:
        if request.path == "/league/1180391690551980032":
            return json_response(league_payload)
        if request.path == "/league/1180391690551980032/rosters":
            return json_response(rosters_payload)
        if request.path == "/league/1180391690551980032/users":
            return json_response(users_payload)
        if request.path.startswith("/league/1180391690551980032/transactions/"):
            return json_response([])
        if request.path == "/draft/1180391690551980033/picks":
            return json_response(draft_picks_payload)
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(league_id="1180391690551980032", season="2025")
    repo_root = make_repo_root(tmp_path)
    with mock_http_server(handler) as base_url:
        exit_code = sleeper_cmd.cmd_league_sync(
            args, repo_root=repo_root, base_url=base_url
        )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "synced league 1180391690551980032 season 2025" in out
    assert (repo_root / "data" / "sleeper" / "league" / "2025.parquet").exists()


# --- sleeper players sync --------------------------------------------------


def test_cmd_players_sync_prints_performed_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def handler(request: Request) -> Response:
        return json_response(
            {"1": {"player_id": "1", "first_name": "A", "last_name": "B"}}
        )

    args = argparse.Namespace(force=False)
    repo_root = make_repo_root(tmp_path)
    with mock_http_server(handler) as base_url:
        exit_code = sleeper_cmd.cmd_players_sync(
            args, repo_root=repo_root, base_url=base_url
        )

    assert exit_code == 0
    assert "synced 1 players" in capsys.readouterr().out


def test_cmd_players_sync_prints_skipped_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    meta_path = repo_root / "data" / "sleeper" / "players.meta.json"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text(json.dumps({"fetched_at": "2026-07-26T00:00:00"}))

    def failing_handler(request: Request) -> Response:
        raise AssertionError("should not fetch")

    args = argparse.Namespace(force=False)
    with mock_http_server(failing_handler) as base_url:
        exit_code = sleeper_cmd.cmd_players_sync(
            args, repo_root=repo_root, base_url=base_url
        )

    assert exit_code == 0
    assert "skipped" in capsys.readouterr().out


# --- sleeper roster show ---------------------------------------------------


def _write_roster_and_players(repo_root: Path, season: str) -> None:
    import polars as pl

    from sleeper_agent.models.sleeper import Roster
    from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    sleeper_dir = repo_root / "data" / "sleeper"
    roster = Roster(
        roster_id=5,
        owner_id="u1",
        league_id="lid",
        player_ids=("7564", "9999"),
        starter_ids=("7564",),
        wins=6,
        losses=7,
        ties=0,
        points_for=1701.0,
        waiver_budget_used=37,
    )
    write_table(
        sleeper_sync.rosters_to_dataframe([roster]),
        sleeper_dir / "rosters" / f"{season}.parquet",
        schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
    )
    players_df = pl.DataFrame(
        {
            "player_id": ["7564"],
            "name": ["Ja'Marr Chase"],
            "position": ["WR"],
            "team": ["CIN"],
            "status": ["Active"],
            "injury_status": [""],
            "fantasy_positions": [["WR"]],
            "years_exp": [4],
        }
    )
    write_table(
        players_df,
        sleeper_dir / "players.parquet",
        schema_version=PLAYERS_SCHEMA_VERSION,
    )


def test_cmd_roster_show_me_prints_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_roster_and_players(repo_root, "2025")

    args = argparse.Namespace(season="2025", roster_id=None, me=True)
    exit_code = sleeper_cmd.cmd_roster_show(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "roster_id=5 record=6-7-0" in out
    assert "Ja'Marr Chase" in out
    assert "9999" in out  # unmapped id falls back to the raw id


def test_cmd_roster_show_reports_missing_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_roster_and_players(repo_root, "2025")

    args = argparse.Namespace(season="2025", roster_id=99, me=False)
    exit_code = sleeper_cmd.cmd_roster_show(args, repo_root=repo_root)

    assert exit_code == 1
    assert "no roster found with roster_id=99" in capsys.readouterr().out


# --- sleeper trending -------------------------------------------------------


def test_cmd_trending_prints_each_entry(capsys: pytest.CaptureFixture[str]) -> None:
    def handler(request: Request) -> Response:
        assert "trending/drop" in request.path
        return json_response([{"player_id": "1", "count": 5}])

    args = argparse.Namespace(type="drop", hours=12)
    with mock_http_server(handler) as base_url:
        exit_code = sleeper_cmd.cmd_trending(args, base_url=base_url)

    assert exit_code == 0
    assert "1\t5" in capsys.readouterr().out


# --- stats sync / vorp ------------------------------------------------------


def test_cmd_stats_sync_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from sleeper_agent.stats.sync import StatsSyncResult

    repo_root = make_repo_root(tmp_path)

    def fake_sync_stats(season: int, stats_dir: Path) -> StatsSyncResult:
        return StatsSyncResult(
            season=season,
            weekly_rows=1,
            snap_rows=1,
            schedule_rows=1,
            injury_rows=1,
            id_crosswalk_rows=1,
        )

    args = argparse.Namespace(season=2025)
    exit_code = stats_cmd.cmd_stats_sync(
        args, repo_root=repo_root, sync_stats=fake_sync_stats
    )

    assert exit_code == 0
    assert "synced stats for 2025" in capsys.readouterr().out


def test_cmd_stats_vorp_raises_clear_error_when_league_not_synced(
    tmp_path: Path,
) -> None:
    repo_root = make_repo_root(tmp_path)
    args = argparse.Namespace(season=2025)

    with pytest.raises(stats_cmd.LeagueNotSyncedError):
        stats_cmd.cmd_stats_vorp(args, repo_root=repo_root)


def test_cmd_stats_vorp_writes_table_and_prints_top_players(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    sleeper_dir = repo_root / "data" / "sleeper"
    stats_dir = repo_root / "data" / "stats"

    from sleeper_agent.models.sleeper import League, LeagueSettings

    league = League(
        league_id="lid",
        name="Only Gold",
        season="2025",
        status="complete",
        previous_league_id=None,
        draft_id="did",
        scoring_settings={"rush_yd": 0.1, "rush_td": 6.0},
        roster_positions=("QB", "RB", "WR", "TE"),
        settings=LeagueSettings(
            waiver_budget=100,
            trade_deadline=11,
            max_keepers=2,
            playoff_week_start=14,
            num_teams=1,
            waiver_type=2,
            best_ball=True,
        ),
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        sleeper_sync.league_to_dataframe(league),
        sleeper_dir / "league" / "2025.parquet",
        schema_version=sleeper_sync.LEAGUE_SCHEMA_VERSION,
    )

    weekly = pd.DataFrame(
        [
            {
                "player_id": "00-A",
                "player_display_name": "Runner A",
                "position": "RB",
                "week": 1,
                "rushing_yards": 100.0,
                "rushing_tds": 1.0,
            },
            {
                "player_id": "00-B",
                "player_display_name": "Runner B",
                "position": "RB",
                "week": 1,
                "rushing_yards": 20.0,
                "rushing_tds": 0.0,
            },
        ]
    )
    ids = pd.DataFrame({"gsis_id": ["00-A", "00-B"], "sleeper_id": ["101", "102"]})

    import polars as pl

    from sleeper_agent.stats.sync import IDS_SCHEMA_VERSION, WEEKLY_SCHEMA_VERSION

    write_table(
        pl.from_pandas(weekly),
        stats_dir / "weekly" / "2025.parquet",
        schema_version=WEEKLY_SCHEMA_VERSION,
    )
    write_table(
        pl.from_pandas(ids),
        stats_dir / "ids.parquet",
        schema_version=IDS_SCHEMA_VERSION,
    )

    args = argparse.Namespace(season=2025)
    exit_code = stats_cmd.cmd_stats_vorp(args, repo_root=repo_root)

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Runner A" in out
    vorp_df = read_table(
        repo_root / "data" / "vorp" / "2025.parquet", expected_schema_version=1
    )
    assert set(vorp_df["sleeper_id"].to_list()) == {"101", "102"}


def test_main_dispatches_registered_handler(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)
    with contextlib.chdir(repo_root), pytest.raises(stats_cmd.LeagueNotSyncedError):
        main(["stats", "vorp", "--season", "2099"])


# --- wiki --------------------------------------------------------------


def _write_players_parquet(sleeper_dir: Path) -> None:
    import polars as pl

    from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    df = pl.DataFrame(
        {
            "player_id": ["1", "2"],
            "name": ["Player One", "Player Two"],
            "position": ["WR", "RB"],
            "team": ["BUF", "KC"],
            "status": ["Active", "Active"],
            "injury_status": ["", ""],
            "fantasy_positions": [["WR"], ["RB"]],
            "years_exp": [3, 5],
        }
    )
    write_table(
        df, sleeper_dir / "players.parquet", schema_version=PLAYERS_SCHEMA_VERSION
    )


def test_cmd_wiki_scaffold_players_for_one_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from sleeper_agent.models.sleeper import Roster
    from sleeper_agent.storage.parquet_store import write_table

    repo_root = make_repo_root(tmp_path)
    sleeper_dir = repo_root / "data" / "sleeper"
    _write_players_parquet(sleeper_dir)
    roster = Roster(
        roster_id=5,
        owner_id="u1",
        league_id="lid",
        player_ids=("1",),
        starter_ids=(),
        wins=0,
        losses=0,
        ties=0,
        points_for=0.0,
        waiver_budget_used=0,
    )
    write_table(
        sleeper_sync.rosters_to_dataframe([roster]),
        sleeper_dir / "rosters" / "2025.parquet",
        schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
    )

    args = argparse.Namespace(season="2025", roster_id=5, all_rostered=False)
    exit_code = wiki_cmd.cmd_wiki_scaffold_players(args, repo_root=repo_root)

    assert exit_code == 0
    assert "created 1 player page(s)" in capsys.readouterr().out
    assert (repo_root / "wiki" / "players" / "1-player-one.md").exists()
    assert not (repo_root / "wiki" / "players" / "2-player-two.md").exists()


def test_cmd_wiki_scaffold_players_all_rostered_dedupes_shared_players(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from sleeper_agent.models.sleeper import Roster
    from sleeper_agent.storage.parquet_store import write_table

    repo_root = make_repo_root(tmp_path)
    sleeper_dir = repo_root / "data" / "sleeper"
    _write_players_parquet(sleeper_dir)
    rosters = [
        Roster(
            roster_id=1,
            owner_id="u1",
            league_id="lid",
            player_ids=("1", "2"),
            starter_ids=(),
            wins=0,
            losses=0,
            ties=0,
            points_for=0.0,
            waiver_budget_used=0,
        ),
        Roster(
            roster_id=2,
            owner_id="u2",
            league_id="lid",
            player_ids=("2",),
            starter_ids=(),
            wins=0,
            losses=0,
            ties=0,
            points_for=0.0,
            waiver_budget_used=0,
        ),
    ]
    write_table(
        sleeper_sync.rosters_to_dataframe(rosters),
        sleeper_dir / "rosters" / "2025.parquet",
        schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
    )

    args = argparse.Namespace(season="2025", roster_id=None, all_rostered=True)
    exit_code = wiki_cmd.cmd_wiki_scaffold_players(args, repo_root=repo_root)

    assert exit_code == 0
    assert "created 2 player page(s)" in capsys.readouterr().out
    assert (repo_root / "wiki" / "players" / "1-player-one.md").exists()
    assert (repo_root / "wiki" / "players" / "2-player-two.md").exists()


def test_cmd_wiki_scaffold_teams(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    args = argparse.Namespace()

    exit_code = wiki_cmd.cmd_wiki_scaffold_teams(args, repo_root=repo_root)

    assert exit_code == 0
    assert "created 32 team page(s)" in capsys.readouterr().out


def test_cmd_wiki_stale_scoped_to_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from sleeper_agent.models.sleeper import Roster
    from sleeper_agent.storage.parquet_store import write_table

    repo_root = make_repo_root(tmp_path)
    wiki_dir_path = repo_root / "wiki"
    (wiki_dir_path / "players").mkdir(parents=True)
    (wiki_dir_path / "players" / "1-a.md").write_text(
        "---\nlast_researched: null\n---\n"
    )
    (wiki_dir_path / "players" / "2-b.md").write_text(
        "---\nlast_researched: null\n---\n"
    )
    (wiki_dir_path / "nfl-teams").mkdir()
    (wiki_dir_path / "nfl-teams" / "BUF.md").write_text(
        "---\nlast_researched: null\n---\n"
    )

    sleeper_dir = repo_root / "data" / "sleeper"
    roster = Roster(
        roster_id=5,
        owner_id="u1",
        league_id="lid",
        player_ids=("1",),
        starter_ids=(),
        wins=0,
        losses=0,
        ties=0,
        points_for=0.0,
        waiver_budget_used=0,
    )
    write_table(
        sleeper_sync.rosters_to_dataframe([roster]),
        sleeper_dir / "rosters" / "2025.parquet",
        schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
    )

    args = argparse.Namespace(days=7, roster_id=None, me=True, season="2025")
    exit_code = wiki_cmd.cmd_wiki_stale(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "1-a.md" in out
    assert "2-b.md" not in out
    assert "BUF.md" in out


def test_cmd_wiki_stale_unscoped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    (repo_root / "wiki" / "players").mkdir(parents=True)
    (repo_root / "wiki" / "players" / "1-a.md").write_text(
        "---\nlast_researched: null\n---\n"
    )

    args = argparse.Namespace(days=7, roster_id=None, me=False, season=None)
    exit_code = wiki_cmd.cmd_wiki_stale(args, repo_root=repo_root)

    assert exit_code == 0
    assert "1-a.md" in capsys.readouterr().out


# --- decisions -----------------------------------------------------------


def test_cmd_decisions_new_and_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)

    new_args = argparse.Namespace(kind="waiver", slug="test-slug", season="2026")
    exit_code = decisions_cmd.cmd_decisions_new(new_args, repo_root=repo_root)
    assert exit_code == 0
    created_line = capsys.readouterr().out
    assert "created" in created_line

    index_args = argparse.Namespace()
    exit_code = decisions_cmd.cmd_decisions_index(index_args, repo_root=repo_root)
    assert exit_code == 0
    assert "wrote" in capsys.readouterr().out
    assert (repo_root / "wiki" / "decisions.md").exists()


# --- value ---------------------------------------------------------------


def _write_value_fixtures(repo_root: Path, season: str) -> None:
    from sleeper_agent.models.sleeper import Roster
    from sleeper_agent.storage.parquet_store import write_table

    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["101", "102"],
            "name": ["Runner A", "Runner B"],
            "position": ["RB", "RB"],
            "games_played": [2, 2],
            "season_points": [32.0, 10.0],
            "points_per_game": [16.0, 5.0],
            "replacement_points": [10.0, 10.0],
            "vorp_season": [22.0, 0.0],
            "vorp_per_game": [11.0, 0.0],
        }
    )
    write_table(
        vorp_df, repo_root / "data" / "vorp" / f"{season}.parquet", schema_version=1
    )

    stats_dir = repo_root / "data" / "stats"
    ids_df = pl.DataFrame({"sleeper_id": [101.0, 102.0], "gsis_id": ["00-A", "00-B"]})
    write_table(ids_df, stats_dir / "ids.parquet", schema_version=1)

    weekly_df = pl.DataFrame(
        {
            "player_id": ["00-A", "00-A"],
            "week": [1, 2],
            "carries": [10.0, 12.0],
        }
    )
    write_table(weekly_df, stats_dir / "weekly" / f"{season}.parquet", schema_version=1)

    injuries_df = pl.DataFrame(
        {
            "gsis_id": ["00-A"],
            "week": [2],
            "report_status": ["Questionable"],
            "report_primary_injury": ["Ankle"],
        }
    )
    write_table(
        injuries_df, stats_dir / "injuries" / f"{season}.parquet", schema_version=1
    )

    wiki_players_dir = repo_root / "wiki" / "players"
    wiki_players_dir.mkdir(parents=True)
    (wiki_players_dir / "101-runner-a.md").write_text(
        "---\n\n---\n## News\n\n- runner A update\n"
    )

    roster = Roster(
        roster_id=5,
        owner_id="u1",
        league_id="lid",
        player_ids=("101", "102", "BUF"),
        starter_ids=(),
        wins=0,
        losses=0,
        ties=0,
        points_for=0.0,
        waiver_budget_used=0,
    )
    write_table(
        sleeper_sync.rosters_to_dataframe([roster]),
        repo_root / "data" / "sleeper" / "rosters" / f"{season}.parquet",
        schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
    )


def test_cmd_value_player_prints_full_valuation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")

    args = argparse.Namespace(sleeper_id="101", season="2025")
    exit_code = value_cmd.cmd_value_player(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Runner A (RB)" in out
    assert "VORP: season=22.0" in out
    assert "Trend (carries)" in out
    assert "Injury: Questionable (Ankle) as of week 2" in out
    assert "runner A update" in out


def test_cmd_value_player_reports_missing_player(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")

    args = argparse.Namespace(sleeper_id="999", season="2025")
    exit_code = value_cmd.cmd_value_player(args, repo_root=repo_root)

    assert exit_code == 1
    assert "no VORP data" in capsys.readouterr().out


def test_cmd_value_player_handles_player_with_no_injury_or_news(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")

    args = argparse.Namespace(sleeper_id="102", season="2025")
    exit_code = value_cmd.cmd_value_player(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Injury: none on record" in out
    assert "Recent news: none filed" in out
    assert "Trend: not available" in out


def test_cmd_value_rank_filters_by_position_and_limits_top_n(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")

    args = argparse.Namespace(season="2025", position="RB", top=1)
    exit_code = value_cmd.cmd_value_rank(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Runner A" in out
    assert "Runner B" not in out


def test_cmd_value_rank_without_position_filter_includes_all_positions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")

    args = argparse.Namespace(season="2025", position=None, top=20)
    exit_code = value_cmd.cmd_value_rank(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Runner A" in out
    assert "Runner B" in out


def test_cmd_value_roster_prints_positional_breakdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")

    args = argparse.Namespace(season="2025", roster_id=None, me=True)
    exit_code = value_cmd.cmd_value_roster(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "roster_id=5" in out
    assert "RB  n=2 total_vorp=" in out
    assert "no VORP data for: BUF" in out


def test_cmd_value_roster_omits_unranked_note_when_fully_covered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from sleeper_agent.models.sleeper import Roster
    from sleeper_agent.storage.parquet_store import write_table

    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")
    # Overwrite the roster fixture so every player_id is one with VORP data.
    roster = Roster(
        roster_id=5,
        owner_id="u1",
        league_id="lid",
        player_ids=("101", "102"),
        starter_ids=(),
        wins=0,
        losses=0,
        ties=0,
        points_for=0.0,
        waiver_budget_used=0,
    )
    write_table(
        sleeper_sync.rosters_to_dataframe([roster]),
        repo_root / "data" / "sleeper" / "rosters" / "2025.parquet",
        schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
    )

    args = argparse.Namespace(season="2025", roster_id=None, me=True)
    exit_code = value_cmd.cmd_value_roster(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "no VORP data for" not in out


def test_cmd_value_roster_reports_missing_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")

    args = argparse.Namespace(season="2025", roster_id=999, me=False)
    exit_code = value_cmd.cmd_value_roster(args, repo_root=repo_root)

    assert exit_code == 1
    assert "no roster found" in capsys.readouterr().out


def test_cmd_value_rank_raises_clear_error_when_vorp_not_computed(
    tmp_path: Path,
) -> None:
    repo_root = make_repo_root(tmp_path)
    args = argparse.Namespace(season="2099", position=None, top=20)

    with pytest.raises(value_cmd.VorpNotComputedError):
        value_cmd.cmd_value_rank(args, repo_root=repo_root)


# --- draft -----------------------------------------------------------------


def _write_draft_keeper_fixtures(repo_root: Path) -> None:
    from sleeper_agent.models.sleeper import DraftPick, Roster
    from sleeper_agent.storage.parquet_store import write_table

    roster = Roster(
        roster_id=5,
        owner_id="u1",
        league_id="lid",
        player_ids=("101", "102", "103", "104"),
        starter_ids=(),
        wins=0,
        losses=0,
        ties=0,
        points_for=0.0,
        waiver_budget_used=0,
    )
    write_table(
        sleeper_sync.rosters_to_dataframe([roster]),
        repo_root / "data" / "sleeper" / "rosters" / "2025.parquet",
        schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
    )

    picks_2025 = [
        DraftPick(
            draft_id="did",
            round=4,
            pick_no=40,
            draft_slot=1,
            roster_id=5,
            player_id="101",
            is_keeper=False,
            picked_by="u1",
            player_name="Runner A",
            player_position="RB",
        ),
        DraftPick(
            draft_id="did",
            round=1,
            pick_no=1,
            draft_slot=1,
            roster_id=5,
            player_id="102",
            is_keeper=False,
            picked_by="u1",
            player_name="Runner B",
            player_position="RB",
        ),
        DraftPick(
            draft_id="did",
            round=2,
            pick_no=20,
            draft_slot=1,
            roster_id=5,
            player_id="103",
            is_keeper=True,
            picked_by="u1",
            player_name="Runner C",
            player_position="RB",
        ),
    ]
    write_table(
        sleeper_sync.draft_picks_to_dataframe(picks_2025),
        repo_root / "data" / "sleeper" / "drafts" / "2025.parquet",
        schema_version=sleeper_sync.DRAFTS_SCHEMA_VERSION,
    )
    picks_2024 = [
        DraftPick(
            draft_id="did24",
            round=3,
            pick_no=30,
            draft_slot=1,
            roster_id=5,
            player_id="103",
            is_keeper=True,
            picked_by="u1",
            player_name="Runner C",
            player_position="RB",
        ),
    ]
    write_table(
        sleeper_sync.draft_picks_to_dataframe(picks_2024),
        repo_root / "data" / "sleeper" / "drafts" / "2024.parquet",
        schema_version=sleeper_sync.DRAFTS_SCHEMA_VERSION,
    )
    # 104 has no draft history at all on record (e.g. picked up as a
    # rookie free agent) — exercises KeeperEligibleUndraftedDefault.

    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["101", "102"],
            "name": ["Runner A", "Runner B"],
            "position": ["RB", "RB"],
            "games_played": [10, 10],
            "season_points": [100.0, 50.0],
            "points_per_game": [10.0, 5.0],
            "replacement_points": [10.0, 10.0],
            "vorp_season": [90.0, 40.0],
            "vorp_per_game": [9.0, 4.0],
        }
    )
    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)


def test_cmd_draft_keepers_prints_eligible_and_ineligible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_draft_keeper_fixtures(repo_root)

    args = argparse.Namespace(season="2026", roster_id=None, me=True, value_season=None)
    exit_code = draft_cmd.cmd_draft_keepers(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "ELIGIBLE  Runner A" in out
    assert "cost=R3" in out
    assert "ineligible Runner B" in out  # round 1 -> cost would be R0
    assert "kept 2 consecutive seasons already" in out  # Runner C
    assert "defaulted to last round" in out  # 104, cost=R15
    assert out.index("Runner A") < out.index("Runner B")  # eligible ranked first


def test_cmd_draft_keepers_shows_n_a_value_when_value_season_has_no_vorp_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_draft_keeper_fixtures(repo_root)

    args = argparse.Namespace(
        season="2026", roster_id=None, me=True, value_season="2099"
    )
    exit_code = draft_cmd.cmd_draft_keepers(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "vorp=n/a" in out


def test_cmd_draft_keepers_reports_missing_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_draft_keeper_fixtures(repo_root)

    args = argparse.Namespace(season="2026", roster_id=999, me=False, value_season=None)
    exit_code = draft_cmd.cmd_draft_keepers(args, repo_root=repo_root)

    assert exit_code == 1
    assert "no roster found" in capsys.readouterr().out


def _league_payload(draft_id: str | None = "did1") -> dict[str, object]:
    return {
        "league_id": "lid1",
        "name": "Test League",
        "season": "2025",
        "status": "in_season",
        "previous_league_id": None,
        "draft_id": draft_id,
        "scoring_settings": {},
        "roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "FLEX", "DEF", "BN"],
        "settings": {"num_teams": 12},
    }


def test_cmd_draft_board_prints_available_players(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1", "2"],
            "name": ["A", "B"],
            "position": ["RB", "WR"],
            "vorp_season": [50.0, 30.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1", rounds=15, watch=False, value_season=None
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Best available by value:" in out
    assert "A" in out


def test_cmd_draft_board_reports_missing_vorp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)

    def handler(request: Request) -> Response:
        return json_response(_league_payload())

    args = argparse.Namespace(
        league_id="lid1", rounds=15, watch=False, value_season=None
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    assert exit_code == 1
    assert "no VORP data" in capsys.readouterr().out


def test_cmd_draft_board_reports_missing_draft_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        pl.DataFrame(
            {
                "sleeper_id": ["1"],
                "name": ["A"],
                "position": ["RB"],
                "vorp_season": [1.0],
            }
        ),
        repo_root / "data" / "vorp" / "2025.parquet",
        schema_version=1,
    )

    def handler(request: Request) -> Response:
        return json_response(_league_payload(draft_id=None))

    args = argparse.Namespace(
        league_id="lid1", rounds=15, watch=False, value_season=None
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    assert exit_code == 1
    assert "has no draft_id" in capsys.readouterr().out


def test_cmd_draft_board_watch_writes_decision_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        pl.DataFrame(
            {
                "sleeper_id": ["1"],
                "name": ["A"],
                "position": ["RB"],
                "vorp_season": [1.0],
            }
        ),
        repo_root / "data" / "vorp" / "2025.parquet",
        schema_version=1,
    )

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1", rounds=15, watch=True, value_season=None
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args,
            repo_root=repo_root,
            base_url=base_url,
            today=lambda: date(2026, 7, 26),
            max_watch_iterations=1,
        )

    assert exit_code == 0
    log_path = repo_root / "decisions" / "2025" / "2026-07-26-draft-live.md"
    assert log_path.exists()


# --- waiver / freeagent ------------------------------------------------


def _write_waiver_freeagent_fixtures(repo_root: Path) -> None:
    from sleeper_agent.models.sleeper import League, LeagueSettings, Roster
    from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    sleeper_dir = repo_root / "data" / "sleeper"

    rosters = [
        Roster(
            roster_id=5,
            owner_id="u1",
            league_id="lid",
            player_ids=("1",),
            starter_ids=(),
            wins=0,
            losses=0,
            ties=0,
            points_for=0.0,
            waiver_budget_used=30,
        ),
        Roster(
            roster_id=6,
            owner_id="u2",
            league_id="lid",
            player_ids=("2",),
            starter_ids=(),
            wins=0,
            losses=0,
            ties=0,
            points_for=0.0,
            waiver_budget_used=0,
        ),
    ]
    write_table(
        sleeper_sync.rosters_to_dataframe(rosters),
        sleeper_dir / "rosters" / "2025.parquet",
        schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
    )

    league = League(
        league_id="lid",
        name="Test League",
        season="2025",
        status="in_season",
        previous_league_id=None,
        draft_id="did",
        scoring_settings={},
        roster_positions=("QB", "RB", "WR", "TE", "FLEX", "DEF"),
        settings=LeagueSettings(
            waiver_budget=100,
            trade_deadline=11,
            max_keepers=2,
            playoff_week_start=14,
            num_teams=12,
            waiver_type=2,
            best_ball=True,
        ),
    )
    write_table(
        sleeper_sync.league_to_dataframe(league),
        sleeper_dir / "league" / "2025.parquet",
        schema_version=sleeper_sync.LEAGUE_SCHEMA_VERSION,
    )

    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1", "2", "3"],
            "name": ["Weak RB", "Good WR", "Free RB"],
            "position": ["RB", "WR", "RB"],
            "games_played": [10, 10, 10],
            "season_points": [10.0, 100.0, 40.0],
            "points_per_game": [1.0, 10.0, 4.0],
            "replacement_points": [20.0, 50.0, 20.0],
            "vorp_season": [-10.0, 50.0, 20.0],
            "vorp_per_game": [-1.0, 5.0, 2.0],
        }
    )
    write_table(vorp_df, repo_root / "data" / "vorp" / "2024.parquet", schema_version=1)

    players_df = pl.DataFrame(
        {
            "player_id": ["1", "2", "3"],
            "name": ["Weak RB", "Good WR", "Free RB"],
            "position": ["RB", "WR", "RB"],
            "team": ["BUF", "KC", "MIA"],
            "status": ["Active", "Active", "Active"],
            "injury_status": ["", "", ""],
            "fantasy_positions": [["RB"], ["WR"], ["RB"]],
            "years_exp": [1, 2, 3],
        }
    )
    write_table(
        players_df,
        sleeper_dir / "players.parquet",
        schema_version=PLAYERS_SCHEMA_VERSION,
    )


def test_cmd_waiver_recommend_prints_ranked_targets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_waiver_freeagent_fixtures(repo_root)

    def handler(request: Request) -> Response:
        assert "trending/add" in request.path
        return json_response([{"player_id": "3", "count": 40}])

    args = argparse.Namespace(
        season="2025",
        value_season=None,
        roster_id=None,
        me=True,
        budget_remaining=None,
        weeks_remaining=10,
        hours=24,
        top=10,
    )
    with mock_http_server(handler) as base_url:
        exit_code = waiver_cmd.cmd_waiver_recommend(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "FAAB budget remaining: 70" in out  # 100 - 30
    assert "Free RB" in out


def test_cmd_waiver_recommend_reports_missing_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_waiver_freeagent_fixtures(repo_root)

    def handler(request: Request) -> Response:
        raise AssertionError("should not fetch trending when roster is missing")

    args = argparse.Namespace(
        season="2025",
        value_season=None,
        roster_id=999,
        me=False,
        budget_remaining=None,
        weeks_remaining=10,
        hours=24,
        top=10,
    )
    with mock_http_server(handler) as base_url:
        exit_code = waiver_cmd.cmd_waiver_recommend(
            args, repo_root=repo_root, base_url=base_url
        )

    assert exit_code == 1
    assert "no roster found" in capsys.readouterr().out


def test_cmd_waiver_recommend_uses_explicit_budget_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_waiver_freeagent_fixtures(repo_root)

    def handler(request: Request) -> Response:
        return json_response([])

    args = argparse.Namespace(
        season="2025",
        value_season="2024",
        roster_id=None,
        me=True,
        budget_remaining=42,
        weeks_remaining=10,
        hours=24,
        top=10,
    )
    with mock_http_server(handler) as base_url:
        exit_code = waiver_cmd.cmd_waiver_recommend(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "FAAB budget remaining: 42" in out


def test_cmd_waiver_recommend_works_without_value_season_vorp_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_waiver_freeagent_fixtures(repo_root)

    def handler(request: Request) -> Response:
        return json_response([{"player_id": "3", "count": 40}])

    args = argparse.Namespace(
        season="2025",
        value_season="2099",
        roster_id=None,
        me=True,
        budget_remaining=None,
        weeks_remaining=10,
        hours=24,
        top=10,
    )
    with mock_http_server(handler) as base_url:
        exit_code = waiver_cmd.cmd_waiver_recommend(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "vorp=   n/a" in out


def test_cmd_freeagent_recommend_prints_upgrades(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_waiver_freeagent_fixtures(repo_root)

    args = argparse.Namespace(
        season="2025", value_season="2024", roster_id=None, me=True, top=10
    )
    exit_code = freeagent_cmd.cmd_freeagent_recommend(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Free RB" in out
    assert "Weak RB" in out


def test_cmd_freeagent_recommend_reports_missing_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_waiver_freeagent_fixtures(repo_root)

    args = argparse.Namespace(
        season="2025", value_season="2024", roster_id=999, me=False, top=10
    )
    exit_code = freeagent_cmd.cmd_freeagent_recommend(args, repo_root=repo_root)

    assert exit_code == 1
    assert "no roster found" in capsys.readouterr().out


def test_cmd_freeagent_recommend_raises_clear_error_when_vorp_not_computed(
    tmp_path: Path,
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_waiver_freeagent_fixtures(repo_root)

    args = argparse.Namespace(
        season="2025", value_season="2099", roster_id=None, me=True, top=10
    )

    with pytest.raises(freeagent_cmd.VorpNotComputedError):
        freeagent_cmd.cmd_freeagent_recommend(args, repo_root=repo_root)
