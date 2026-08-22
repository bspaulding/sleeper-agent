"""`value` command group: VORP + trend + injury + wiki-news player valuation."""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from sleeper_agent.config import data_dir, find_repo_root, wiki_dir
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.stats.sync import IDS_SCHEMA_VERSION, WEEKLY_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table
from sleeper_agent.value.scoring import (
    InjuryReported,
    compute_injury,
    compute_trend,
    filter_rostered,
    gsis_id_for_sleeper_id,
    recent_news_excerpt,
)
from sleeper_agent.value.team_changes import (
    TeamChange,
    detect_team_changes,
    triage_team_changes,
)

# Columns `detect_team_changes` needs beyond what a bare weekly-stats fetch
# always carries (e.g. hand-built fixtures in older tests) -- absence means
# "not enough data to detect role changes yet", same best-effort-empty
# convention as a missing `players.parquet`, not an error.
_TEAM_CHANGE_WEEKLY_COLUMNS = {"team", "position", "carries", "targets"}

VORP_SCHEMA_VERSION = 1
ME_ROSTER_ID = 5


class VorpNotComputedError(Exception):
    def __init__(self, season: str) -> None:
        self.season = season
        super().__init__(
            f"data/vorp/{season}.parquet not found — run `sleeper-agent stats vorp --season {season}` first"
        )


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    value_parser = subparsers.add_parser("value", help="Player valuation")
    value_subparsers = value_parser.add_subparsers(dest="value_command")

    player_parser = value_subparsers.add_parser(
        "player", help="Full valuation for one player"
    )
    player_parser.add_argument("sleeper_id")
    player_parser.add_argument("--season", required=True)
    player_parser.set_defaults(func=cmd_value_player)

    rank_parser = value_subparsers.add_parser("rank", help="Ranked value list")
    rank_parser.add_argument("--season", required=True)
    rank_parser.add_argument("--position", default=None)
    rank_parser.add_argument("--top", type=int, default=20)
    rank_parser.set_defaults(func=cmd_value_rank)

    roster_parser = value_subparsers.add_parser(
        "roster", help="Positional value breakdown for a roster"
    )
    roster_parser.add_argument("--season", required=True)
    roster_parser.add_argument("--roster-id", type=int, default=None)
    roster_parser.add_argument("--me", action="store_true")
    roster_parser.set_defaults(func=cmd_value_roster)


def _read_vorp(root: Path, season: str) -> pl.DataFrame:
    path = data_dir(root) / "vorp" / f"{season}.parquet"
    if not path.exists():
        raise VorpNotComputedError(season)
    return read_table(path, expected_schema_version=VORP_SCHEMA_VERSION)


def _read_players(root: Path) -> pl.DataFrame | None:
    path = data_dir(root) / "sleeper" / "players.parquet"
    if not path.exists():
        return None
    return read_table(path, expected_schema_version=PLAYERS_SCHEMA_VERSION)


def _team_changes_by_sleeper_id(
    root: Path, season: str, players_df: pl.DataFrame | None
) -> dict[str, TeamChange]:
    """Best-effort triaged role-changer (FA/trade) lookup for the `[MOVED:
    ...]` tag on `value rank`/`value player` rows.

    Absent `data/sleeper/players.parquet`, `data/stats/weekly/{season}.parquet`,
    `data/stats/ids.parquet`, or the weekly table not yet carrying the
    columns role-change detection needs, this is just an empty dict — the
    output renders exactly as it does today.
    """
    weekly_path = data_dir(root) / "stats" / "weekly" / f"{season}.parquet"
    ids_path = data_dir(root) / "stats" / "ids.parquet"
    if players_df is None or not weekly_path.exists() or not ids_path.exists():
        return {}
    weekly = read_table(weekly_path, expected_schema_version=WEEKLY_SCHEMA_VERSION)
    if not _TEAM_CHANGE_WEEKLY_COLUMNS.issubset(weekly.columns):
        return {}
    ids = read_table(ids_path, expected_schema_version=IDS_SCHEMA_VERSION)
    changes = triage_team_changes(detect_team_changes(weekly, players_df, ids))
    return {change.sleeper_id: change for change in changes}


