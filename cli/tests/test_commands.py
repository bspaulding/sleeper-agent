from __future__ import annotations

import argparse
import contextlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sleeper_agent.commands import sleeper_cmd, stats_cmd
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
