"""`draft` command group: keeper eligibility/cost, live best-available board.

`draft board` defaults to a live Textual TUI (`draft_tools.board_app`):
board clear/redraws on every new pick, with a toggleable picks-stream
panel (`p`/`Tab`). `--once` gives the old one-shot plain print. When stdout
isn't a tty (piped, logged, unattended Monitor runs) the TUI can't attach,
so it falls back to the plain line-based `watch_board` loop.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from sleeper_agent.config import data_dir, find_repo_root
from sleeper_agent.draft_tools.bigboard import (
    BigboardMalformedError,
    BigboardNotBuiltError,
    BigboardRow,
    BigboardUnresolvedRowError,
    filter_off_roster,
    load_bigboard,
)
from sleeper_agent.draft_tools.board import (
    RosterRequirement,
    render_board_for_picks,
    roster_requirement_from_draft,
    watch_board,
)
from sleeper_agent.draft_tools.board_app import DraftBoardApp, DraftBoardModel
from sleeper_agent.draft_tools.keepers import (
    DEFAULT_NUM_TEAMS,
    KeeperCandidate,
    build_season_chain,
    infer_total_rounds,
    load_latest_adp,
    rank_keeper_candidates,
)
from sleeper_agent.draft_tools.recap import (
    DraftNotCompleteError,
    build_team_recaps,
    check_draft_complete,
    recap_to_dict,
    render_recap_text,
)
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
from sleeper_agent.sleeper_client.league import fetch_league, fetch_rosters, fetch_users
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.stats.sync import IDS_SCHEMA_VERSION, WEEKLY_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table
from sleeper_agent.value.scoring import injury_statuses
from sleeper_agent.value.team_changes import (
    TeamChange,
    detect_team_changes,
    triage_team_changes,
)

ME_ROSTER_ID = 5
VORP_SCHEMA_VERSION = 2


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
        "board",
        help="Live best-available-by-value draft board (Textual TUI; --once for a one-shot print)",
    )
    board_source = board_parser.add_mutually_exclusive_group(required=True)
    board_source.add_argument("--league-id")
    board_source.add_argument(
        "--draft-id",
        help=(
            "Draft ID directly, bypassing league lookup — needed for a Sleeper mock "
            "draft, which has no league of its own. --value-season defaults to "
            "current year minus 1 if not given."
        ),
    )
    board_parser.add_argument(
        "--once",
        action="store_true",
        help="One-shot plain render (no TUI, no polling). Default is the live TUI.",
    )
    board_parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="Picks-endpoint poll interval (seconds), for both the TUI and the non-tty "
        "watch loop. Default 1.0 — ~60 req/min, well under Sleeper's ~1000 req/min budget.",
    )
    board_parser.add_argument(
        "--show-picks",
        action="store_true",
        help="Start with the picks stream panel visible (toggleable with p/Tab).",
    )
    board_parser.add_argument(
        "--rounds",
        type=int,
        default=15,
        help="Board display depth only (rounds x teams rows). Draft *length* comes from the draft object's own settings.rounds, not this.",
    )
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
        "--notify-my-turn",
        action="store_true",
        help=(
            "In the non-tty plain watch loop, print a 'YOUR TURN: pick N (round R)' "
            "line the moment the next unmade pick belongs to us — a machine-readable "
            "signal for an unattended watcher (see .claude/skills/draft.md). Requires "
            "--draft-slot (or --me/--roster-id resolving to a slot in this draft's "
            "slot_to_roster_id map); no-ops otherwise. Has no effect on --once or the TUI."
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

    recap_parser = draft_subparsers.add_parser(
        "recap", help="Post-draft recap data: picks joined against the big board"
    )
    recap_parser.add_argument("--draft-id", required=True)
    recap_parser.add_argument("--value-season", default=None)
    recap_parser.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable output for the draft-recap skill. Default is a "
        "human-readable per-team table.",
    )
    recap_parser.set_defaults(func=cmd_draft_recap)


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


def _team_changes_by_sleeper_id(
    root: Path, season: str, players_df: pl.DataFrame | None
) -> dict[str, TeamChange]:
    """Best-effort triaged role-changer (FA/trade) lookup for draft board's
    `[MOVED: ...]` tag.

    Absent `data/stats/weekly/{season}.parquet`, `data/stats/ids.parquet`, or
    `data/sleeper/players.parquet`, this is just an empty dict — the board
    renders exactly as it does today, same no-annotation-by-default
    convention as `--me`/`--roster-id`.
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
    bigboard_rows: list[BigboardRow]
    my_roster_id: int | None
    my_draft_slot: int | None
    requirement: RosterRequirement
    team_changes: dict[str, TeamChange]
    injury_statuses: dict[str, str]


