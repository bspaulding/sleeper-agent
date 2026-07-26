"""`freeagent recommend` CLI wiring."""

from __future__ import annotations

import argparse
from pathlib import Path

from sleeper_agent.config import data_dir, find_repo_root
from sleeper_agent.freeagent.recommend import recommend_free_agents
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table
from sleeper_agent.waiver.recommend import PlayerValueRow

ME_ROSTER_ID = 5
VORP_SCHEMA_VERSION = 1


class VorpNotComputedError(Exception):
    def __init__(self, season: str) -> None:
        self.season = season
        super().__init__(
            f"data/vorp/{season}.parquet not found — run `sleeper-agent stats vorp --season {season}` first"
        )


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    freeagent_parser = subparsers.add_parser(
        "freeagent", help="Non-FAAB free agent recommendations"
    )
    freeagent_subparsers = freeagent_parser.add_subparsers(dest="freeagent_command")

    recommend_parser = freeagent_subparsers.add_parser(
        "recommend", help="Ranked free-agent upgrades"
    )
    recommend_parser.add_argument("--season", required=True)
    recommend_parser.add_argument("--value-season", default=None)
    recommend_parser.add_argument("--roster-id", type=int, default=None)
    recommend_parser.add_argument("--me", action="store_true")
    recommend_parser.add_argument("--top", type=int, default=10)
    recommend_parser.set_defaults(func=cmd_freeagent_recommend)


def cmd_freeagent_recommend(
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
    roster_id = ME_ROSTER_ID if args.me else args.roster_id
    matching = [r for r in rosters if r.roster_id == roster_id]
    if not matching:
        print(f"no roster found with roster_id={roster_id}")
        return 1
    roster = matching[0]

    rostered_player_ids = {pid for r in rosters for pid in r.player_ids}

    players_df = read_table(
        sleeper_dir / "players.parquet", expected_schema_version=PLAYERS_SCHEMA_VERSION
    )
    all_player_ids = set(players_df["player_id"].to_list())
    available_player_ids = all_player_ids - rostered_player_ids

    value_season = args.value_season or str(int(args.season) - 1)
    vorp_path = data_dir(root) / "vorp" / f"{value_season}.parquet"
    if not vorp_path.exists():
        raise VorpNotComputedError(value_season)
    vorp_df = read_table(vorp_path, expected_schema_version=VORP_SCHEMA_VERSION)
    value_by_id = {
        row["sleeper_id"]: PlayerValueRow(
            name=row["name"], position=row["position"], vorp_season=row["vorp_season"]
        )
        for row in vorp_df.to_dicts()
    }

    recommendations = recommend_free_agents(
        roster, value_by_id, available_player_ids, top_n=args.top
    )

    print(f"roster_id={roster.roster_id} free-agent upgrade suggestions:")
    for rec in recommendations:
        print(
            f"  {rec.name:<25} {rec.position:<3} vorp={rec.vorp_season:7.1f} "
            f"(+{rec.vorp_delta:.1f} over {rec.upgrade_over_name})"
        )
    return 0
