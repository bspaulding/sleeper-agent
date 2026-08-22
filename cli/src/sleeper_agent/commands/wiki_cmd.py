"""`wiki` command group: scaffold player/team stub pages, list stale pages."""

from __future__ import annotations

import argparse
from pathlib import Path

from sleeper_agent.config import data_dir, find_repo_root, wiki_dir
from sleeper_agent.draft_tools.rookies import triage_rookies
from sleeper_agent.models.sleeper import Player, parse_player
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.stats.draft_picks_sync import DRAFT_PICKS_SCHEMA_VERSION
from sleeper_agent.stats.sync import IDS_SCHEMA_VERSION, WEEKLY_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table
from sleeper_agent.value.team_changes import detect_team_changes, triage_team_changes
from sleeper_agent.wiki_tools.frontmatter_sync import sync_player_team_frontmatter
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

    rookies_parser = scaffold_subparsers.add_parser(
        "rookies", help="Scaffold pages for this season's triaged rookies"
    )
    rookies_parser.add_argument("--season", type=int, required=True)
    rookies_parser.set_defaults(func=cmd_wiki_scaffold_rookies)

    role_changers_parser = scaffold_subparsers.add_parser(
        "role-changers",
        help="Scaffold pages for this season's triaged role changers (FA/trade)",
    )
    role_changers_parser.add_argument("--season", type=int, required=True)
    role_changers_parser.set_defaults(func=cmd_wiki_scaffold_role_changers)

    wiki_subparsers.add_parser(
        "sync-frontmatter",
        help="Refresh nfl_team on player pages from the latest players sync",
    ).set_defaults(func=cmd_wiki_sync_frontmatter)

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


def cmd_wiki_scaffold_rookies(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    """Scaffold `wiki/players/*.md` stubs for this season's triaged rookies.

    Unlike `wiki scaffold players`, this isn't scoped to a fantasy roster
    (`cmd_wiki_scaffold_players` reads `rosters/{season}.parquet`, which no
    pre-draft rookie is on) — the triage list from `triage_rookies`
    (`draft_tools/rookies.py`) is the input instead. Reuses
    `scaffold_players` unchanged, since it already works off a `Player`
    list rather than a roster.

    `draft_picks.parquet` is a single overwritten file (`sync_draft_picks`
    doesn't partition by season), so `--season` is checked against what's
    actually in it — otherwise a stale or forgotten re-sync would silently
    scaffold a different season's rookies under the requested label.
    """
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    nfl_dir = data_dir(root) / "nfl"
    draft_picks_path = nfl_dir / "draft_picks.parquet"
    if not draft_picks_path.exists():
        print(
            f"no draft-picks data — run `stats draft-picks sync --season {args.season}` first"
        )
        return 1

    draft_picks_df = read_table(
        draft_picks_path, expected_schema_version=DRAFT_PICKS_SCHEMA_VERSION
    )
    synced_seasons = set(draft_picks_df["season"].unique().to_list())
    if synced_seasons != {args.season}:
        synced = ", ".join(str(season) for season in sorted(synced_seasons))
        print(
            f"data/nfl/draft_picks.parquet has season(s) [{synced}], not "
            f"{args.season} — run `stats draft-picks sync --season {args.season}` first"
        )
        return 1

    sleeper_dir = data_dir(root) / "sleeper"
    players_df = read_table(
        sleeper_dir / "players.parquet", expected_schema_version=PLAYERS_SCHEMA_VERSION
    )

    rookies = triage_rookies(draft_picks_df, players_df)
    result = scaffold_players(wiki_dir(root), [r.player for r in rookies])
    print(
        f"created {len(result.created)} player page(s), {len(result.already_existed)} already existed"
    )
    return 0


def cmd_wiki_scaffold_role_changers(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    """Scaffold `wiki/players/*.md` stubs for this season's triaged role
    changers (FA/trade).

    Unlike rookies, most role-changers are veterans who already have a wiki
    page from a prior season -- this only creates the rare missing one
    (e.g. a practice-squad call-up who never got scaffolded). `--season`
    here is the prior season whose weekly stats define "old team" (matches
    `value rank --season`/`stats vorp --season`'s convention), not the
    season the players are moving into.
    """
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    stats_dir = data_dir(root) / "stats"
    weekly_path = stats_dir / "weekly" / f"{args.season}.parquet"
    if not weekly_path.exists():
        print(f"no weekly stats — run `stats sync --season {args.season}` first")
        return 1

    weekly_df = read_table(weekly_path, expected_schema_version=WEEKLY_SCHEMA_VERSION)
    ids_df = read_table(
        stats_dir / "ids.parquet", expected_schema_version=IDS_SCHEMA_VERSION
    )

    sleeper_dir = data_dir(root) / "sleeper"
    players_df = read_table(
        sleeper_dir / "players.parquet", expected_schema_version=PLAYERS_SCHEMA_VERSION
    )
    players_by_id = _read_players_by_id(sleeper_dir)

    changes = triage_team_changes(detect_team_changes(weekly_df, players_df, ids_df))
    players = [
        players_by_id[change.sleeper_id]
        for change in changes
        if change.sleeper_id in players_by_id
    ]

    result = scaffold_players(wiki_dir(root), players)
    print(
        f"created {len(result.created)} player page(s), {len(result.already_existed)} already existed"
    )
    return 0


def cmd_wiki_sync_frontmatter(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    """Refresh `nfl_team` on every `wiki/players/*.md` page from the latest
    `data/sleeper/players.parquet` sync.

    `nfl_team` is only ever set once, at scaffold time — a player who
    changes team after their page already exists (the role-changer
    population `value/team_changes.py` detects) goes stale silently
    otherwise. Run after `sleeper players sync`, same as `wiki stale`
    is a secondary check on News content, not something folded into the
    sync itself.
    """
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    sleeper_dir = data_dir(root) / "sleeper"
    players_df = read_table(
        sleeper_dir / "players.parquet", expected_schema_version=PLAYERS_SCHEMA_VERSION
    )
    result = sync_player_team_frontmatter(wiki_dir(root), players_df)
    print(
        f"updated {len(result.updated)} page(s), {len(result.unchanged)} unchanged, "
        f"{len(result.skipped)} skipped (no matching player)"
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
