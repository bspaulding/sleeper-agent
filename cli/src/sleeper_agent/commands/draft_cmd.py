"""`draft` command group: keeper eligibility/cost, live best-available board."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from sleeper_agent.config import data_dir, decisions_dir, find_repo_root, wiki_dir
from sleeper_agent.draft_tools.board import (
    RosterRequirement,
    render_board_for_picks,
    roster_requirement_from_draft,
    watch_board,
    watch_picks,
)
from sleeper_agent.draft_tools.keepers import (
    KeeperCandidate,
    build_season_chain,
    infer_total_rounds,
    rank_keeper_candidates,
)
from sleeper_agent.draft_tools.rookies import TriagedRookie, triage_rookies
from sleeper_agent.models.sleeper import Draft, DraftPick
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
from sleeper_agent.stats.draft_picks_sync import DRAFT_PICKS_SCHEMA_VERSION
from sleeper_agent.stats.sync import IDS_SCHEMA_VERSION, WEEKLY_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table
from sleeper_agent.value.scoring import (
    filter_rostered,
    injury_statuses,
    recent_news_excerpt,
)
from sleeper_agent.value.team_changes import (
    TeamChange,
    detect_team_changes,
    triage_team_changes,
)

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
    board_parser.add_argument(
        "--exclude-players",
        default=None,
        help=(
            "Comma-separated sleeper_ids to drop from the board (e.g. projected "
            "league keepers when practicing against a mock draft, which has no "
            "keeper data of its own). Real drafts don't need this: is_keeper picks "
            "are already excluded from the live feed."
        ),
    )
    board_parser.set_defaults(func=cmd_draft_board)

    watch_picks_parser = draft_subparsers.add_parser(
        "watch-picks",
        help="Live pick-by-pick tracker; auto-fetches the board the instant it's your turn",
    )
    watch_picks_source = watch_picks_parser.add_mutually_exclusive_group(required=True)
    watch_picks_source.add_argument("--league-id")
    watch_picks_source.add_argument(
        "--draft-id",
        help=(
            "Draft ID directly, bypassing league lookup — needed for a Sleeper mock "
            "draft, which has no league of its own. Requires --value-season."
        ),
    )
    watch_picks_parser.add_argument(
        "--rounds",
        type=int,
        default=15,
        help=(
            "Board display depth only (rounds x teams rows). Draft *length* comes "
            "from the draft object's own settings.rounds, not this."
        ),
    )
    watch_picks_parser.add_argument("--value-season", default=None)
    watch_picks_parser.add_argument(
        "--num-teams",
        type=int,
        default=12,
        help=(
            "Ignored here: turn-detection geometry is read from the draft object's "
            "own settings.teams. Accepted for symmetry with `draft board`."
        ),
    )
    watch_picks_parser.add_argument("--me", action="store_true")
    watch_picks_parser.add_argument("--roster-id", type=int, default=None)
    watch_picks_parser.add_argument(
        "--draft-slot",
        type=int,
        default=None,
        help=(
            "Resolve my roster_id from this draft's slot_to_roster_id map — needed for "
            "a mock draft (no stable roster_id across seasons), or as an alternative to "
            "--me/--roster-id in league mode."
        ),
    )
    watch_picks_parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="Picks-endpoint poll interval — cheap enough to poll faster than draft board --watch's 5s default.",
    )
    watch_picks_parser.add_argument(
        "--exclude-players",
        default=None,
        help=(
            "Comma-separated sleeper_ids to drop from the board (e.g. projected "
            "league keepers for a mock draft). Real drafts don't need this."
        ),
    )
    watch_picks_parser.set_defaults(func=cmd_draft_watch_picks)


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


def _read_draft_picks(root: Path) -> pl.DataFrame | None:
    path = data_dir(root) / "nfl" / "draft_picks.parquet"
    if not path.exists():
        return None
    return read_table(path, expected_schema_version=DRAFT_PICKS_SCHEMA_VERSION)


def _triaged_rookies(
    root: Path, players_df: pl.DataFrame | None
) -> list[TriagedRookie]:
    """Best-effort rookie triage list for `draft board`'s "Rookie watch" section.

    Absent `data/nfl/draft_picks.parquet` (not yet synced via `stats
    draft-picks sync`) or `data/sleeper/players.parquet`, this is just an
    empty list — the board renders exactly as it does today, same
    no-annotation-by-default convention as `--me`/`--roster-id`.
    """
    draft_picks_df = _read_draft_picks(root)
    if draft_picks_df is None or players_df is None:
        return []
    return triage_rookies(draft_picks_df, players_df)


def _rookie_news_by_sleeper_id(
    root: Path, rookies: list[TriagedRookie]
) -> dict[str, list[str]]:
    wiki_root = wiki_dir(root)
    return {
        rookie.player.player_id: recent_news_excerpt(
            wiki_root, rookie.player.player_id, limit=1
        )
        for rookie in rookies
    }


def _team_changes_by_sleeper_id(
    root: Path, season: str, players_df: pl.DataFrame | None
) -> dict[str, TeamChange]:
    """Best-effort triaged role-changer (FA/trade) lookup for draft board's
    `[MOVED: ...]` tag.

    Absent `data/stats/weekly/{season}.parquet`, `data/stats/ids.parquet`, or
    `data/sleeper/players.parquet`, this is just an empty dict — the board
    renders exactly as it does today, same no-annotation-by-default
    convention as `--me`/`--roster-id`/rookie watch.
    """
    weekly_path = data_dir(root) / "stats" / "weekly" / f"{season}.parquet"
    ids_path = data_dir(root) / "stats" / "ids.parquet"
    if players_df is None or not weekly_path.exists() or not ids_path.exists():
        return {}
    weekly = read_table(weekly_path, expected_schema_version=WEEKLY_SCHEMA_VERSION)
    ids = read_table(ids_path, expected_schema_version=IDS_SCHEMA_VERSION)
    changes = triage_team_changes(detect_team_changes(weekly, players_df, ids))
    return {change.sleeper_id: change for change in changes}


@dataclass(frozen=True)
class DraftContext:
    draft_id: str
    value_season: str
    num_teams: int
    draft: Draft
    vorp_df: pl.DataFrame
    my_roster_id: int | None
    my_draft_slot: int | None
    requirement: RosterRequirement
    triaged_rookies: list[TriagedRookie]
    rookie_news: dict[str, list[str]]
    team_changes: dict[str, TeamChange]
    injury_statuses: dict[str, str]


def parse_excluded_players(raw: str | None) -> list[str]:
    """Parse `--exclude-players "2449,4943"` into a clean sleeper_id list.

    Tolerates whitespace and trailing commas; empty/None input means no
    exclusions. Used by `draft board`/`draft watch-picks` to drop projected
    league keepers when practicing against a mock draft (which carries no
    keeper data of its own).
    """
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _injury_statuses_by_sleeper_id(
    root: Path, players_df: pl.DataFrame | None
) -> dict[str, str]:
    """Best-effort live Sleeper injury designations for draft board's
    `[INJ: ...]` tag.

    Absent `data/sleeper/players.parquet`, this is just an empty dict — the
    board renders exactly as it does today, same no-annotation-by-default
    convention as `--me`/`--roster-id`/rookie watch/`[MOVED: ...]`.
    """
    if players_df is None:
        return {}
    return injury_statuses(players_df)


def _resolve_draft_context(
    args: argparse.Namespace, root: Path, *, base_url: str
) -> DraftContext | None:
    """Shared setup for `draft board` and `draft watch-picks`: resolve the
    draft/value-season/num-teams (from --league-id or --draft-id), resolve
    "me" (--me/--roster-id/--draft-slot), and load VORP + rookie-watch +
    team-changes data. Prints its own error message and returns None on
    failure, same convention as the code it was extracted from.
    """
    if args.draft_id is not None:
        if args.value_season is None:
            print(
                "--value-season is required with --draft-id (e.g. for a Sleeper mock "
                "draft, there's no league to infer a season from)"
            )
            return None
        draft_id = args.draft_id
        value_season = args.value_season
        num_teams = args.num_teams
    else:
        league = fetch_league(args.league_id, base_url=base_url)
        if league.draft_id is None:
            print(f"league {args.league_id} has no draft_id")
            return None
        draft_id = league.draft_id
        value_season = args.value_season or league.season
        num_teams = max(league.settings.num_teams, 1)

    vorp_df = _read_vorp(root, value_season)
    if vorp_df is None:
        print(
            f"no VORP data for season {value_season} — run `stats vorp --season {value_season}` first"
        )
        return None

    draft = fetch_draft(draft_id, base_url=base_url)
    requirement = roster_requirement_from_draft(draft)
    my_roster_id: int | None = None
    my_draft_slot: int | None = None
    if args.draft_slot is not None:
        my_roster_id = draft.slot_to_roster_id.get(args.draft_slot)
        if my_roster_id is None:
            print(
                f"--draft-slot {args.draft_slot} is not in this draft's "
                f"slot_to_roster_id (valid slots: {sorted(draft.slot_to_roster_id)})"
            )
            return None
        my_draft_slot = args.draft_slot
    elif args.me:
        my_roster_id = ME_ROSTER_ID
    elif args.roster_id is not None:
        my_roster_id = args.roster_id

    players_df = _read_players(root)
    triaged_rookies = _triaged_rookies(root, players_df)
    rookie_news = _rookie_news_by_sleeper_id(root, triaged_rookies)
    team_changes = _team_changes_by_sleeper_id(root, value_season, players_df)
    if players_df is not None:
        vorp_df = filter_rostered(vorp_df, players_df)

    # Mock-draft practice aid: projected league keepers are known to be off the
    # pool but don't appear on a mock's picks endpoint, so without this the
    # board overstates availability. Filtering here means every downstream
    # consumer (board_view, tiers, watch loops) sees the same reduced pool.
    excluded = parse_excluded_players(getattr(args, "exclude_players", None))
    if excluded:
        vorp_df = vorp_df.filter(~pl.col("sleeper_id").is_in(excluded))

    return DraftContext(
        draft_id=draft_id,
        value_season=value_season,
        num_teams=num_teams,
        draft=draft,
        vorp_df=vorp_df,
        my_roster_id=my_roster_id,
        my_draft_slot=my_draft_slot,
        requirement=requirement,
        triaged_rookies=triaged_rookies,
        rookie_news=rookie_news,
        team_changes=team_changes,
        injury_statuses=_injury_statuses_by_sleeper_id(root, players_df),
    )


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
    context = _resolve_draft_context(args, root, base_url=base_url)
    if context is None:
        return 1

    top_n = args.rounds * context.num_teams

    if args.watch:
        log_path = (
            decisions_dir(root)
            / context.value_season
            / f"{today().isoformat()}-draft-live.md"
        )
        watch_board(
            context.draft_id,
            context.vorp_df,
            base_url=base_url,
            log_path=log_path,
            max_iterations=max_watch_iterations,
            my_roster_id=context.my_roster_id,
            my_draft_slot=context.my_draft_slot,
            requirement=context.requirement
            if context.my_roster_id is not None
            else None,
            triaged_rookies=context.triaged_rookies,
            rookie_news_by_sleeper_id=context.rookie_news,
            team_changes=context.team_changes,
            injury_statuses=context.injury_statuses,
        )
        return 0

    picks = fetch_draft_picks(context.draft_id, base_url=base_url)
    print(_render_context_board(context, picks, top_n=top_n))
    return 0


def _render_context_board(
    context: DraftContext, picks: list[DraftPick], *, top_n: int
) -> str:
    return render_board_for_picks(
        context.vorp_df,
        picks,
        top_n=top_n,
        my_roster_id=context.my_roster_id,
        my_draft_slot=context.my_draft_slot,
        requirement=context.requirement,
        triaged_rookies=context.triaged_rookies,
        rookie_news_by_sleeper_id=context.rookie_news,
        team_changes=context.team_changes,
        injury_statuses=context.injury_statuses,
    )


def cmd_draft_watch_picks(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
    max_iterations: int | None = None,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    if args.poll_seconds < 0:
        print(f"--poll-seconds must be >= 0 (got {args.poll_seconds})")
        return 1
    context = _resolve_draft_context(args, root, base_url=base_url)
    if context is None:
        return 1

    # Draft geometry comes from the Draft object Sleeper itself returned, not
    # from --num-teams/--rounds. Those flags default to 12/15 and are silently
    # wrong for any other league shape — and a wrong num_teams makes
    # `slot_for_pick`'s snake math wrong for every round >= 2 with no error.
    draft_num_teams = context.draft.num_teams
    draft_rounds = context.draft.rounds
    if draft_num_teams <= 0 or draft_rounds <= 0:
        print(
            f"draft {context.draft_id} reports no usable geometry "
            f"(settings.teams={draft_num_teams}, settings.rounds={draft_rounds}) — "
            "turn detection needs both"
        )
        return 1

    turn_detection_slot = context.my_draft_slot
    if turn_detection_slot is None and context.my_roster_id is not None:
        turn_detection_slot = next(
            (
                slot
                for slot, roster_id in context.draft.slot_to_roster_id.items()
                if roster_id == context.my_roster_id
            ),
            None,
        )
        if turn_detection_slot is None:
            print(
                f"warning: roster_id {context.my_roster_id} is not in this draft's "
                f"slot_to_roster_id (mapped slots: "
                f"{sorted(context.draft.slot_to_roster_id)}) — streaming picks "
                "without turn detection (no MY PICK markers, no board on your "
                "turn). Pass --draft-slot to fix."
            )

    top_n = args.rounds * draft_num_teams

    def render_full_board(picks: list[DraftPick]) -> str:
        return _render_context_board(context, picks, top_n=top_n)

    watch_picks(
        context.draft_id,
        num_teams=draft_num_teams,
        draft_type=context.draft.draft_type,
        my_draft_slot=turn_detection_slot,
        total_picks=draft_rounds * draft_num_teams,
        render_full_board=render_full_board,
        base_url=base_url,
        poll_seconds=args.poll_seconds,
        max_iterations=max_iterations,
    )
    return 0
