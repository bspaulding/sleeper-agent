"""`draft board` — live best-available-by-value view across the draft.

Cross-references the pre-draft big board (`data/bigboard/<season>.csv`,
built and hand-reviewed ahead of the draft — see
docs/superpowers/specs/2026-08-23-draft-bigboard-design.md) against the
draft's public picks endpoint (no auth needed), excluding every player
who's already been picked — live or pre-filled `is_keeper: true` — from the
"available" list. The big board supplies the ranking order (rookies inline,
ties pre-broken); NEED/FLEX/SURPLUS and tier annotation are still computed
live against the current roster. The live mode defaults to a Textual TUI
(`board_app.DraftBoardApp`, clear/redraw on every new pick, toggleable picks
stream panel); `watch_board` below is the plain line-based loop the TUI
falls back to when stdout isn't a tty (piped/logged, unattended Monitor
runs), polling and re-rendering only when the picked-player set actually
changes.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sleeper_agent.draft_tools.bigboard import BigboardRow
from sleeper_agent.models.sleeper import Draft, DraftPick
from sleeper_agent.sleeper_client.draft import fetch_draft_picks
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL
from sleeper_agent.value.team_changes import TeamChange

FLEX_ELIGIBLE_POSITIONS = frozenset({"RB", "WR", "TE"})


def _flush_print(s: str) -> None:
    print(s, flush=True)


@dataclass(frozen=True)
class RosterRequirement:
    hard_min: dict[str, int]
    flex_capacity: int


def roster_requirement_from_draft(draft: Draft) -> RosterRequirement:
    return RosterRequirement(
        hard_min={
            "QB": draft.slots_qb,
            "RB": draft.slots_rb,
            "WR": draft.slots_wr,
            "TE": draft.slots_te,
            "DEF": draft.slots_def,
        },
        flex_capacity=draft.slots_flex,
    )


def remaining_flex_capacity(
    counts: dict[str, int], requirement: RosterRequirement
) -> int:
    """How many of the shared FLEX slots are still unclaimed, across every
    flex-eligible position at once — not evaluated independently per
    position. A player drafted past their own position's hard_min but into a
    still-open flex slot uses up one unit of this *shared* pool, regardless
    of which flex-eligible position they play; RB and WR aren't each granted
    their own private copy of `flex_capacity`."""
    used = sum(
        max(0, counts.get(position, 0) - requirement.hard_min.get(position, 0))
        for position in FLEX_ELIGIBLE_POSITIONS
    )
    return requirement.flex_capacity - used


def position_tag(
    position: str, count: int, requirement: RosterRequirement, remaining_flex: int
) -> str:
    """NEED/SURPLUS reflects only this position's own hard_min — never mixed
    with FLEX capacity, which is a separate, shared resource (see
    `remaining_flex_capacity`). A row can be both: a position already past
    its hard_min ("SURPLUS") can still be worth drafting if the shared FLEX
    pool has room ("SURPLUS, FLEX") — those are two independent facts about
    the roster, not one combined tier."""
    hard_min = requirement.hard_min.get(position, 0)
    if count < hard_min:
        return "NEED"
    if position in FLEX_ELIGIBLE_POSITIONS and remaining_flex > 0:
        return "SURPLUS, FLEX"
    return "SURPLUS"


def my_roster_positions(
    picks: Sequence[DraftPick],
    my_roster_id: int,
    *,
    my_draft_slot: int | None = None,
) -> dict[str, int]:
    """Count my drafted players by position.

    Sleeper's picks endpoint returns `roster_id: null` for every pick in a
    mock draft (there's no real league roster behind it), so matching by
    `roster_id` alone silently counts zero picks as mine for the entire
    mock-draft codepath (`--draft-id`/`--draft-slot`). `draft_slot` has no
    such gap — it's populated on every pick in both mock and league drafts —
    so when the caller resolved `my_roster_id` from `--draft-slot`, match on
    `draft_slot` instead; otherwise (the `--me`/`--roster-id` league path)
    fall back to `roster_id` as before.
    """
    counts: dict[str, int] = {}
    for pick in picks:
        owned = (
            pick.draft_slot == my_draft_slot
            if my_draft_slot is not None
            else pick.roster_id == my_roster_id
        )
        if not owned:
            continue
        position = pick.player_position or "UNK"
        counts[position] = counts.get(position, 0) + 1
    return counts


DEFAULT_TOP_N = 30


def bigboard_view(
    bigboard_rows: Sequence[BigboardRow],
    drafted_picks: list[DraftPick],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> list[BigboardRow]:
    drafted_ids = {pick.player_id for pick in drafted_picks}
    available = [row for row in bigboard_rows if row.player_id not in drafted_ids]
    return available[:top_n]


def compute_tiers(board: Sequence[BigboardRow]) -> dict[str, int]:
    tiers: dict[str, int] = {}
    by_position: dict[str, list[BigboardRow]] = {}
    for row in board:
        if row.source != "vorp":
            continue
        by_position.setdefault(row.position, []).append(row)
    for rows in by_position.values():
        rows.sort(key=lambda r: r.vorp or 0.0, reverse=True)
        tier = 1
        prev_vorp: float | None = None
        for row in rows:
            if prev_vorp is not None and _is_tier_break(prev_vorp, row.vorp or 0.0):
                tier += 1
            tiers[row.player_id] = tier
            prev_vorp = row.vorp
    return tiers


def _is_tier_break(prev_vorp: float, vorp: float) -> bool:
    if prev_vorp <= 0:
        return True
    return (prev_vorp - vorp) / prev_vorp >= 0.20


ROSTER_SUMMARY_POSITIONS = ("QB", "RB", "WR", "TE", "DEF")


def render_roster_summary(
    counts: dict[str, int], requirement: RosterRequirement
) -> str:
    parts = [
        f"{position} {counts.get(position, 0)}/{requirement.hard_min.get(position, 0)}"
        for position in ROSTER_SUMMARY_POSITIONS
    ]
    summary = "My roster so far: " + "  ".join(parts)
    if requirement.flex_capacity:
        flex_positions = "/".join(
            position
            for position in ROSTER_SUMMARY_POSITIONS
            if position in FLEX_ELIGIBLE_POSITIONS
        )
        summary += (
            f"  ({requirement.flex_capacity} FLEX slots shared across {flex_positions})"
        )
    return summary


def render_board(
    board: Sequence[BigboardRow],
    *,
    my_counts: dict[str, int] | None = None,
    requirement: RosterRequirement | None = None,
    team_changes: dict[str, TeamChange] | None = None,
    injury_statuses: dict[str, str] | None = None,
) -> str:
    annotation = (
        (my_counts, requirement)
        if my_counts is not None and requirement is not None
        else None
    )
    lines = []
    if annotation is not None:
        counts, req = annotation
        lines.append(render_roster_summary(counts, req))
        lines.append("")
    lines.append("Best available by value:")
    tiers = compute_tiers(board) if annotation is not None else {}
    remaining_flex = (
        remaining_flex_capacity(annotation[0], annotation[1])
        if annotation is not None
        else 0
    )
    team_changes = team_changes or {}
    injury_statuses = injury_statuses or {}
    for rank, row in enumerate(board, start=1):
        if row.source == "rookie":
            line = f"{rank:2d}. {row.name:<25} {row.position:<3} [ROOKIE R{row.draft_round}]"
        else:
            # A hand-edited bigboard CSV could have source="vorp" with an empty
            # `vorp` cell and still load fine (bigboard.py doesn't enforce the
            # pairing) — this runs inside watch_board's live polling loop, so a
            # bare TypeError here would end a live draft session. Render it
            # visibly instead of crashing.
            vorp_display = f"{row.vorp:7.1f}" if row.vorp is not None else "    n/a"
            line = f"{rank:2d}. {row.name:<25} {row.position:<3} vorp={vorp_display}"
        if annotation is not None:
            counts, req = annotation
            tag = position_tag(
                row.position, counts.get(row.position, 0), req, remaining_flex
            )
            if row.source == "vorp":
                tier = tiers.get(row.player_id, 1)
                line += f" tier={tier} [{tag}]"
            else:
                line += f" [{tag}]"
        change = team_changes.get(row.player_id)
        if change is not None:
            line += f" [MOVED: {change.old_team}→{change.new_team}]"
        status = injury_statuses.get(row.player_id)
        if status is not None:
            line += f" [INJ: {status}]"
        lines.append(line)
    return "\n".join(lines)


def render_board_for_picks(
    bigboard_rows: Sequence[BigboardRow],
    picks: Sequence[DraftPick],
    *,
    top_n: int = DEFAULT_TOP_N,
    my_roster_id: int | None = None,
    my_draft_slot: int | None = None,
    requirement: RosterRequirement | None = None,
    team_changes: dict[str, TeamChange] | None = None,
    injury_statuses: dict[str, str] | None = None,
) -> str:
    """Assemble + render the full board for a given picks list.

    The `bigboard_view` -> `my_roster_positions` -> `render_board` sequence
    (including the "only annotate when we know who 'me' is" gating on
    `my_roster_id`) was independently duplicated across `watch_board` and
    `draft board`'s one-shot path (and formerly the now-removed `draft
    watch-picks`'s on-my-turn board). This is that sequence, once.
    """
    picks_list = list(picks)
    board = bigboard_view(bigboard_rows, picks_list, top_n=top_n)
    my_counts = (
        my_roster_positions(picks_list, my_roster_id, my_draft_slot=my_draft_slot)
        if my_roster_id is not None
        else None
    )
    return render_board(
        board,
        my_counts=my_counts,
        requirement=requirement if my_roster_id is not None else None,
        team_changes=team_changes,
        injury_statuses=injury_statuses,
    )


def slot_for_pick(pick_no: int, num_teams: int) -> int:
    """Which draft slot owns a given overall pick number, standard snake order.

    Odd rounds go 1..num_teams ascending; even rounds reverse (num_teams..1).
    No 3rd-round-reversal — this league's drafts (and every mock run so far)
    use plain snake.
    """
    round_number = (pick_no - 1) // num_teams + 1
    pos_in_round = pick_no - (round_number - 1) * num_teams
    if round_number % 2 == 1:
        return pos_in_round
    return num_teams - pos_in_round + 1


def watch_board(
    draft_id: str,
    bigboard_rows: Sequence[BigboardRow],
    *,
    base_url: str = SLEEPER_BASE_URL,
    # Sleeper's documented limit is ~1000 req/min before risking an IP block; one GET per
    # poll at 1s is ~60 req/min (~6% of budget), so there's no rate-limit reason to poll
    # slower — see .claude/skills/draft.md's "During the draft" section.
    poll_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
    # Plain `print` fully block-buffers stdout when it isn't a tty (i.e. whenever
    # something is capturing/piping this process's output, like a background
    # watcher) — renders can sit unflushed for multiple picks. `--watch` exists
    # specifically to be consumed live, so flush every render explicitly.
    render: Callable[[str], None] = _flush_print,
    fetch_picks: Callable[..., list[DraftPick]] = fetch_draft_picks,
    my_roster_id: int | None = None,
    my_draft_slot: int | None = None,
    requirement: RosterRequirement | None = None,
    team_changes: dict[str, TeamChange] | None = None,
    injury_statuses: dict[str, str] | None = None,
    # Machine-readable "it's your turn" signal for an unattended watcher (an
    # agent, not a human reading the TUI) — see .claude/skills/draft.md. Needs
    # my_draft_slot + num_teams + total_picks to compute; silently does
    # nothing if any are missing, same no-annotation-by-default convention as
    # my_roster_id/my_draft_slot elsewhere in this module.
    notify_my_turn: bool = False,
    num_teams: int | None = None,
    total_picks: int | None = None,
    notify: Callable[[str], None] = _flush_print,
) -> None:
    previous_drafted_ids: frozenset[str] | None = None
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        picks = fetch_picks(draft_id, base_url=base_url)
        drafted_ids = frozenset(pick.player_id for pick in picks)
        if drafted_ids != previous_drafted_ids:
            rendered = render_board_for_picks(
                bigboard_rows,
                picks,
                my_roster_id=my_roster_id,
                my_draft_slot=my_draft_slot,
                requirement=requirement,
                team_changes=team_changes,
                injury_statuses=injury_statuses,
            )
            render(rendered)
            if (
                notify_my_turn
                and my_draft_slot is not None
                and num_teams is not None
                and total_picks is not None
            ):
                picks_by_no = {pick.pick_no: pick for pick in picks}
                next_pick_no = next_unmade_pick_no(picks_by_no, total_picks)
                if (
                    next_pick_no is not None
                    and slot_for_pick(next_pick_no, num_teams) == my_draft_slot
                ):
                    round_number = (next_pick_no - 1) // num_teams + 1
                    notify(f"YOUR TURN: pick {next_pick_no} (round {round_number})")
            previous_drafted_ids = drafted_ids
        iteration += 1
        if max_iterations is None or iteration < max_iterations:
            sleep(poll_seconds)


def render_pick_line(pick: DraftPick, my_draft_slot: int | None) -> str:
    name = pick.player_name or pick.player_id
    position = pick.player_position or "?"
    team = pick.player_team or "?"
    line = f"Pick {pick.pick_no} (slot {pick.draft_slot}): {name} ({position}, {team})"
    if my_draft_slot is not None and pick.draft_slot == my_draft_slot:
        line += " <== MY PICK"
    return line


def next_unmade_pick_no(
    picks_by_no: dict[int, DraftPick], total_picks: int
) -> int | None:
    """Smallest pick_no <= total_picks that hasn't happened yet, or None if the
    draft is over.

    Not `len(picks_by_no) + 1` and not `max(picks_by_no) + 1`: Sleeper
    pre-fills `is_keeper: true` picks into the picks endpoint at their real
    `pick_no` from the very first poll (see this module's docstring and
    `tests/fixtures/sleeper/draft_picks.json`, which has live picks at 1-3
    sitting alongside keepers at 47/48). Both shortcuts would skip straight
    past the live picks still to come in the gap.
    """
    for pick_no in range(1, total_picks + 1):
        if pick_no not in picks_by_no:
            return pick_no
    return None


def picks_in_order(picks_by_no: dict[int, DraftPick]) -> list[DraftPick]:
    return [picks_by_no[pick_no] for pick_no in sorted(picks_by_no)]
