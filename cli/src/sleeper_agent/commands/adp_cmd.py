"""`adp` command group: sync a DraftSharks ADP snapshot for keeper pricing."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import date
from pathlib import Path

from sleeper_agent.adp import sync as adp_sync
from sleeper_agent.config import data_dir, find_repo_root
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table


class PlayersNotSyncedError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "data/sleeper/players.parquet not found — run "
            "`sleeper-agent sleeper players sync` first"
        )


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    adp_parser = subparsers.add_parser(
        "adp", help="DraftSharks ADP snapshot for the keeper-cost ADP-reset rule"
    )
    adp_subparsers = adp_parser.add_subparsers(dest="adp_command")

    sync_parser = adp_subparsers.add_parser(
        "sync", help="Fetch + snapshot current DraftSharks Sleeper/PPR/12-team ADP"
    )
    sync_parser.set_defaults(func=cmd_adp_sync)


def cmd_adp_sync(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    today: Callable[[], date] = date.today,
    sync_adp: Callable[..., adp_sync.AdpSyncResult] = adp_sync.sync_adp,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    players_path = data_dir(root) / "sleeper" / "players.parquet"
    if not players_path.exists():
        raise PlayersNotSyncedError()
    players_df = read_table(
        players_path, expected_schema_version=PLAYERS_SCHEMA_VERSION
    )

    retrieved_date = today().isoformat()
    result = sync_adp(data_dir(root) / "adp", players_df, retrieved_date=retrieved_date)

    print(
        f"synced ADP snapshot {result.retrieved_date}: {result.matched_rows}/"
        f"{result.total_rows} rows matched to a Sleeper player_id"
    )
    if result.unmatched_names:
        preview = ", ".join(result.unmatched_names[:10])
        remaining = len(result.unmatched_names) - 10
        suffix = f" (+{remaining} more)" if remaining > 0 else ""
        print(f"  unmatched: {preview}{suffix}")
    return 0
