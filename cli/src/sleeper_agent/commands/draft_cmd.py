"""`draft` command group: keeper eligibility/cost, live best-available board."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import date
from pathlib import Path

import polars as pl

from sleeper_agent.config import data_dir, decisions_dir, find_repo_root
from sleeper_agent.draft_tools.board import (
    board_view,
    my_roster_positions,
    render_board,
    roster_requirement_from_draft,
    watch_board,
)
from sleeper_agent.draft_tools.keepers import (
    KeeperCandidate,
    build_season_chain,
    infer_total_rounds,
    rank_keeper_candidates,
)
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.draft import (
    KeeperEligible,
    KeeperEligibleUndraftedDefault,
    KeeperIneligibleCostBelowRoundOne,
    KeeperIneligibleMaxYearsReached,
    fetch_draft,
    fetch_draft_picks,
    keeper_history,
)
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL
from sleeper_agent.sleeper_client.league import fetch_league
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table
from sleeper_agent.value.scoring import filter_rostered

ME_ROSTER_ID = 5
VORP_SCHEMA_VERSION = 1


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    draft_parser = subparsers.add_parser(
        "draft", help="Keeper eligibility + live draft board"
    )
    draft_subparsers = draft_parser.add_subparsers(dest="draft_command")

    keepers_parser = draft_subparsers.add_parser(
        "keepers", help="Keeper eligibility and cost for a roster"
    )
    keepers_parser.add_argument("--season", required=True)
    keepers_parser.add_argument("--roster-id", type=int, default=None)
    keepers_parser.add_argument("--me", action="store_true")
    keepers_parser.add_argument("--value-season", default=None)
    keepers_parser.set_defaults(func=cmd_draft_keepers)

    board_parser = draft_subparsers.add_parser(
        "board", help="Live best-available-by-value board"
    )
    board_source = board_parser.add_mutually_exclusive_group(required=True)
    board_source.add_argument("--league-id")
    board_source.add_argument(
        "--draft-id",
        help=(
            "Draft ID directly, bypassing league lookup — needed for a Sleeper mock "
            "draft, which has no league of its own. Requires --value-season."
        ),
    )
    board_parser.add_argument("--rounds", type=int, default=15)
    board_parser.add_argument("--watch", action="store_true")
    board_parser.add_argument("--value-season", default=None)
    board_parser.add_argument(
        "--num-teams",
        type=int,
        default=12,
        help="Only used with --draft-id, where there's no league.settings to read it from.",
    )
    board_parser.add_argument("--me", action="store_true")
    board_parser.add_argument("--roster-id", type=int, default=None)
    board_parser.add_argument(
        "--draft-slot",
        type=int,
        default=None,
        help=(
            "Resolve my roster_id from this draft's slot_to_roster_id map — needed for "
            "a mock draft (no stable roster_id across seasons), or as an alternative to "
            "--me/--roster-id in league mode."
        ),
    )
    board_parser.set_defaults(func=cmd_draft_board)


def _read_vorp(root: Path, season: str) -> pl.DataFrame | None:
    path = data_dir(root) / "vorp" / f"{season}.parquet"
    if not path.exists():
        return None
    return read_table(path, expected_schema_version=VORP_SCHEMA_VERSION)


def _read_players(root: Path) -> pl.DataFrame | None:
    path = data_dir(root) / "sleeper" / "players.parquet"
    if not path.exists():
        return None
    return read_table(path, expected_schema_version=PLAYERS_SCHEMA_VERSION)


def cmd_draft_keepers(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    sleeper_dir = data_dir(root) / "sleeper"

    # The roster to evaluate is whoever's on the team *heading into* this
    # season's draft — i.e. the prior season's final roster snapshot, not
    # `args.season`'s own roster file (which doesn't exist yet pre-draft;
    # rosters/{season}.parquet only gets synced after that season's draft
    # has actually happened and Sleeper reflects it).
    roster_season = str(int(args.season) - 1)
    rosters = sleeper_sync.dataframe_to_rosters(
        read_table(
            sleeper_dir / "rosters" / f"{roster_season}.parquet",
            expected_schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
        )
    )
    roster_id = ME_ROSTER_ID if args.me else args.roster_id
    matching = [r for r in rosters if r.roster_id == roster_id]
    if not matching:
        print(f"no roster found with roster_id={roster_id}")
        return 1
    roster = matching[0]

    season_chain, picks_by_season = build_season_chain(root, args.season)
    total_rounds = infer_total_rounds(season_chain, picks_by_season)

    value_season = args.value_season or str(int(args.season) - 1)
    vorp_df = _read_vorp(root, value_season)
    vorp_by_id: dict[str, float] = {}
    name_by_id: dict[str, str] = {}
    position_by_id: dict[str, str] = {}
    if vorp_df is not None:
        for row in vorp_df.to_dicts():
            vorp_by_id[row["sleeper_id"]] = row["vorp_season"]
            name_by_id[row["sleeper_id"]] = row["name"]
            position_by_id[row["sleeper_id"]] = row["position"]

    candidates = [
        KeeperCandidate(
            player_id=player_id,
            name=name_by_id.get(player_id, player_id),
            position=position_by_id.get(player_id),
            status=keeper_history(
                player_id, roster.roster_id, season_chain, picks_by_season, total_rounds
            ),
            vorp_season=vorp_by_id.get(player_id),
        )
        for player_id in roster.player_ids
    ]

    ranked = rank_keeper_candidates(candidates)
    print(f"roster_id={roster.roster_id} keeper eligibility for season {args.season}:")
    for candidate in ranked:
        match candidate.status:
            case KeeperEligible(cost_round=cost, last_round=last_round):
                vorp_display = (
                    f"{candidate.vorp_season:.1f}"
                    if candidate.vorp_season is not None
                    else "n/a"
                )
                print(
                    f"  ELIGIBLE  {candidate.name:<25} cost=R{cost} (last drafted/kept R{last_round}) "
                    f"vorp={vorp_display}"
                )
            case KeeperEligibleUndraftedDefault(cost_round=cost):
                vorp_display = (
                    f"{candidate.vorp_season:.1f}"
                    if candidate.vorp_season is not None
                    else "n/a"
                )
                print(
                    f"  ELIGIBLE  {candidate.name:<25} cost=R{cost} "
                    f"(no draft history — defaulted to last round) vorp={vorp_display}"
                )
            case KeeperIneligibleMaxYearsReached(consecutive_kept_seasons=n):
                print(
                    f"  ineligible {candidate.name:<24} kept {n} consecutive seasons already (max reached)"
                )
            case KeeperIneligibleCostBelowRoundOne(last_round=last_round):
                print(
                    f"  ineligible {candidate.name:<24} last drafted/kept round {last_round} (cost would be R0)"
                )
            case _:  # pragma: no cover - KeeperStatus is exhaustive over the four cases above
                raise AssertionError(f"unreachable: {candidate.status!r}")
    return 0


def cmd_draft_board(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
    today: Callable[[], date] = date.today,
    max_watch_iterations: int | None = None,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())

    if args.draft_id is not None:
        if args.value_season is None:
            print(
                "--value-season is required with --draft-id (e.g. for a Sleeper mock "
                "draft, there's no league to infer a season from)"
            )
            return 1
        draft_id = args.draft_id
        value_season = args.value_season
        num_teams = args.num_teams
    else:
        league = fetch_league(args.league_id, base_url=base_url)
        if league.draft_id is None:
            print(f"league {args.league_id} has no draft_id")
            return 1
        draft_id = league.draft_id
        value_season = args.value_season or league.season
        num_teams = max(league.settings.num_teams, 1)

    vorp_df = _read_vorp(root, value_season)
    if vorp_df is None:
        print(
            f"no VORP data for season {value_season} — run `stats vorp --season {value_season}` first"
        )
        return 1

    draft = fetch_draft(draft_id, base_url=base_url)
    requirement = roster_requirement_from_draft(draft)
    my_roster_id: int | None = None
    if args.draft_slot is not None:
        my_roster_id = draft.slot_to_roster_id.get(args.draft_slot)
    elif args.me:
        my_roster_id = ME_ROSTER_ID
    elif args.roster_id is not None:
        my_roster_id = args.roster_id

    players_df = _read_players(root)
    if players_df is not None:
        vorp_df = filter_rostered(vorp_df, players_df)

    top_n = args.rounds * num_teams

    if args.watch:
        log_path = (
            decisions_dir(root) / value_season / f"{today().isoformat()}-draft-live.md"
        )
        watch_board(
            draft_id,
            vorp_df,
            base_url=base_url,
            log_path=log_path,
            max_iterations=max_watch_iterations,
            my_roster_id=my_roster_id,
            requirement=requirement if my_roster_id is not None else None,
        )
        return 0

    picks = fetch_draft_picks(draft_id, base_url=base_url)
    board = board_view(vorp_df, picks, top_n=top_n)
    my_counts = (
        my_roster_positions(picks, my_roster_id) if my_roster_id is not None else None
    )
    print(
        render_board(
            board,
            my_counts=my_counts,
            requirement=requirement if my_roster_id is not None else None,
        )
    )
    return 0
