from __future__ import annotations

import argparse
import contextlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from sleeper_agent.commands import (
    decisions_cmd,
    draft_cmd,
    freeagent_cmd,
    sleeper_cmd,
    stats_cmd,
    trade_cmd,
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


def test_stats_draft_picks_sync_subcommand_is_registered() -> None:
    from sleeper_agent.main import build_parser

    parser = build_parser()
    args = parser.parse_args(["stats", "draft-picks", "sync", "--season", "2026"])

    assert args.func is stats_cmd.cmd_stats_draft_picks_sync
    assert args.season == 2026


def test_wiki_scaffold_rookies_subcommand_is_registered() -> None:
    from sleeper_agent.main import build_parser

    parser = build_parser()
    args = parser.parse_args(["wiki", "scaffold", "rookies", "--season", "2026"])

    assert args.func is wiki_cmd.cmd_wiki_scaffold_rookies
    assert args.season == 2026


def test_wiki_scaffold_role_changers_subcommand_is_registered() -> None:
    from sleeper_agent.main import build_parser

    parser = build_parser()
    args = parser.parse_args(["wiki", "scaffold", "role-changers", "--season", "2025"])

    assert args.func is wiki_cmd.cmd_wiki_scaffold_role_changers
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
    fetched_at = datetime(2026, 7, 26, 0, 0, 0, tzinfo=UTC)
    meta_path = repo_root / "data" / "sleeper" / "players.meta.json"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text(json.dumps({"fetched_at": fetched_at.isoformat()}))

    def failing_handler(request: Request) -> Response:
        raise AssertionError("should not fetch")

    args = argparse.Namespace(force=False)
    with mock_http_server(failing_handler) as base_url:
        exit_code = sleeper_cmd.cmd_players_sync(
            args,
            repo_root=repo_root,
            base_url=base_url,
            now=lambda: fetched_at + timedelta(hours=12),
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


def test_cmd_stats_draft_picks_sync_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from sleeper_agent.stats.draft_picks_sync import DraftPicksSyncResult

    repo_root = make_repo_root(tmp_path)

    def fake_sync_draft_picks(season: int, nfl_dir: Path) -> DraftPicksSyncResult:
        return DraftPicksSyncResult(season=season, draft_pick_rows=257)

    args = argparse.Namespace(season=2026)
    exit_code = stats_cmd.cmd_stats_draft_picks_sync(
        args, repo_root=repo_root, sync_draft_picks=fake_sync_draft_picks
    )

    assert exit_code == 0
    assert "synced draft picks for 2026: 257 row(s)" in capsys.readouterr().out


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

    weekly = pl.DataFrame(
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
    ids = pl.DataFrame({"gsis_id": ["00-A", "00-B"], "sleeper_id": ["101", "102"]})

    from sleeper_agent.stats.sync import IDS_SCHEMA_VERSION, WEEKLY_SCHEMA_VERSION

    write_table(
        weekly,
        stats_dir / "weekly" / "2025.parquet",
        schema_version=WEEKLY_SCHEMA_VERSION,
    )
    write_table(
        ids,
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


def _write_draft_picks_parquet(nfl_dir: Path, rows: list[dict[str, object]]) -> None:
    from sleeper_agent.stats.draft_picks_sync import DRAFT_PICKS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        pl.DataFrame(rows),
        nfl_dir / "draft_picks.parquet",
        schema_version=DRAFT_PICKS_SCHEMA_VERSION,
    )


def test_cmd_wiki_scaffold_rookies_creates_pages_for_triaged_rookies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    sleeper_dir = repo_root / "data" / "sleeper"
    nfl_dir = repo_root / "data" / "nfl"
    _write_players_parquet(sleeper_dir)
    _write_draft_picks_parquet(
        nfl_dir,
        [
            {
                "season": 2026,
                "round": 1,
                "pick": 1,
                "position": "WR",
                "pfr_player_name": "Rookie WR",
                "gsis_id": "X1",
                "sleeper_id": "1",  # matches Player One (WR) in players.parquet
            },
            {
                "season": 2026,
                "round": 5,
                "pick": 140,
                "position": "WR",
                "pfr_player_name": "Day 3 WR",
                "gsis_id": "X2",
                "sleeper_id": "2",  # matches Player Two (RB) — round 5 WR, cut anyway
            },
        ],
    )

    args = argparse.Namespace(season=2026)
    exit_code = wiki_cmd.cmd_wiki_scaffold_rookies(args, repo_root=repo_root)

    assert exit_code == 0
    assert "created 1 player page(s)" in capsys.readouterr().out
    assert (repo_root / "wiki" / "players" / "1-player-one.md").exists()
    assert not (repo_root / "wiki" / "players" / "2-player-two.md").exists()


def test_cmd_wiki_scaffold_rookies_reports_missing_draft_picks_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    sleeper_dir = repo_root / "data" / "sleeper"
    _write_players_parquet(sleeper_dir)

    args = argparse.Namespace(season=2026)
    exit_code = wiki_cmd.cmd_wiki_scaffold_rookies(args, repo_root=repo_root)

    assert exit_code == 1
    assert "no draft-picks data" in capsys.readouterr().out


def test_cmd_wiki_scaffold_rookies_reports_season_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`draft_picks.parquet` is a single overwritten file, not season-partitioned —
    if it holds a different season than requested (e.g. stale from last year, or a
    forgotten re-sync), fail loudly rather than silently scaffolding the wrong
    season's rookies under the requested season's label."""
    repo_root = make_repo_root(tmp_path)
    sleeper_dir = repo_root / "data" / "sleeper"
    nfl_dir = repo_root / "data" / "nfl"
    _write_players_parquet(sleeper_dir)
    _write_draft_picks_parquet(
        nfl_dir,
        [
            {
                "season": 2025,
                "round": 1,
                "pick": 1,
                "position": "WR",
                "pfr_player_name": "Rookie WR",
                "gsis_id": "X1",
                "sleeper_id": "1",
            }
        ],
    )

    args = argparse.Namespace(season=2026)
    exit_code = wiki_cmd.cmd_wiki_scaffold_rookies(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "2025" in out
    assert "2026" in out
    assert not (repo_root / "wiki" / "players" / "1-player-one.md").exists()


def test_cmd_wiki_scaffold_rookies_leaves_existing_pages_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    sleeper_dir = repo_root / "data" / "sleeper"
    nfl_dir = repo_root / "data" / "nfl"
    _write_players_parquet(sleeper_dir)
    _write_draft_picks_parquet(
        nfl_dir,
        [
            {
                "season": 2026,
                "round": 1,
                "pick": 1,
                "position": "WR",
                "pfr_player_name": "Rookie WR",
                "gsis_id": "X1",
                "sleeper_id": "1",
            }
        ],
    )
    page_path = repo_root / "wiki" / "players" / "1-player-one.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text(
        "---\nsleeper_id: '1'\n---\n\n## News\n\n- already researched\n"
    )

    args = argparse.Namespace(season=2026)
    exit_code = wiki_cmd.cmd_wiki_scaffold_rookies(args, repo_root=repo_root)

    assert exit_code == 0
    assert "created 0 player page(s), 1 already existed" in capsys.readouterr().out
    assert "already researched" in page_path.read_text()


def _write_role_changer_fixtures(repo_root: Path, *, season: str = "2025") -> None:
    """A players.parquet + weekly stats + id-crosswalk trio with one
    triaged role-changer (>=50 prior-season touches, CAR -> PIT) and one
    below the opportunity floor (30 touches, triaged out)."""
    from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        pl.DataFrame(
            {
                "player_id": ["1", "2"],
                "name": ["Player One", "Player Two"],
                "position": ["RB", "RB"],
                "team": ["PIT", "SEA"],
                "status": ["Active", "Active"],
                "injury_status": ["", ""],
                "fantasy_positions": [["RB"], ["RB"]],
                "years_exp": [3, 2],
            }
        ),
        repo_root / "data" / "sleeper" / "players.parquet",
        schema_version=PLAYERS_SCHEMA_VERSION,
    )
    write_table(
        pl.DataFrame(
            {
                "player_id": ["00-A", "00-A", "00-B"],
                "position": ["RB", "RB", "RB"],
                "week": [1, 2, 1],
                "team": ["CAR", "CAR", "JAX"],
                "carries": [30.0, 25.0, 30.0],
                "targets": [0.0, 0.0, 0.0],
            }
        ),
        repo_root / "data" / "stats" / "weekly" / f"{season}.parquet",
        schema_version=1,
    )
    write_table(
        pl.DataFrame(
            {"gsis_id": ["00-A", "00-B"], "sleeper_id": [1, 2]},
        ),
        repo_root / "data" / "stats" / "ids.parquet",
        schema_version=1,
    )


def test_cmd_wiki_scaffold_role_changers_creates_pages_for_triaged_movers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_role_changer_fixtures(repo_root)

    args = argparse.Namespace(season=2025)
    exit_code = wiki_cmd.cmd_wiki_scaffold_role_changers(args, repo_root=repo_root)

    assert exit_code == 0
    assert "created 1 player page(s)" in capsys.readouterr().out
    assert (repo_root / "wiki" / "players" / "1-player-one.md").exists()
    # 30 touches for Player Two is below the 50-touch opportunity floor.
    assert not (repo_root / "wiki" / "players" / "2-player-two.md").exists()


def test_cmd_wiki_scaffold_role_changers_leaves_existing_pages_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_role_changer_fixtures(repo_root)
    page_path = repo_root / "wiki" / "players" / "1-player-one.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text(
        "---\nsleeper_id: '1'\n---\n\n## News\n\n- already researched\n"
    )

    args = argparse.Namespace(season=2025)
    exit_code = wiki_cmd.cmd_wiki_scaffold_role_changers(args, repo_root=repo_root)

    assert exit_code == 0
    assert "created 0 player page(s), 1 already existed" in capsys.readouterr().out
    assert "already researched" in page_path.read_text()


def test_cmd_wiki_scaffold_role_changers_reports_missing_weekly_stats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    sleeper_dir = repo_root / "data" / "sleeper"
    _write_players_parquet(sleeper_dir)
    # No data/stats/weekly/2025.parquet written.

    args = argparse.Namespace(season=2025)
    exit_code = wiki_cmd.cmd_wiki_scaffold_role_changers(args, repo_root=repo_root)

    assert exit_code == 1
    assert "no weekly stats" in capsys.readouterr().out


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


def test_cmd_value_rank_excludes_players_with_no_nfl_team(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")
    write_table(
        pl.DataFrame(
            {"player_id": ["101", "102"], "team": ["KC", None]},
        ),
        repo_root / "data" / "sleeper" / "players.parquet",
        schema_version=PLAYERS_SCHEMA_VERSION,
    )

    args = argparse.Namespace(season="2025", position=None, top=20)
    exit_code = value_cmd.cmd_value_rank(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Runner A" in out
    assert "Runner B" not in out


def _write_value_team_change_fixtures(repo_root: Path, season: str) -> None:
    """Builds on `_write_value_fixtures`: Runner A (101) is a triaged
    role-changer (55 touches, CAR -> PIT); Runner B (102) has a current
    team on record but never changed it."""
    from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    _write_value_fixtures(repo_root, season)

    stats_dir = repo_root / "data" / "stats"
    write_table(
        pl.DataFrame(
            {
                "player_id": ["00-A", "00-A", "00-B"],
                "position": ["RB", "RB", "RB"],
                "week": [1, 2, 1],
                "team": ["CAR", "CAR", "SEA"],
                "carries": [30.0, 25.0, 10.0],
                "targets": [0.0, 0.0, 0.0],
            }
        ),
        stats_dir / "weekly" / f"{season}.parquet",
        schema_version=1,
    )
    write_table(
        pl.DataFrame(
            {
                "player_id": ["101", "102"],
                "name": ["Runner A", "Runner B"],
                "position": ["RB", "RB"],
                "team": ["PIT", "SEA"],
                "status": ["Active", "Active"],
                "injury_status": ["", ""],
                "fantasy_positions": [["RB"], ["RB"]],
                "years_exp": [3, 2],
            }
        ),
        repo_root / "data" / "sleeper" / "players.parquet",
        schema_version=PLAYERS_SCHEMA_VERSION,
    )


def test_cmd_value_rank_tags_triaged_role_changer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_team_change_fixtures(repo_root, "2025")

    args = argparse.Namespace(season="2025", position=None, top=20)
    exit_code = value_cmd.cmd_value_rank(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    lines = out.splitlines()
    runner_a_line = next(line for line in lines if "Runner A" in line)
    runner_b_line = next(line for line in lines if "Runner B" in line)
    assert "[MOVED: CAR" in runner_a_line
    assert "PIT]" in runner_a_line
    assert "[MOVED" not in runner_b_line


def test_cmd_value_rank_omits_moved_tag_without_players_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_fixtures(repo_root, "2025")  # no players.parquet written

    args = argparse.Namespace(season="2025", position=None, top=20)
    exit_code = value_cmd.cmd_value_rank(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[MOVED" not in out


def test_cmd_value_player_tags_triaged_role_changer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_team_change_fixtures(repo_root, "2025")

    args = argparse.Namespace(sleeper_id="101", season="2025")
    exit_code = value_cmd.cmd_value_player(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[MOVED: CAR" in out
    assert "PIT]" in out


def test_cmd_value_player_omits_moved_tag_for_non_mover(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_value_team_change_fixtures(repo_root, "2025")

    args = argparse.Namespace(sleeper_id="102", season="2025")
    exit_code = value_cmd.cmd_value_player(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[MOVED" not in out


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


def _draft_object_payload(
    draft_id: str = "did1", slot_to_roster_id: dict[str, int] | None = None
) -> dict[str, object]:
    return {
        "draft_id": draft_id,
        "type": "snake",
        "settings": {
            "rounds": 15,
            "teams": 12,
            "slots_qb": 1,
            "slots_rb": 2,
            "slots_wr": 2,
            "slots_te": 1,
            "slots_flex": 2,
            "slots_def": 1,
        },
        "slot_to_roster_id": slot_to_roster_id or {"1": 5},
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
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Best available by value:" in out
    assert "A" in out
    assert "My roster so far" not in out  # no --me/--roster-id/--draft-slot given


def test_cmd_draft_board_excludes_players_with_no_nfl_team(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1", "2"],
            "name": ["Rostered Guy", "Teamless Guy"],
            "position": ["RB", "WR"],
            "vorp_season": [50.0, 30.0],
        }
    )
    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)
    write_table(
        pl.DataFrame({"player_id": ["1", "2"], "team": ["KC", ""]}),
        repo_root / "data" / "sleeper" / "players.parquet",
        schema_version=PLAYERS_SCHEMA_VERSION,
    )

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Rostered Guy" in out
    assert "Teamless Guy" not in out


def _write_rookie_fixtures(repo_root: Path, *, season: str = "2025") -> None:
    """A players.parquet + data/nfl/draft_picks.parquet pair with one
    round-1 WR rookie (triaged in) and one round-5 WR rookie (triaged out)."""
    from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
    from sleeper_agent.stats.draft_picks_sync import DRAFT_PICKS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        pl.DataFrame(
            {
                "player_id": ["101", "102"],
                "name": ["Rookie Star", "Rookie Deep Bench"],
                "position": ["WR", "WR"],
                "team": ["KC", "BUF"],
                "status": ["Active", "Active"],
                "injury_status": ["", ""],
                "fantasy_positions": [["WR"], ["WR"]],
                "years_exp": [0, 0],
            }
        ),
        repo_root / "data" / "sleeper" / "players.parquet",
        schema_version=PLAYERS_SCHEMA_VERSION,
    )
    write_table(
        pl.DataFrame(
            {
                "season": [int(season), int(season)],
                "round": [1, 5],
                "pick": [1, 140],
                "position": ["WR", "WR"],
                "pfr_player_name": ["Rookie Star", "Rookie Deep Bench"],
                "gsis_id": ["X1", "X2"],
                "sleeper_id": ["101", "102"],
            }
        ),
        repo_root / "data" / "nfl" / "draft_picks.parquet",
        schema_version=DRAFT_PICKS_SCHEMA_VERSION,
    )


def test_cmd_draft_board_prints_rookie_watch_section_when_draft_picks_data_present(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)
    _write_rookie_fixtures(repo_root)

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Rookie watch" in out
    assert "Rookie Star" in out
    # Round-5 WR is below the WR triage cutoff (rounds 1-2) — never surfaced.
    assert "Rookie Deep Bench" not in out


def test_cmd_draft_board_rookie_watch_excludes_already_drafted_rookie(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)
    _write_rookie_fixtures(repo_root)

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response(
                [
                    {
                        "draft_id": "did1",
                        "round": 1,
                        "pick_no": 1,
                        "draft_slot": 1,
                        "roster_id": 9,
                        "player_id": "101",
                        "is_keeper": False,
                        "picked_by": "u9",
                        "metadata": {
                            "first_name": "Rookie",
                            "last_name": "Star",
                            "position": "WR",
                        },
                    }
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Rookie watch" not in out  # only triaged rookie was drafted


def test_cmd_draft_board_omits_rookie_watch_when_no_draft_picks_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)
    # No data/nfl/draft_picks.parquet written.

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Rookie watch" not in out


def _write_team_change_fixtures(repo_root: Path, *, season: str = "2025") -> None:
    """A players.parquet + weekly stats + id-crosswalk trio with one
    triaged role-changer (>=50 prior-season touches, CAR -> PIT) and one
    below the opportunity floor (30 touches, triaged out)."""
    from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        pl.DataFrame(
            {
                "player_id": ["1", "2"],
                "name": ["A", "Low Volume Guy"],
                "position": ["RB", "RB"],
                "team": ["PIT", "SEA"],
                "status": ["Active", "Active"],
                "injury_status": ["", ""],
                "fantasy_positions": [["RB"], ["RB"]],
                "years_exp": [3, 2],
            }
        ),
        repo_root / "data" / "sleeper" / "players.parquet",
        schema_version=PLAYERS_SCHEMA_VERSION,
    )
    write_table(
        pl.DataFrame(
            {
                "player_id": ["00-A", "00-A", "00-B"],
                "position": ["RB", "RB", "RB"],
                "week": [1, 2, 1],
                "team": ["CAR", "CAR", "JAX"],
                "carries": [30.0, 25.0, 30.0],
                "targets": [0.0, 0.0, 0.0],
            }
        ),
        repo_root / "data" / "stats" / "weekly" / f"{season}.parquet",
        schema_version=1,
    )
    write_table(
        pl.DataFrame(
            {"gsis_id": ["00-A", "00-B"], "sleeper_id": [1, 2]},
        ),
        repo_root / "data" / "stats" / "ids.parquet",
        schema_version=1,
    )


def test_cmd_draft_board_tags_triaged_role_changer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1", "2"],
            "name": ["A", "Low Volume Guy"],
            "position": ["RB", "RB"],
            "vorp_season": [50.0, 30.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)
    _write_team_change_fixtures(repo_root)

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[MOVED: CAR" in out
    assert "PIT]" in out
    # 30 touches for player "2" is below the 50-touch opportunity floor.
    lines = [line for line in out.splitlines() if "Low Volume Guy" in line]
    assert len(lines) == 1
    assert "[MOVED" not in lines[0]


def test_cmd_draft_board_omits_moved_tag_when_no_stats_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)
    # No data/stats/weekly, data/stats/ids.parquet, or players.parquet written.

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[MOVED" not in out


def test_cmd_draft_board_watch_threads_moved_tag_into_decision_log(
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
                "vorp_season": [50.0],
            }
        ),
        repo_root / "data" / "vorp" / "2025.parquet",
        schema_version=1,
    )
    _write_team_change_fixtures(repo_root)

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=True,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
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
    assert "[MOVED: CAR" in log_path.read_text()


def test_cmd_draft_board_reports_missing_vorp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)

    def handler(request: Request) -> Response:
        return json_response(_league_payload())

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
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
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
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
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=True,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
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


def test_cmd_draft_board_watch_threads_rookie_watch_into_decision_log(
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
    _write_rookie_fixtures(repo_root)

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=True,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
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
    assert "Rookie watch" in log_path.read_text()
    assert "Rookie Star" in log_path.read_text()


def test_cmd_draft_board_with_draft_id_skips_league_lookup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Sleeper mock draft has no league to resolve — --draft-id points at it directly."""
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

    write_table(vorp_df, repo_root / "data" / "vorp" / "2026.parquet", schema_version=1)

    def handler(request: Request) -> Response:
        if request.path == "/draft/mockdid1":
            return json_response(_draft_object_payload(draft_id="mockdid1"))
        if request.path == "/draft/mockdid1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id=None,
        draft_id="mockdid1",
        rounds=15,
        watch=False,
        value_season="2026",
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Best available by value:" in out
    assert "A" in out


def test_cmd_draft_board_annotates_with_me_flag(
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
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            # roster_id 5 matches draft_cmd.ME_ROSTER_ID
            return json_response(
                [
                    {
                        "draft_id": "did1",
                        "round": 1,
                        "pick_no": 1,
                        "draft_slot": 1,
                        "roster_id": 5,
                        "player_id": "3",
                        "is_keeper": False,
                        "picked_by": "u1",
                        "metadata": {
                            "first_name": "Already",
                            "last_name": "Drafted",
                            "position": "RB",
                        },
                    }
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=True,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "My roster so far:" in out
    assert "RB 1/2" in out


def test_cmd_draft_board_annotates_with_roster_id_flag(
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
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload(slot_to_roster_id={"1": 7}))
        if request.path == "/draft/did1/picks":
            # roster_id 7 matches args.roster_id below (a non-ME_ROSTER_ID value)
            return json_response(
                [
                    {
                        "draft_id": "did1",
                        "round": 1,
                        "pick_no": 1,
                        "draft_slot": 1,
                        "roster_id": 7,
                        "player_id": "3",
                        "is_keeper": False,
                        "picked_by": "u1",
                        "metadata": {
                            "first_name": "Already",
                            "last_name": "Drafted",
                            "position": "RB",
                        },
                    }
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=7,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "My roster so far:" in out
    assert "RB 1/2" in out


def test_cmd_draft_board_annotates_with_draft_slot_in_mock_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2026.parquet", schema_version=1)

    def handler(request: Request) -> Response:
        if request.path == "/draft/mockdid1":
            # slot 8 -> roster_id 42 for this mock
            return json_response(
                _draft_object_payload(draft_id="mockdid1", slot_to_roster_id={"8": 42})
            )
        if request.path == "/draft/mockdid1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id=None,
        draft_id="mockdid1",
        rounds=15,
        watch=False,
        value_season="2026",
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=8,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "My roster so far:" in out
    assert "RB 0/2" in out


def test_cmd_draft_board_reports_unresolvable_draft_slot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2026.parquet", schema_version=1)

    def handler(request: Request) -> Response:
        if request.path == "/draft/mockdid1":
            # only slot 8 is mapped for this mock; slot 3 is not present
            return json_response(
                _draft_object_payload(draft_id="mockdid1", slot_to_roster_id={"8": 42})
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id=None,
        draft_id="mockdid1",
        rounds=15,
        watch=False,
        value_season="2026",
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=3,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "--draft-slot 3" in out
    assert "[8]" in out


def test_cmd_draft_board_with_draft_id_requires_value_season(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)

    args = argparse.Namespace(
        league_id=None,
        draft_id="mockdid1",
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
    )
    exit_code = draft_cmd.cmd_draft_board(args, repo_root=repo_root)

    assert exit_code == 1
    assert "--value-season is required with --draft-id" in capsys.readouterr().out


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


# --- trade ---------------------------------------------------------------


def _write_trade_fixtures(repo_root: Path) -> None:
    from sleeper_agent.models.sleeper import Roster
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
            waiver_budget_used=0,
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
        Roster(
            roster_id=7,
            owner_id="u3",
            league_id="lid",
            player_ids=("3",),
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

    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1", "2", "3"],
            "name": ["Our RB", "Their WR", "Other TE"],
            "position": ["RB", "WR", "TE"],
            "games_played": [10, 10, 10],
            "season_points": [100.0, 105.0, 5.0],
            "points_per_game": [10.0, 10.5, 0.5],
            "replacement_points": [50.0, 50.0, 5.0],
            "vorp_season": [50.0, 51.0, -20.0],
            "vorp_per_game": [5.0, 5.1, -2.0],
        }
    )
    write_table(vorp_df, repo_root / "data" / "vorp" / "2024.parquet", schema_version=1)


def test_cmd_trade_evaluate_prints_value_delta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_trade_fixtures(repo_root)

    args = argparse.Namespace(
        give="1", get="2", season="2025", value_season="2024", json=False
    )
    exit_code = trade_cmd.cmd_trade_evaluate(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "give value: 50.0" in out
    assert "get value:  51.0" in out
    assert "value delta (get - give): +1.0" in out


def test_cmd_trade_evaluate_json_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_trade_fixtures(repo_root)

    args = argparse.Namespace(
        give="1", get="2", season="2025", value_season="2024", json=True
    )
    exit_code = trade_cmd.cmd_trade_evaluate(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    parsed = json.loads(out)
    assert parsed["value_delta"] == 1.0


def test_cmd_trade_evaluate_raises_clear_error_when_vorp_not_computed(
    tmp_path: Path,
) -> None:
    repo_root = make_repo_root(tmp_path)
    args = argparse.Namespace(
        give="1", get="2", season="2099", value_season=None, json=False
    )

    with pytest.raises(trade_cmd.VorpNotComputedError):
        trade_cmd.cmd_trade_evaluate(args, repo_root=repo_root)


def test_cmd_trade_propose_against_one_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_trade_fixtures(repo_root)

    args = argparse.Namespace(
        season="2025",
        value_season="2024",
        roster_id=None,
        me=True,
        target_roster_id=6,
        all=False,
        top=5,
    )
    exit_code = trade_cmd.cmd_trade_propose(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "vs roster_id=6" in out
    assert "Our RB" in out
    assert "Their WR" in out


def test_cmd_trade_propose_all_scans_every_other_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_trade_fixtures(repo_root)

    args = argparse.Namespace(
        season="2025",
        value_season="2024",
        roster_id=None,
        me=True,
        target_roster_id=None,
        all=True,
        top=5,
    )
    exit_code = trade_cmd.cmd_trade_propose(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "vs roster_id=6" in out
    assert (
        "vs roster_id=7" not in out
    )  # roster 7's only player (TE, -20 vorp) is outside tolerance


def test_cmd_trade_propose_reports_missing_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_trade_fixtures(repo_root)

    args = argparse.Namespace(
        season="2025",
        value_season="2024",
        roster_id=999,
        me=False,
        target_roster_id=6,
        all=False,
        top=5,
    )
    exit_code = trade_cmd.cmd_trade_propose(args, repo_root=repo_root)

    assert exit_code == 1
    assert "no roster found" in capsys.readouterr().out


def test_cmd_trade_propose_reports_missing_target_roster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_trade_fixtures(repo_root)

    args = argparse.Namespace(
        season="2025",
        value_season="2024",
        roster_id=None,
        me=True,
        target_roster_id=999,
        all=False,
        top=5,
    )
    exit_code = trade_cmd.cmd_trade_propose(args, repo_root=repo_root)

    assert exit_code == 1
    assert "no roster found" in capsys.readouterr().out


def test_cmd_trade_propose_reports_no_candidates_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    _write_trade_fixtures(repo_root)

    args = argparse.Namespace(
        season="2025",
        value_season="2024",
        roster_id=None,
        me=True,
        target_roster_id=7,
        all=False,
        top=5,
    )
    exit_code = trade_cmd.cmd_trade_propose(args, repo_root=repo_root)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "no candidate trades found" in out
