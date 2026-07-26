"""Builds the argparse.ArgumentParser tree and dispatches to plain functions.

Each command group lives in its own `sleeper_agent.commands.<group>_cmd`
module with an `add_subcommands(subparsers)` function, so this file stays a
flat wiring layer. Argument definitions and print/format glue live in those
command modules; business logic lives in the domain modules (`sleeper_client`,
`stats`, `value`, ...) as plain functions that return data.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sleeper-agent",
        description="LLM-driven Sleeper fantasy football team management CLI.",
    )
    parser.add_subparsers(dest="command")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(
        args
    )  # pragma: no cover - unreachable until a command group registers a handler


def run() -> None:  # pragma: no cover - thin entrypoint wrapper
    sys.exit(main())
