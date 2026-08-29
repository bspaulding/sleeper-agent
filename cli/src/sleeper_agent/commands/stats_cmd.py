"""`stats` command group: nflverse ingestion + VORP computation."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

import polars as pl

from sleeper_agent.config import data_dir, find_repo_root
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.stats import draft_picks_sync
from sleeper_agent.stats import sync as stats_sync
from sleeper_agent.stats import vorp as vorp_module
from sleeper_agent.storage.parquet_store import read_table, write_table

VORP_SCHEMA_VERSION = 1


class LeagueNotSyncedError(Exception):
    def __init__(self, season: str) -> None:
        self.season = season
        super().__init__(
            f"data/sleeper/league/{season}.parquet not found — run "
            f"`sleeper-agent sleeper league sync --season {season} --league-id <id>` first"
        )


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    stats_parser = subparsers.add_parser(
        "stats", help="External stats ingestion + VORP"
    )
    stats_subparsers = stats_parser.add_subparsers(dest="stats_command")

    sync_parser = stats_subparsers.add_parser(
        "sync", help="Sync nflverse stats for a season"
    )
    sync_parser.add_argument("--season", type=int, required=True)
    sync_parser.set_defaults(func=cmd_stats_sync)

    vorp_parser = stats_subparsers.add_parser("vorp", help="Compute VORP for a season")
    vorp_parser.add_argument("--season", type=int, required=True)
    vorp_parser.set_defaults(func=cmd_stats_vorp)

    draft_picks_parser = stats_subparsers.add_parser(
        "draft-picks", help="NFL draft-capital data (rookie triage)"
    )
    draft_picks_subparsers = draft_picks_parser.add_subparsers(
        dest="draft_picks_command"
    )
    draft_picks_sync_parser = draft_picks_subparsers.add_parser(
        "sync", help="Sync NFL draft picks + Sleeper-id crosswalk for a season"
    )
    draft_picks_sync_parser.add_argument("--season", type=int, required=True)
    draft_picks_sync_parser.set_defaults(func=cmd_stats_draft_picks_sync)


def cmd_stats_sync(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    sync_stats: Callable[
        [int, Path], stats_sync.StatsSyncResult
    ] = stats_sync.sync_stats,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    stats_dir = data_dir(root) / "stats"
    result = sync_stats(args.season, stats_dir)
    print(
        f"synced stats for {result.season}: {result.weekly_rows} weekly rows, "
        f"{result.snap_rows} snap rows, {result.schedule_rows} schedule rows, "
        f"{result.injury_rows} injury rows, {result.id_crosswalk_rows} id-crosswalk rows, "
        f"{result.team_rows} team rows"
    )
    return 0


def cmd_stats_draft_picks_sync(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    sync_draft_picks: Callable[
        [int, Path], draft_picks_sync.DraftPicksSyncResult
    ] = draft_picks_sync.sync_draft_picks,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    nfl_dir = data_dir(root) / "nfl"
    result = sync_draft_picks(args.season, nfl_dir)
    print(f"synced draft picks for {result.season}: {result.draft_pick_rows} row(s)")
    return 0


def cmd_stats_vorp(args: argparse.Namespace, *, repo_root: Path | None = None) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    season = str(args.season)
    sleeper_dir = data_dir(root) / "sleeper"
    stats_dir = data_dir(root) / "stats"

    league_path = sleeper_dir / "league" / f"{season}.parquet"
    if not league_path.exists():
        raise LeagueNotSyncedError(season)
    league = sleeper_sync.dataframe_to_league(
        read_table(
            league_path, expected_schema_version=sleeper_sync.LEAGUE_SCHEMA_VERSION
        )
    )

    weekly = read_table(
        stats_dir / "weekly" / f"{args.season}.parquet",
        expected_schema_version=stats_sync.WEEKLY_SCHEMA_VERSION,
    )
    ids = read_table(
        stats_dir / "ids.parquet", expected_schema_version=stats_sync.IDS_SCHEMA_VERSION
    )

    results = vorp_module.compute_vorp(
        weekly,
        ids,
        league.scoring_settings,
        league.roster_positions,
        league.settings.num_teams,
    )

    team_stats_path = stats_dir / "team" / f"{args.season}.parquet"
    schedules_path = stats_dir / "schedules" / f"{args.season}.parquet"
    players_path = sleeper_dir / "players.parquet"
    if team_stats_path.exists() and schedules_path.exists() and players_path.exists():
        team_stats = read_table(
            team_stats_path, expected_schema_version=stats_sync.TEAM_SCHEMA_VERSION
        )
        schedules = read_table(
            schedules_path, expected_schema_version=stats_sync.SCHEDULES_SCHEMA_VERSION
        )
        players_df = read_table(
            players_path, expected_schema_version=PLAYERS_SCHEMA_VERSION
        )
        def_players = players_df.filter(pl.col("position") == "DEF")
        results = results + vorp_module.compute_def_vorp(
            team_stats,
            schedules,
            def_players,
            league.scoring_settings,
            league.roster_positions,
            league.settings.num_teams,
        )

    df = pl.DataFrame(
        {
            "sleeper_id": [r.sleeper_id for r in results],
            "name": [r.name for r in results],
            "position": [r.position for r in results],
            "games_played": [r.games_played for r in results],
            "season_points": [r.season_points for r in results],
            "points_per_game": [r.points_per_game for r in results],
            "replacement_points": [r.replacement_points for r in results],
            "vorp_season": [r.vorp_season for r in results],
            "vorp_per_game": [r.vorp_per_game for r in results],
        }
    )
    write_table(
        df,
        data_dir(root) / "vorp" / f"{season}.parquet",
        schema_version=VORP_SCHEMA_VERSION,
    )

    top = sorted(results, key=lambda r: r.vorp_season, reverse=True)[:20]
    for rank, player in enumerate(top, start=1):
        print(
            f"{rank:2d}. {player.name:<25} {player.position:<3} "
            f"vorp={player.vorp_season:7.1f} pts={player.season_points:7.1f}"
        )
    return 0
