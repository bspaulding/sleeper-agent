"""Draft object + picks (public, no auth) — live board polling and keeper history."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from sleeper_agent.models.sleeper import (
    Draft,
    DraftPick,
    DraftRaw,
    parse_draft,
    parse_draft_pick,
    raw_json_dict,
)
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL, get_json


def fetch_draft(draft_id: str, *, base_url: str = SLEEPER_BASE_URL) -> Draft:
    raw = raw_json_dict(get_json(f"{base_url}/draft/{draft_id}"))
    return parse_draft(cast(DraftRaw, raw))


def fetch_draft_picks(
    draft_id: str, *, base_url: str = SLEEPER_BASE_URL
) -> list[DraftPick]:
    raw = get_json(f"{base_url}/draft/{draft_id}/picks")
    return [parse_draft_pick(item) for item in raw or []]


# --- keeper eligibility & cost (PROJECT_PLAN.md §3, §6.5) ------------------


@dataclass(frozen=True)
class KeeperEligible:
    cost_round: int
    last_round: int


@dataclass(frozen=True)
class KeeperIneligibleMaxYearsReached:
    consecutive_kept_seasons: int


@dataclass(frozen=True)
class KeeperIneligibleCostBelowRoundOne:
    last_round: int


@dataclass(frozen=True)
class KeeperEligibleUndraftedDefault:
    """Eligible to keep, defaulted to the draft's last round.

    No draft-pick record exists for this player+roster anywhere in the
    available season chain (e.g. picked up via waiver/free agency, never
    drafted by this franchise). Confirmed against real 2025 draft data
    (IMPLEMENTATION_PLAN.md's Phase E real-world validation caught this):
    Sleeper assigns an undrafted player kept for the first time to the
    draft's final round rather than marking them ineligible — there's no
    prior round to discount from, so the cheapest keeper slot is used
    instead. Not one of PROJECT_PLAN.md §3's two named-invalid cases —
    both of those assume a prior draft record exists — so this is a
    documented extension of that tagged union for a real case the plan
    didn't originally enumerate.
    """

    cost_round: int


KeeperStatus = (
    KeeperEligible
    | KeeperEligibleUndraftedDefault
    | KeeperIneligibleMaxYearsReached
    | KeeperIneligibleCostBelowRoundOne
)


def _find_pick(
    picks_by_season: Mapping[str, Sequence[DraftPick]],
    season: str,
    player_id: str,
    roster_id: int,
) -> DraftPick | None:
    for pick in picks_by_season.get(season, ()):
        if pick.player_id == player_id and pick.roster_id == roster_id:
            return pick
    return None


def keeper_history(
    player_id: str,
    roster_id: int,
    season_chain: Sequence[str],
    picks_by_season: Mapping[str, Sequence[DraftPick]],
    total_rounds: int,
) -> KeeperStatus:
    """Compute keeper eligibility + cost for a player on a roster.

    `season_chain` is every season with synced draft data *before* the
    season being computed for, ordered most-recent-first (e.g. computing
    for 2026 with history back to 2023: `["2025", "2024", "2023"]`).
    `total_rounds` is the draft's round count (used only for the
    undrafted-player fallback below).

    Rule (PROJECT_PLAN.md §3): find the most recent draft-pick record for
    this player+roster; count how many consecutive seasons immediately
    before and including that record have `is_keeper=True` (walking back
    until a live pick or the chain ends); if that count is already >= 2,
    the player returns to the open pool. Otherwise the keeper cost is
    `last_round - 1`, where `last_round` is that most recent record's
    round — invalid (not eligible at all) only when that computes to 0
    (i.e. `last_round == 1`). Round 1 itself is a valid keeper cost.

    If no draft record exists at all, see `KeeperEligibleUndraftedDefault`.
    """
    most_recent_index: int | None = None
    most_recent_pick: DraftPick | None = None
    for index, season in enumerate(season_chain):
        pick = _find_pick(picks_by_season, season, player_id, roster_id)
        if pick is not None:
            most_recent_index = index
            most_recent_pick = pick
            break

    if most_recent_pick is None or most_recent_index is None:
        return KeeperEligibleUndraftedDefault(cost_round=total_rounds)

    consecutive_kept = 0
    index = most_recent_index
    while index < len(season_chain):
        pick = _find_pick(picks_by_season, season_chain[index], player_id, roster_id)
        if pick is None or not pick.is_keeper:
            break
        consecutive_kept += 1
        if consecutive_kept >= 2:
            break
        index += 1

    if consecutive_kept >= 2:
        return KeeperIneligibleMaxYearsReached(
            consecutive_kept_seasons=consecutive_kept
        )

    cost = most_recent_pick.round - 1
    if cost <= 0:
        return KeeperIneligibleCostBelowRoundOne(last_round=most_recent_pick.round)
    return KeeperEligible(cost_round=cost, last_round=most_recent_pick.round)
