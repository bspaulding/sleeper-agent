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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sleeper_agent.models.sleeper import Draft, DraftPick
from sleeper_agent.sleeper_client.draft import fetch_draft_picks
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL

FLEX_ELIGIBLE_POSITIONS = frozenset({"RB", "WR", "TE"})


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


def board_view(
    vorp_df: pl.DataFrame, drafted_picks: list[DraftPick], *, top_n: int = 30
) -> pl.DataFrame:
    drafted_ids = {pick.player_id for pick in drafted_picks}
    available = vorp_df.filter(~pl.col("sleeper_id").is_in(list(drafted_ids)))
    return available.sort("vorp_season", descending=True).head(top_n)


def render_board(board: pl.DataFrame) -> str:
    lines = ["Best available by value:"]
    for rank, row in enumerate(board.to_dicts(), start=1):
        lines.append(
            f"{rank:2d}. {row['name']:<25} {row['position']:<3} vorp={row['vorp_season']:7.1f}"
        )
    return "\n".join(lines)


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
    render: Callable[[str], None] = print,
    fetch_picks: Callable[..., list[DraftPick]] = fetch_draft_picks,
    log_path: Path | None = None,
) -> None:
    previous_drafted_ids: frozenset[str] | None = None
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        picks = fetch_picks(draft_id, base_url=base_url)
        drafted_ids = frozenset(pick.player_id for pick in picks)
        if drafted_ids != previous_drafted_ids:
            board = board_view(vorp_df, picks)
            rendered = render_board(board)
            render(rendered)
            if log_path is not None:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(f"# Draft board — live\n\n{rendered}\n")
            previous_drafted_ids = drafted_ids
        iteration += 1
        if max_iterations is None or iteration < max_iterations:
            sleep(poll_seconds)
