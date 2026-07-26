"""`decisions` command group: scaffold a new decision entry, rebuild the index."""

from __future__ import annotations

import argparse
from pathlib import Path

from sleeper_agent.config import decisions_dir, find_repo_root, wiki_dir
from sleeper_agent.decisions.index import build_index
from sleeper_agent.decisions.scaffold import DecisionKind, new_decision


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    decisions_parser = subparsers.add_parser("decisions", help="Decision log")
    decisions_subparsers = decisions_parser.add_subparsers(dest="decisions_command")

    new_parser = decisions_subparsers.add_parser(
        "new", help="Scaffold a new decision entry"
    )
    new_parser.add_argument(
        "--kind", choices=[k.value for k in DecisionKind], required=True
    )
    new_parser.add_argument("--slug", required=True)
    new_parser.add_argument("--season", required=True)
    new_parser.set_defaults(func=cmd_decisions_new)

    decisions_subparsers.add_parser(
        "index", help="Regenerate wiki/decisions.md"
    ).set_defaults(func=cmd_decisions_index)


def cmd_decisions_new(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    path = new_decision(
        decisions_dir(root), DecisionKind(args.kind), args.slug, args.season
    )
    print(f"created {path}")
    return 0


def cmd_decisions_index(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    path = build_index(decisions_dir(root), wiki_dir(root))
    print(f"wrote {path}")
    return 0
