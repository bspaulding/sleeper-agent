"""`wiki` command group: scaffold player/team stub pages, list stale pages."""

from __future__ import annotations

import argparse
from pathlib import Path

from sleeper_agent.config import data_dir, find_repo_root, wiki_dir
from sleeper_agent.models.sleeper import Player, parse_player
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table
from sleeper_agent.wiki_tools.scaffold import (
    players_for_roster,
    scaffold_players,
    scaffold_teams,
)
from sleeper_agent.wiki_tools.staleness import stale_pages

ME_ROSTER_ID = 5


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    wiki_parser = subparsers.add_parser("wiki", help="Wiki scaffolding + staleness")
    wiki_subparsers = wiki_parser.add_subparsers(dest="wiki_command")

    scaffold_parser = wiki_subparsers.add_parser(
        "scaffold", help="Scaffold wiki stub pages"
    )
    scaffold_subparsers = scaffold_parser.add_subparsers(dest="scaffold_command")

    players_parser = scaffold_subparsers.add_parser(
        "players", help="Scaffold player pages"
    )
    players_parser.add_argument("--season", required=True)
    players_parser.add_argument("--roster-id", type=int, default=None)
    players_parser.add_argument("--all-rostered", action="store_true")
    players_parser.set_defaults(func=cmd_wiki_scaffold_players)

    scaffold_subparsers.add_parser(
        "teams", help="Scaffold NFL team pages"
    ).set_defaults(func=cmd_wiki_scaffold_teams)

    stale_parser = wiki_subparsers.add_parser("stale", help="List stale wiki pages")
    stale_parser.add_argument("--days", type=int, default=7)
    stale_parser.add_argument("--roster-id", type=int, default=None)
    stale_parser.add_argument("--me", action="store_true")
    stale_parser.add_argument("--season", default=None)
    stale_parser.set_defaults(func=cmd_wiki_stale)


def _read_players_by_id(sleeper_dir: Path) -> dict[str, Player]:
    players_df = read_table(
        sleeper_dir / "players.parquet", expected_schema_version=PLAYERS_SCHEMA_VERSION
    )
    players = [
        parse_player(
            row["player_id"],
            {
                "player_id": row["player_id"],
                "full_name": row["name"],
                "position": row["position"],
                "team": row["team"],
                "status": row["status"],
                "injury_status": row["injury_status"],
                "fantasy_positions": row["fantasy_positions"],
                "years_exp": row["years_exp"],
            },
        )
        for row in players_df.to_dicts()
    ]
    return {p.player_id: p for p in players}


def cmd_wiki_scaffold_players(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    sleeper_dir = data_dir(root) / "sleeper"

    rosters = sleeper_sync.dataframe_to_rosters(
        read_table(
            sleeper_dir / "rosters" / f"{args.season}.parquet",
            expected_schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
        )
    )
    players_by_id = _read_players_by_id(sleeper_dir)

    if args.all_rostered:
        target_rosters = rosters
    else:
        target_rosters = [r for r in rosters if r.roster_id == args.roster_id]

    players: list[Player] = []
    seen: set[str] = set()
    for roster in target_rosters:
        for player in players_for_roster(roster, players_by_id):
            if player.player_id not in seen:
                seen.add(player.player_id)
                players.append(player)

    result = scaffold_players(wiki_dir(root), players)
    print(
        f"created {len(result.created)} player page(s), {len(result.already_existed)} already existed"
    )
    return 0


def cmd_wiki_scaffold_teams(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    result = scaffold_teams(wiki_dir(root))
    print(
        f"created {len(result.created)} team page(s), {len(result.already_existed)} already existed"
    )
    return 0


def cmd_wiki_stale(args: argparse.Namespace, *, repo_root: Path | None = None) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    roster_id = ME_ROSTER_ID if args.me else args.roster_id

    pages = stale_pages(wiki_dir(root), ["players", "nfl-teams"], days=args.days)

    if roster_id is not None:
        sleeper_dir = data_dir(root) / "sleeper"
        rosters = sleeper_sync.dataframe_to_rosters(
            read_table(
                sleeper_dir / "rosters" / f"{args.season}.parquet",
                expected_schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
            )
        )
        matching = [r for r in rosters if r.roster_id == roster_id]
        player_ids = set(matching[0].player_ids) if matching else set()
        pages = [
            page
            for page in pages
            if "nfl-teams" in page.path.parts
            or page.path.stem.split("-", 1)[0] in player_ids
        ]

    for page in pages:
        last = page.last_researched.isoformat() if page.last_researched else "never"
        print(f"{page.path} (last_researched={last})")
    return 0
