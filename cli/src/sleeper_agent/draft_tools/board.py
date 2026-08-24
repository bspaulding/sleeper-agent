"""`draft board` — live best-available-by-value view across the draft.

Cross-references the pre-draft big board (`data/bigboard/<season>.csv`,
built and hand-reviewed ahead of the draft — see
docs/superpowers/specs/2026-08-23-draft-bigboard-design.md) against the
draft's public picks endpoint (no auth needed), excluding every player
who's already been picked — live or pre-filled `is_keeper: true` — from the
"available" list. The big board supplies the ranking order (rookies inline,
ties pre-broken); NEED/FLEX/SURPLUS and tier annotation are still computed
live against the current roster. `--watch` polls and re-renders only when
the picked-player set actually changes, and (optionally) mirrors the current
board to a decision-log-style file so an unattended Routine run leaves a
record.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from requests import RequestException

from sleeper_agent.draft_tools.bigboard import BigboardRow
from sleeper_agent.models.sleeper import Draft, DraftPick
from sleeper_agent.sleeper_client.draft import fetch_draft_picks
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL, SleeperHTTPError
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


def position_tag(position: str, count: int, requirement: RosterRequirement) -> str:
    hard_min = requirement.hard_min.get(position, 0)
    if count < hard_min:
        return "NEED"
    flex_ceiling = hard_min + (
        requirement.flex_capacity if position in FLEX_ELIGIBLE_POSITIONS else 0
    )
    if count < flex_ceiling:
        return "FLEX"
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
            tag = position_tag(row.position, counts.get(row.position, 0), req)
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
    `my_roster_id`) was independently duplicated in three places —
    `watch_board`, `draft board`'s one-shot path, and `draft watch-picks`'
    on-my-turn board. This is that sequence, once.
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
    # poll at 5s is ~12 req/min (~1% of budget), so there's no rate-limit reason to poll
    # slower — see .claude/skills/draft.md's "During the draft" section.
    poll_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
    # Plain `print` fully block-buffers stdout when it isn't a tty (i.e. whenever
    # something is capturing/piping this process's output, like a background
    # watcher) — renders can sit unflushed for multiple picks. `--watch` exists
    # specifically to be consumed live, so flush every render explicitly.
    render: Callable[[str], None] = _flush_print,
    fetch_picks: Callable[..., list[DraftPick]] = fetch_draft_picks,
    log_path: Path | None = None,
    my_roster_id: int | None = None,
    my_draft_slot: int | None = None,
    requirement: RosterRequirement | None = None,
    team_changes: dict[str, TeamChange] | None = None,
    injury_statuses: dict[str, str] | None = None,
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
            if log_path is not None:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(f"# Draft board — live\n\n{rendered}\n")
            previous_drafted_ids = drafted_ids
        iteration += 1
        if max_iterations is None or iteration < max_iterations:
            sleep(poll_seconds)


def _render_pick_line(pick: DraftPick, my_draft_slot: int | None) -> str:
    name = pick.player_name or pick.player_id
    position = pick.player_position or "?"
    team = pick.player_team or "?"
    line = f"Pick {pick.pick_no} (slot {pick.draft_slot}): {name} ({position}, {team})"
    if my_draft_slot is not None and pick.draft_slot == my_draft_slot:
        line += " <== MY PICK"
    return line


def _next_unmade_pick_no(
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


def _picks_in_order(picks_by_no: dict[int, DraftPick]) -> list[DraftPick]:
    return [picks_by_no[pick_no] for pick_no in sorted(picks_by_no)]


def watch_picks(
    draft_id: str,
    *,
    num_teams: int,
    draft_type: str,
    my_draft_slot: int | None,
    total_picks: int,
    render_full_board: Callable[[list[DraftPick]], str],
    base_url: str = SLEEPER_BASE_URL,
    poll_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
    render: Callable[[str], None] = _flush_print,
    fetch_picks: Callable[..., list[DraftPick]] = fetch_draft_picks,
) -> None:
    """Stream one line per new pick; auto-render the full board the instant
    the next pick is mine.

    Deliberately lighter-weight than `watch_board`: it never reprints the
    whole board for picks that aren't mine, and only fetches/renders the
    board once per "my turn" (not on every poll while the human is still on
    the clock) — see `.claude/skills/draft.md`'s "Preferred live setup".

    Progress is tracked as an accumulated `pick_no -> DraftPick` map, merged
    into (never replaced) from each fetch, rather than as a count of picks
    seen. Counting assumes the picks endpoint is a contiguous prefix ordered
    by `pick_no`, which is false in this league: keeper picks arrive
    pre-filled at their real `pick_no` (47, 48, ...) from the first poll, so
    a count-based "next pick" jumps clean over every live pick still to come
    below them. Keying by `pick_no` also makes a transiently short/partial
    response a structural no-op — it can only fail to add entries, never drop
    or re-print ones already seen — so no separate shrinking-response guard
    is needed.
    """
    picks_by_no: dict[int, DraftPick] = {}
    announced_pick_no: int | None = None
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        try:
            picks = fetch_picks(draft_id, base_url=base_url)
        except (SleeperHTTPError, RequestException) as exc:
            # This command is built to run unattended under `Monitor` for the
            # hours a real draft takes; a single timeout/DNS blip/reset must not
            # end live tracking. Warn and retry on the next poll instead.
            render(f"fetch failed, retrying: {exc}")
        else:
            for pick in sorted(picks, key=lambda p: p.pick_no):
                is_new = pick.pick_no not in picks_by_no
                picks_by_no[pick.pick_no] = pick
                if is_new:
                    render(_render_pick_line(pick, my_draft_slot))

            if draft_type == "snake" and my_draft_slot is not None:
                next_pick_no = _next_unmade_pick_no(picks_by_no, total_picks)
                if (
                    next_pick_no is not None
                    and slot_for_pick(next_pick_no, num_teams) == my_draft_slot
                    and announced_pick_no != next_pick_no
                ):
                    render(render_full_board(_picks_in_order(picks_by_no)))
                    announced_pick_no = next_pick_no

            if len(picks_by_no) >= total_picks:
                return

        iteration += 1
        if max_iterations is None or iteration < max_iterations:
            sleep(poll_seconds)
