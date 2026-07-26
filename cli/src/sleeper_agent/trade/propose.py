"""`trade propose` — scan for value-balanced 1-for-1 candidate packages.

Matches our roster's surplus positions against a target roster's needs (and
vice versa), generates candidate 1-for-1 packages within a value-delta
tolerance, and ranks by a plausibility heuristic — an extremely
lopsided-but-technically-fair offer is unlikely to be accepted even if the
math works, so raw value-delta alone isn't the ranking key.
"""

from __future__ import annotations

from dataclasses import dataclass

from sleeper_agent.models.sleeper import Roster
from sleeper_agent.waiver.recommend import PlayerValueRow

DEFAULT_TOLERANCE = 0.10


@dataclass(frozen=True)
class TradeProposal:
    give_player_id: str
    give_name: str
    give_position: str
    get_player_id: str
    get_name: str
    get_position: str
    value_delta: float  # get value - give value, from our roster's perspective
    plausibility_score: float


def position_average_vorp(
    roster: Roster, value_by_id: dict[str, PlayerValueRow]
) -> dict[str, float]:
    totals: dict[str, list[float]] = {}
    for player_id in roster.player_ids:
        row = value_by_id.get(player_id)
        if row is None:
            continue
        totals.setdefault(row.position, []).append(row.vorp_season)
    return {position: sum(values) / len(values) for position, values in totals.items()}


def propose_trades(
    our_roster: Roster,
    target_roster: Roster,
    value_by_id: dict[str, PlayerValueRow],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    top_n: int = 5,
) -> list[TradeProposal]:
    our_players = [
        (pid, value_by_id[pid]) for pid in our_roster.player_ids if pid in value_by_id
    ]
    their_players = [
        (pid, value_by_id[pid])
        for pid in target_roster.player_ids
        if pid in value_by_id
    ]

    our_position_avg = position_average_vorp(our_roster, value_by_id)
    their_position_avg = position_average_vorp(target_roster, value_by_id)

    candidates: list[TradeProposal] = []
    for give_id, give_row in our_players:
        for get_id, get_row in their_players:
            base = max(abs(give_row.vorp_season), abs(get_row.vorp_season), 1.0)
            delta = get_row.vorp_season - give_row.vorp_season
            if abs(delta) / base > tolerance:
                continue

            # Plausibility: reward filling an actual need on both sides (the
            # position we're getting is one we're weak at; the position
            # we're giving is one the other team is weak at, so they're
            # more likely to value it) and penalize larger absolute deltas
            # even within tolerance, since a bigger swing is a harder sell.
            our_need = -our_position_avg.get(get_row.position, 0.0)
            their_need = -their_position_avg.get(give_row.position, 0.0)
            plausibility = our_need + their_need - abs(delta)

            candidates.append(
                TradeProposal(
                    give_player_id=give_id,
                    give_name=give_row.name,
                    give_position=give_row.position,
                    get_player_id=get_id,
                    get_name=get_row.name,
                    get_position=get_row.position,
                    value_delta=delta,
                    plausibility_score=plausibility,
                )
            )

    candidates.sort(key=lambda c: c.plausibility_score, reverse=True)
    return candidates[:top_n]
