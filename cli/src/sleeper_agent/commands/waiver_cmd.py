"""`waiver recommend` CLI wiring."""

from __future__ import annotations

import argparse
from pathlib import Path

from sleeper_agent.config import data_dir, find_repo_root
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL
from sleeper_agent.sleeper_client.trending import TrendingType, fetch_trending
from sleeper_agent.storage.parquet_store import read_table
from sleeper_agent.waiver.recommend import PlayerValueRow, recommend_waivers

ME_ROSTER_ID = 5
VORP_SCHEMA_VERSION = 1


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    waiver_parser = subparsers.add_parser("waiver", help="FAAB waiver recommendations")
    waiver_subparsers = waiver_parser.add_subparsers(dest="waiver_command")

    recommend_parser = waiver_subparsers.add_parser(
        "recommend", help="Ranked waiver targets"
    )
    recommend_parser.add_argument("--season", required=True)
    recommend_parser.add_argument("--value-season", default=None)
    recommend_parser.add_argument("--roster-id", type=int, default=None)
    recommend_parser.add_argument("--me", action="store_true")
    recommend_parser.add_argument("--budget-remaining", type=int, default=None)
    recommend_parser.add_argument("--weeks-remaining", type=int, default=12)
    recommend_parser.add_argument("--hours", type=int, default=24)
    recommend_parser.add_argument("--top", type=int, default=10)
    recommend_parser.set_defaults(func=cmd_waiver_recommend)


def cmd_waiver_recommend(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    sleeper_dir = data_dir(root) / "sleeper"

    rosters = sleeper_sync.dataframe_to_rosters(
        read_table(
            sleeper_dir / "rosters" / f"{args.season}.parquet",
            expected_schema_version=sleeper_sync.ROSTERS_SCHEMA_VERSION,
        )
    )
    roster_id = ME_ROSTER_ID if args.me else args.roster_id
    matching = [r for r in rosters if r.roster_id == roster_id]
    if not matching:
        print(f"no roster found with roster_id={roster_id}")
        return 1
    roster = matching[0]

    rostered_player_ids = {pid for r in rosters for pid in r.player_ids}

    if args.budget_remaining is not None:
        budget_remaining = args.budget_remaining
    else:
        league = sleeper_sync.dataframe_to_league(
            read_table(
                sleeper_dir / "league" / f"{args.season}.parquet",
                expected_schema_version=sleeper_sync.LEAGUE_SCHEMA_VERSION,
            )
        )
        budget_remaining = league.settings.waiver_budget - roster.waiver_budget_used

    value_season = args.value_season or str(int(args.season) - 1)
    vorp_path = data_dir(root) / "vorp" / f"{value_season}.parquet"
    value_by_id: dict[str, PlayerValueRow] = {}
    if vorp_path.exists():
        vorp_df = read_table(vorp_path, expected_schema_version=VORP_SCHEMA_VERSION)
        for row in vorp_df.to_dicts():
            value_by_id[row["sleeper_id"]] = PlayerValueRow(
                name=row["name"],
                position=row["position"],
                vorp_season=row["vorp_season"],
            )

    trending_type = TrendingType.ADD
    trending = fetch_trending(trending_type, hours=args.hours, base_url=base_url)

    targets = recommend_waivers(
        trending,
        rostered_player_ids,
        value_by_id,
        budget_remaining,
        args.weeks_remaining,
        top_n=args.top,
    )

    print(f"roster_id={roster.roster_id} FAAB budget remaining: {budget_remaining}")
    for target in targets:
        vorp_display = (
            f"{target.vorp_season:.1f}" if target.vorp_season is not None else "n/a"
        )
        print(
            f"  {target.name:<25} {target.position:<3} trending={target.trending_count:4d} "
            f"vorp={vorp_display:>6} bid=${target.bid_low}-${target.bid_high}"
        )
    return 0