def parse_excluded_players(raw: str | None) -> list[str]:
    """Parse `--exclude-players "2449,4943"` into a clean sleeper_id list.

    Tolerates whitespace and trailing commas; empty/None input means no
    exclusions. Used by `draft board` to drop projected
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
    convention as `--me`/`--roster-id`/`[MOVED: ...]`.
    """
    if players_df is None:
        return {}
    return injury_statuses(players_df)


def _resolve_draft_context(
    args: argparse.Namespace,
    root: Path,
    *,
    base_url: str,
    today: Callable[[], date] = date.today,
) -> DraftContext | None:
    """Shared setup for `draft board` (TUI, --once, and non-tty fallback):
    draft/value-season/num-teams (from --league-id or --draft-id), resolve
    "me" (--me/--roster-id/--draft-slot), and load the big board + team-
    changes data. Prints its own error message and returns None on failure,
    same convention as the code it was extracted from.
    """
    if args.draft_id is not None:
        if args.value_season is None:
            value_season = str(today().year - 1)
            print(
                f"--value-season not given with --draft-id; defaulting to {value_season} "
                "(current year minus 1, the most recently completed season pre-season)"
            )
        else:
            value_season = args.value_season
        draft_id = args.draft_id
        num_teams = args.num_teams
    else:
        league = fetch_league(args.league_id, base_url=base_url)
        if league.draft_id is None:
            print(f"league {args.league_id} has no draft_id")
            return None
        draft_id = league.draft_id
        if args.value_season is None:
            value_season = str(int(league.season) - 1)
            print(
                f"--value-season not given with --league-id; defaulting to {value_season} "
                "(league season minus 1, the most recently completed season pre-season — "
                f"never {league.season} itself, since that season's stats/VORP don't exist "
                "until after it's played)"
            )
        else:
            value_season = args.value_season
        num_teams = max(league.settings.num_teams, 1)

    try:
        bigboard_rows = load_bigboard(root, value_season)
    except (
        BigboardNotBuiltError,
        BigboardUnresolvedRowError,
        BigboardMalformedError,
    ) as exc:
        print(str(exc))
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
    team_changes = _team_changes_by_sleeper_id(root, value_season, players_df)
    if players_df is not None:
        bigboard_rows = filter_off_roster(bigboard_rows, players_df)

    # Mock-draft practice aid: projected league keepers are known to be off the
    # pool but don't appear on a mock's picks endpoint, so without this the
    # board overstates availability. Filtering here means every downstream
    # consumer (bigboard_view, tiers, watch loops) sees the same reduced pool.
    excluded = parse_excluded_players(getattr(args, "exclude_players", None))
    if excluded:
        bigboard_rows = [row for row in bigboard_rows if row.player_id not in excluded]

    return DraftContext(
        draft_id=draft_id,
        value_season=value_season,
        num_teams=num_teams,
        draft=draft,
        bigboard_rows=bigboard_rows,
        my_roster_id=my_roster_id,
        my_draft_slot=my_draft_slot,
        requirement=requirement,
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

    adp_snapshot = load_latest_adp(root)
    adp_pick_by_player_id = adp_snapshot[1] if adp_snapshot is not None else None
    adp_snapshot_date = adp_snapshot[0] if adp_snapshot is not None else None

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
                player_id,
                roster.roster_id,
                season_chain,
                picks_by_season,
                total_rounds,
                adp_pick_by_player_id=adp_pick_by_player_id,
                adp_snapshot_date=adp_snapshot_date,
                num_teams=DEFAULT_NUM_TEAMS,
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
            case KeeperEligibleUndraftedDefault(
                cost_round=cost, adp_pick=adp_pick, adp_snapshot_date=adp_date
            ):
                vorp_display = (
                    f"{candidate.vorp_season:.1f}"
                    if candidate.vorp_season is not None
                    else "n/a"
                )
                if adp_pick is not None:
                    print(
                        f"  ELIGIBLE  {candidate.name:<25} cost=R{cost} "
                        f"(ADP-reset: pick #{adp_pick} as of {adp_date}) "
                        f"vorp={vorp_display}"
                    )
                else:
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


def _team_names_by_slot(draft: Draft, *, base_url: str) -> dict[int, str]:
    """Real team names for a league draft (`draft.league_id` non-empty);
    empty dict for a mock draft, where `build_team_recaps` falls back to
    `"Slot N"` labels on its own.
    """
    if not draft.league_id:
        return {}
    rosters = fetch_rosters(draft.league_id, base_url=base_url)
    users = fetch_users(draft.league_id, base_url=base_url)
    user_by_id = {user.user_id: user for user in users}
    owner_by_roster_id = {roster.roster_id: roster.owner_id for roster in rosters}
    names: dict[int, str] = {}
    for slot, roster_id in draft.slot_to_roster_id.items():
        owner_id = owner_by_roster_id.get(roster_id)
        user = user_by_id.get(owner_id) if owner_id is not None else None
        if user is not None:
            names[slot] = user.team_name or user.display_name
    return names


def cmd_draft_recap(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
    today: Callable[[], date] = date.today,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    if args.value_season is None:
        value_season = str(today().year - 1)
        print(
            f"--value-season not given; defaulting to {value_season} "
            "(current year minus 1, the most recently completed season pre-season)"
        )
    else:
        value_season = args.value_season

    draft = fetch_draft(args.draft_id, base_url=base_url)
    picks = fetch_draft_picks(args.draft_id, base_url=base_url)
    try:
        check_draft_complete(draft, picks)
    except DraftNotCompleteError as exc:
        print(str(exc))
        return 1

    try:
        bigboard_rows = load_bigboard(root, value_season)
    except (
        BigboardNotBuiltError,
        BigboardUnresolvedRowError,
        BigboardMalformedError,
    ) as exc:
        print(str(exc))
        return 1

    team_names = _team_names_by_slot(draft, base_url=base_url)
    teams = build_team_recaps(picks, bigboard_rows, team_names)

    if args.json:
        print(json.dumps(recap_to_dict(draft, value_season, teams)))
    else:
        print(render_recap_text(teams))
    return 0


def _resolve_turn_detection_slot(context: DraftContext) -> int | None:
    """`my_draft_slot` if given directly, else derived from `my_roster_id`
    via this draft's `slot_to_roster_id` map (needed for --me/--roster-id
    without --draft-slot). Returns None, silently, if neither resolves —
    callers that need turn detection are responsible for warning; this is
    shared by both the TUI and the non-tty --notify-my-turn path.
    """
    if context.my_draft_slot is not None:
        return context.my_draft_slot
    if context.my_roster_id is None:
        return None
    return next(
        (
            slot
            for slot, roster_id in context.draft.slot_to_roster_id.items()
            if roster_id == context.my_roster_id
        ),
        None,
    )


def cmd_draft_board(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
    today: Callable[[], date] = date.today,
    max_watch_iterations: int | None = None,
    is_tty: Callable[[], bool] | None = None,
    run_board_tui: Callable[..., int] | None = None,
) -> int:
    """Live draft board. Modes, in dispatch order:

    1. `--once` — one-shot plain print (the pre-TUI default).
    2. non-tty stdout — plain line-based `watch_board` loop (piped/logged/
       unattended Monitor runs; the TUI can't attach to a pipe).
    3. tty stdout — the Textual TUI (`_run_board_tui`), which is the default.
    """
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    if not args.once and args.poll_seconds < 0:
        print(f"--poll-seconds must be >= 0 (got {args.poll_seconds})")
        return 1
    context = _resolve_draft_context(args, root, base_url=base_url, today=today)
    if context is None:
        return 1

    if args.once:
        picks = fetch_draft_picks(context.draft_id, base_url=base_url)
        top_n = args.rounds * context.num_teams
        print(_render_context_board(context, picks, top_n=top_n))
        return 0

    tty = is_tty() if is_tty is not None else sys.stdout.isatty()
    if not tty:
        notify_my_turn = getattr(args, "notify_my_turn", False)
        turn_detection_slot = _resolve_turn_detection_slot(context)
        if (
            notify_my_turn
            and turn_detection_slot is None
            and context.my_roster_id is not None
        ):
            print(
                f"warning: roster_id {context.my_roster_id} is not in this draft's "
                f"slot_to_roster_id (mapped slots: "
                f"{sorted(context.draft.slot_to_roster_id)}) — --notify-my-turn has "
                "nothing to match against. Pass --draft-slot to fix."
            )
        watch_board(
            context.draft_id,
            context.bigboard_rows,
            base_url=base_url,
            poll_seconds=args.poll_seconds,
            max_iterations=max_watch_iterations,
            my_roster_id=context.my_roster_id,
            my_draft_slot=turn_detection_slot,
            requirement=context.requirement
            if context.my_roster_id is not None
            else None,
            team_changes=context.team_changes,
            injury_statuses=context.injury_statuses,
            notify_my_turn=notify_my_turn,
            num_teams=context.draft.num_teams,
            total_picks=context.draft.rounds * context.draft.num_teams,
        )
        return 0

    if run_board_tui is not None:
        return run_board_tui(context, args, base_url=base_url)
    return _run_board_tui(context, args, base_url=base_url)


def _run_board_tui(
    context: DraftContext, args: argparse.Namespace, *, base_url: str
) -> int:
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

    turn_detection_slot = _resolve_turn_detection_slot(context)
    if turn_detection_slot is None and context.my_roster_id is not None:
        print(
            f"warning: roster_id {context.my_roster_id} is not in this draft's "
            f"slot_to_roster_id (mapped slots: "
            f"{sorted(context.draft.slot_to_roster_id)}) — streaming picks "
            "without turn detection (no MY PICK markers, no your-turn "
            "banner). Pass --draft-slot to fix."
        )

    model = DraftBoardModel(
        context.bigboard_rows,
        top_n=args.rounds * draft_num_teams,
        num_teams=draft_num_teams,
        draft_type=context.draft.draft_type,
        total_picks=draft_rounds * draft_num_teams,
        my_roster_id=context.my_roster_id,
        my_draft_slot=turn_detection_slot,
        requirement=context.requirement,
        team_changes=context.team_changes,
        injury_statuses=context.injury_statuses,
    )
    app = DraftBoardApp(
        model,
        draft_id=context.draft_id,
        poll_seconds=args.poll_seconds,
        show_picks=args.show_picks,
        base_url=base_url,
    )
    app.run()
    return 0


def _render_context_board(
    context: DraftContext, picks: list[DraftPick], *, top_n: int
) -> str:
    return render_board_for_picks(
        context.bigboard_rows,
        picks,
        top_n=top_n,
        my_roster_id=context.my_roster_id,
        my_draft_slot=context.my_draft_slot,
        requirement=context.requirement,
        team_changes=context.team_changes,
        injury_statuses=context.injury_statuses,
    )
