"""`sleeper` command group: league resolution/sync, players sync, roster show, trending.

Each `cmd_*` handler takes an optional `base_url`/`repo_root` override with a
real default (`SLEEPER_BASE_URL`, `find_repo_root(Path.cwd())`) — the same
explicit-parameter-with-real-default pattern used everywhere else in this
codebase, so tests can point commands at a `mock_http_server`/`tmp_path`
without any network access or monkeypatching.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sleeper_agent.config import data_dir, find_repo_root
from sleeper_agent.sleeper_client import league as league_client
from sleeper_agent.sleeper_client import players as players_client
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client import trending as trending_client
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL
from sleeper_agent.sleeper_client.trending import TrendingType
from sleeper_agent.storage.parquet_store import read_table

DEFAULT_USERNAME = "yellldarb"
ME_ROSTER_ID = 5


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    sleeper_parser = subparsers.add_parser("sleeper", help="Sleeper league/team data")
    sleeper_subparsers = sleeper_parser.add_subparsers(dest="sleeper_command")

    league_parser = sleeper_subparsers.add_parser(
        "league", help="League resolution + sync"
    )
    league_subparsers = league_parser.add_subparsers(dest="league_command")

    resolve_parser = league_subparsers.add_parser(
        "resolve", help="Resolve the current season's league ID"
    )
    resolve_parser.add_argument("--season", required=True)
    resolve_parser.add_argument("--user", default=DEFAULT_USERNAME)
    resolve_parser.set_defaults(func=cmd_league_resolve)

    sync_parser = league_subparsers.add_parser(
        "sync", help="Sync league/roster/user/transaction/draft-pick data"
    )
    sync_parser.add_argument("--league-id", required=True)
    sync_parser.add_argument("--season", required=True)
    sync_parser.set_defaults(func=cmd_league_sync)

    players_parser = sleeper_subparsers.add_parser(
        "players", help="Player dictionary sync"
    )
    players_subparsers = players_parser.add_subparsers(dest="players_command")
    players_sync_parser = players_subparsers.add_parser(
        "sync", help="Sync the full player dictionary"
    )
    players_sync_parser.add_argument("--force", action="store_true")
    players_sync_parser.set_defaults(func=cmd_players_sync)

    roster_parser = sleeper_subparsers.add_parser("roster", help="Roster inspection")
    roster_subparsers = roster_parser.add_subparsers(dest="roster_command")
    roster_show_parser = roster_subparsers.add_parser(
        "show", help="Show a roster's players"
    )
    roster_show_parser.add_argument("--season", required=True)
    roster_show_parser.add_argument("--roster-id", type=int, default=None)
    roster_show_parser.add_argument("--me", action="store_true")
    roster_show_parser.set_defaults(func=cmd_roster_show)

    trending_parser = sleeper_subparsers.add_parser(
        "trending", help="Trending adds/drops"
    )
    trending_parser.add_argument("--type", choices=["add", "drop"], default="add")
    trending_parser.add_argument("--hours", type=int, default=24)
    trending_parser.set_defaults(func=cmd_trending)


def cmd_league_resolve(
    args: argparse.Namespace, *, base_url: str = SLEEPER_BASE_URL
) -> int:
    user_id = league_client.fetch_user_id(args.user, base_url=base_url)
    result = league_client.resolve_league_id(user_id, args.season, base_url=base_url)
    match result:
        case league_client.LeagueResolved(league_id=league_id, season=season):
            print(f"league_id={league_id} season={season}")
        case league_client.LeagueResolvedViaFallback(
            league_id=league_id, requested_season=requested, resolved_season=resolved
        ):
            print(
                f"no league found for season {requested}; fell back to season {resolved}: "
                f"league_id={league_id}"
            )
        case (
            _
        ):  # pragma: no cover - ResolveResult is exhaustive over its two cases above
            raise AssertionError(f"unreachable: {result!r}")
    return 0


def cmd_league_sync(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    sleeper_dir = data_dir(root) / "sleeper"
    result = sleeper_sync.sync_league(
        args.league_id, args.season, sleeper_dir, base_url=base_url
    )
    print(
        f"synced league {result.league_id} season {result.season}: "
        f"{result.roster_count} rosters, {result.user_count} users, "
        f"{result.transaction_count} transactions, {result.draft_pick_count} draft picks"
    )
    return 0


def cmd_players_sync(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
    now: Callable[[], datetime] = datetime.now,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    sleeper_dir = data_dir(root) / "sleeper"
    players_path = sleeper_dir / "players.parquet"
    meta_path = sleeper_dir / "players.meta.json"
    result = players_client.sync_players(
        players_path, meta_path, base_url=base_url, force=args.force, now=now
    )
    match result:
        case players_client.PlayersSyncSkipped(fetched_at=fetched_at):
            print(
                f"skipped: players dictionary already synced at {fetched_at.isoformat()} (<24h ago)"
            )
        case players_client.PlayersSyncPerformed(
            player_count=count, fetched_at=fetched_at
        ):
            print(f"synced {count} players at {fetched_at.isoformat()}")
        case _:  # pragma: no cover - PlayersSyncResult is exhaustive over its two cases above
            raise AssertionError(f"unreachable: {result!r}")
    return 0


def cmd_roster_show(args: argparse.Namespace, *, repo_root: Path | None = None) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    sleeper_dir = data_dir(root) / "sleeper"

    rosters_path = sleeper_dir / "rosters" / f"{args.season}.parquet"
    rosters = sleeper_sync.dataframe_to_rosters(
        read_table(
            rosters_path, expected_schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION
        )
    )

    roster_id = ME_ROSTER_ID if args.me else args.roster_id
    matching = [r for r in rosters if r.roster_id == roster_id]
    if not matching:
        print(f"no roster found with roster_id={roster_id}")
        return 1
    roster = matching[0]

    players_path = sleeper_dir / "players.parquet"
    players_df = read_table(
        players_path, expected_schema_version=players_client.PLAYERS_SCHEMA_VERSION
    )
    names_by_id = dict(zip(players_df["player_id"], players_df["name"], strict=True))

    print(
        f"roster_id={roster.roster_id} record={roster.wins}-{roster.losses}-{roster.ties}"
    )
    for player_id in roster.player_ids:
        name = names_by_id.get(player_id, player_id)
        print(f"  {name}")
    return 0


def cmd_trending(args: argparse.Namespace, *, base_url: str = SLEEPER_BASE_URL) -> int:
    trending_type = TrendingType.ADD if args.type == "add" else TrendingType.DROP
    entries = trending_client.fetch_trending(
        trending_type, hours=args.hours, base_url=base_url
    )
    for entry in entries:
        print(f"{entry.player_id}\t{entry.count}")
    return 0