def cmd_value_player(args: argparse.Namespace, *, repo_root: Path | None = None) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    season = args.season
    vorp_df = _read_vorp(root, season)
    matches = vorp_df.filter(pl.col("sleeper_id") == args.sleeper_id)
    if matches.height == 0:
        print(f"no VORP data for sleeper_id={args.sleeper_id} in season {season}")
        return 1
    row = matches.row(0, named=True)

    stats_dir = data_dir(root) / "stats"
    ids = read_table(
        stats_dir / "ids.parquet", expected_schema_version=IDS_SCHEMA_VERSION
    )
    weekly = read_table(
        stats_dir / "weekly" / f"{season}.parquet",
        expected_schema_version=WEEKLY_SCHEMA_VERSION,
    )
    injuries_path = stats_dir / "injuries" / f"{season}.parquet"
    injuries = (
        read_table(injuries_path, expected_schema_version=1)
        if injuries_path.exists()
        else None
    )

    gsis_id = gsis_id_for_sleeper_id(ids, args.sleeper_id)
    player_weekly = (
        weekly.filter(pl.col("player_id") == gsis_id) if gsis_id else weekly.clear()
    )
    trend = compute_trend(player_weekly, row["position"])
    injury = (
        compute_injury(injuries, gsis_id)
        if (gsis_id and injuries is not None)
        else None
    )
    news = recent_news_excerpt(wiki_dir(root), args.sleeper_id)

    players_df = _read_players(root)
    team_changes = _team_changes_by_sleeper_id(root, season, players_df)
    change = team_changes.get(args.sleeper_id)

    header = f"{row['name']} ({row['position']})"
    if change is not None:
        header += f" [MOVED: {change.old_team}→{change.new_team}]"
    print(header)
    print(
        f"  VORP: season={row['vorp_season']:.1f} per-game={row['vorp_per_game']:.2f} "
        f"(points={row['season_points']:.1f} over {row['games_played']} games)"
    )
    if trend is not None:
        print(
            f"  Trend ({trend.metric}): last {trend.last_n_games}-game avg={trend.recent_avg:.1f} "
            f"vs season avg={trend.season_avg:.1f} (delta={trend.delta:+.1f})"
        )
    else:
        print("  Trend: not available")
    if isinstance(injury, InjuryReported):
        print(
            f"  Injury: {injury.status} ({injury.primary_injury or 'unspecified'}) as of week {injury.as_of_week}"
        )
    else:
        print("  Injury: none on record")
    if news:
        print("  Recent news:")
        for line in news:
            print(f"    {line}")
    else:
        print("  Recent news: none filed")
    return 0


def cmd_value_rank(args: argparse.Namespace, *, repo_root: Path | None = None) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    vorp_df = _read_vorp(root, args.season)
    players_df = _read_players(root)
    team_changes = _team_changes_by_sleeper_id(root, args.season, players_df)
    if players_df is not None:
        vorp_df = filter_rostered(vorp_df, players_df)
    if args.position:
        vorp_df = vorp_df.filter(pl.col("position") == args.position)
    ranked = vorp_df.sort("vorp_season", descending=True).head(args.top)
    for rank, row in enumerate(ranked.to_dicts(), start=1):
        line = f"{rank:2d}. {row['name']:<25} {row['position']:<3} vorp={row['vorp_season']:7.1f}"
        change = team_changes.get(row["sleeper_id"])
        if change is not None:
            line += f" [MOVED: {change.old_team}→{change.new_team}]"
        print(line)
    return 0


def cmd_value_roster(args: argparse.Namespace, *, repo_root: Path | None = None) -> int:
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

    vorp_df = _read_vorp(root, args.season)
    roster_vorp = vorp_df.filter(pl.col("sleeper_id").is_in(list(roster.player_ids)))
    unranked_ids = set(roster.player_ids) - set(roster_vorp["sleeper_id"].to_list())

    breakdown = (
        roster_vorp.group_by("position")
        .agg(
            [
                pl.col("vorp_season").sum().alias("total_vorp"),
                pl.col("vorp_season").mean().alias("avg_vorp"),
                pl.len().alias("count"),
            ]
        )
        .sort("total_vorp", descending=True)
    )

    print(f"roster_id={roster.roster_id} positional value breakdown:")
    for row in breakdown.to_dicts():
        print(
            f"  {row['position']:<3} n={row['count']} total_vorp={row['total_vorp']:7.1f} avg={row['avg_vorp']:6.1f}"
        )
    if unranked_ids:
        print(
            f"  (no VORP data for: {', '.join(sorted(unranked_ids))} — likely DEF or unmapped players)"
        )
    return 0
