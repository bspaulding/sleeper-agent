"""`draft board` — live best-available-by-value view across the draft.

Cross-references `data/vorp` against the draft's public picks endpoint (no
auth needed), excluding every player who's already been picked — live or
pre-filled `is_keeper: true` — from the "available" list. `--watch` polls
and re-renders only when the picked-player set actually changes, and
(optionally) mirrors the current board to a decision-log-style file so an
unattended Routine run leaves a record.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sleeper_agent.draft_tools.rookies import TriagedRookie
from sleeper_agent.models.sleeper import Draft, DraftPick, Player
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


@dataclass(frozen=True)
class RookieWatchRow:
    player: Player
    draft_round: int
    news_excerpt: tuple[str, ...]


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


def board_view(
    vorp_df: pl.DataFrame, drafted_picks: list[DraftPick], *, top_n: int = 30
) -> pl.DataFrame:
    drafted_ids = {pick.player_id for pick in drafted_picks}
    available = vorp_df.filter(~pl.col("sleeper_id").is_in(list(drafted_ids)))
    return available.sort("vorp_season", descending=True).head(top_n)


def rookie_watch_rows(
    triaged_rookies: Sequence[TriagedRookie],
    drafted_picks: Sequence[DraftPick],
    *,
    news_by_sleeper_id: dict[str, list[str]] | None = None,
) -> list[RookieWatchRow]:
    """Available triaged rookies, cross-referenced against drafted picks.

    Mirrors `board_view`'s drafted-player exclusion, but stays a separate
    function/list rather than folding into `board_view`'s VORP-sorted
    output — triaged rookies have no VORP number to sort by (inventing a
    synthetic one would blend a qualitative triage judgment into a number
    the rest of the board treats as directly comparable), so they render as
    an unranked "Rookie watch" section instead (see `render_board`).
    """
    drafted_ids = {pick.player_id for pick in drafted_picks}
    news_by_sleeper_id = news_by_sleeper_id or {}
    return [
        RookieWatchRow(
            player=rookie.player,
            draft_round=rookie.draft_round,
            news_excerpt=tuple(news_by_sleeper_id.get(rookie.player.player_id, ())),
        )
        for rookie in triaged_rookies
        if rookie.player.player_id not in drafted_ids
    ]


def compute_tiers(board: pl.DataFrame) -> dict[str, int]:
    tiers: dict[str, int] = {}
    for position in sorted(set(board["position"].to_list())):
        rows = (
            board.filter(pl.col("position") == position)
            .sort("vorp_season", descending=True)
            .to_dicts()
        )
        tier = 1
        prev_vorp: float | None = None
        for row in rows:
            if prev_vorp is not None and _is_tier_break(prev_vorp, row["vorp_season"]):
                tier += 1
            tiers[row["sleeper_id"]] = tier
            prev_vorp = row["vorp_season"]
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
    board: pl.DataFrame,
    *,
    my_counts: dict[str, int] | None = None,
    requirement: RosterRequirement | None = None,
    rookie_watch: Sequence[RookieWatchRow] | None = None,
    team_changes: dict[str, TeamChange] | None = None,
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
    for rank, row in enumerate(board.to_dicts(), start=1):
        line = (
            f"{rank:2d}. {row['name']:<25} {row['position']:<3} "
            f"vorp={row['vorp_season']:7.1f}"
        )
        if annotation is not None:
            counts, req = annotation
            tier = tiers.get(row["sleeper_id"], 1)
            tag = position_tag(row["position"], counts.get(row["position"], 0), req)
            line += f" tier={tier} [{tag}]"
        change = team_changes.get(row["sleeper_id"])
        if change is not None:
            line += f" [MOVED: {change.old_team}→{change.new_team}]"
        lines.append(line)
    if rookie_watch:
        lines.append("")
        lines.append(
            "Rookie watch (triaged, not ranked against VORP — "
            "see wiki/team/rookie-evaluation.md):"
        )
        for entry in rookie_watch:
            line = (
                f"    {entry.player.name:<25} {entry.player.position:<3} "
                f"R{entry.draft_round}"
            )
            if entry.news_excerpt:
                line += f"  {entry.news_excerpt[0]}"
            lines.append(line)
    return "\n".join(lines)


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
    vorp_df: pl.DataFrame,
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
    triaged_rookies: Sequence[TriagedRookie] = (),
    rookie_news_by_sleeper_id: dict[str, list[str]] | None = None,
    team_changes: dict[str, TeamChange] | None = None,
) -> None:
    previous_drafted_ids: frozenset[str] | None = None
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        picks = fetch_picks(draft_id, base_url=base_url)
        drafted_ids = frozenset(pick.player_id for pick in picks)
        if drafted_ids != previous_drafted_ids:
            board = board_view(vorp_df, picks)
            my_counts = (
                my_roster_positions(
                    picks, my_roster_id, my_draft_slot=my_draft_slot
                )
                if my_roster_id is not None
                else None
            )
            rookie_watch = (
                rookie_watch_rows(
                    triaged_rookies, picks, news_by_sleeper_id=rookie_news_by_sleeper_id
                )
                if triaged_rookies
                else None
            )
            rendered = render_board(
                board,
                my_counts=my_counts,
                requirement=requirement if my_roster_id is not None else None,
                rookie_watch=rookie_watch,
                team_changes=team_changes,
            )
            render(rendered)
            if log_path is not None:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(f"# Draft board — live\n\n{rendered}\n")
            previous_drafted_ids = drafted_ids
        iteration += 1
        if max_iterations is None or iteration < max_iterations:
            sleep(poll_seconds)
