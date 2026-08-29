"""`trade` command group: evaluate a specific offer, propose candidate trades."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sleeper_agent.config import data_dir, find_repo_root
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.storage.parquet_store import read_table
from sleeper_agent.trade.evaluate import evaluate_trade, parse_offer
from sleeper_agent.trade.propose import propose_trades
from sleeper_agent.waiver.recommend import PlayerValueRow

ME_ROSTER_ID = 5
VORP_SCHEMA_VERSION = 2


class VorpNotComputedError(Exception):
    def __init__(self, season: str) -> None:
        self.season = season
        super().__init__(
            f"data/vorp/{season}.parquet not found — run `sleeper-agent stats vorp --season {season}` first"
        )


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    trade_parser = subparsers.add_parser(
        "trade", help="Trade evaluation + proposal scanning"
    )
    trade_subparsers = trade_parser.add_subparsers(dest="trade_command")

    evaluate_parser = trade_subparsers.add_parser(
        "evaluate", help="Evaluate a specific offer"
    )
    evaluate_parser.add_argument("--give", required=True)
    evaluate_parser.add_argument("--get", required=True)
    evaluate_parser.add_argument("--season", required=True)
    evaluate_parser.add_argument("--value-season", default=None)
    evaluate_parser.add_argument("--json", action="store_true")
    evaluate_parser.set_defaults(func=cmd_trade_evaluate)

    propose_parser = trade_subparsers.add_parser(
        "propose", help="Scan for candidate trades"
    )
    propose_parser.add_argument("--season", required=True)
    propose_parser.add_argument("--value-season", default=None)
    propose_parser.add_argument("--roster-id", type=int, default=None)
    propose_parser.add_argument("--me", action="store_true")
    propose_parser.add_argument("--target-roster-id", type=int, default=None)
    propose_parser.add_argument("--all", action="store_true")
    propose_parser.add_argument("--top", type=int, default=5)
    propose_parser.set_defaults(func=cmd_trade_propose)


def _read_value_by_id(root: Path, season: str) -> dict[str, PlayerValueRow]:
    path = data_dir(root) / "vorp" / f"{season}.parquet"
    if not path.exists():
        raise VorpNotComputedError(season)
    vorp_df = read_table(path, expected_schema_version=VORP_SCHEMA_VERSION)
    return {
        row["sleeper_id"]: PlayerValueRow(
            name=row["name"], position=row["position"], vorp_season=row["vorp_season"]
        )
        for row in vorp_df.to_dicts()
    }


def cmd_trade_evaluate(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    value_season = args.value_season or str(int(args.season) - 1)
    value_by_id = _read_value_by_id(root, value_season)

    give = parse_offer(args.give)
    get = parse_offer(args.get)
    evaluation = evaluate_trade(give, get, value_by_id)

    if args.json:
        print(
            json.dumps(
                {
                    "give_value": evaluation.give_value,
                    "get_value": evaluation.get_value,
                    "value_delta": evaluation.value_delta,
                    "give_position_totals": evaluation.give_position_totals,
                    "get_position_totals": evaluation.get_position_totals,
                }
            )
        )
        return 0

    print(
        f"give value: {evaluation.give_value:.1f}  ({evaluation.give_position_totals})"
    )
    print(f"get value:  {evaluation.get_value:.1f}  ({evaluation.get_position_totals})")
    print(f"value delta (get - give): {evaluation.value_delta:+.1f}")
    return 0


def cmd_trade_propose(
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
    our_roster_id = ME_ROSTER_ID if args.me else args.roster_id
    our_matching = [r for r in rosters if r.roster_id == our_roster_id]
    if not our_matching:
        print(f"no roster found with roster_id={our_roster_id}")
        return 1
    our_roster = our_matching[0]

    if args.all:
        targets = [r for r in rosters if r.roster_id != our_roster.roster_id]
    else:
        targets = [r for r in rosters if r.roster_id == args.target_roster_id]
        if not targets:
            print(f"no roster found with roster_id={args.target_roster_id}")
            return 1

    value_season = args.value_season or str(int(args.season) - 1)
    value_by_id = _read_value_by_id(root, value_season)

    any_found = False
    for target in targets:
        proposals = propose_trades(our_roster, target, value_by_id, top_n=args.top)
        if not proposals:
            continue
        any_found = True
        print(f"-- vs roster_id={target.roster_id} --")
        for proposal in proposals:
            print(
                f"  give {proposal.give_name} ({proposal.give_position}) <-> "
                f"get {proposal.get_name} ({proposal.get_position}) "
                f"delta={proposal.value_delta:+.1f} plausibility={proposal.plausibility_score:.1f}"
            )
    if not any_found:
        print("no candidate trades found within tolerance")
    return 0
