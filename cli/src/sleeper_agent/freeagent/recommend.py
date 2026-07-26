"""`freeagent recommend` — non-FAAB add/drop suggestions.

Ranks available (unrostered league-wide) upgrades over the roster's weakest
rostered player per position — no bid math, this is for the gap between
waiver periods (`PROJECT_PLAN.md` §6.6).
"""

from __future__ import annotations

from dataclasses import dataclass

from sleeper_agent.models.sleeper import Roster
from sleeper_agent.waiver.recommend import PlayerValueRow


@dataclass(frozen=True)
class FreeAgentRecommendation:
    player_id: str
    name: str
    position: str
    vorp_season: float
    upgrade_over_player_id: str
    upgrade_over_name: str
    vorp_delta: float


def _weakest_rostered_by_position(
    roster: Roster, value_by_id: dict[str, PlayerValueRow]
) -> dict[str, tuple[str, str, float]]:
    weakest: dict[str, tuple[str, str, float]] = {}
    for player_id in roster.player_ids:
        row = value_by_id.get(player_id)
        if row is None:
            continue
        current = weakest.get(row.position)
        if current is None or row.vorp_season < current[2]:
            weakest[row.position] = (player_id, row.name, row.vorp_season)
    return weakest


def recommend_free_agents(
    roster: Roster,
    value_by_id: dict[str, PlayerValueRow],
    available_player_ids: set[str],
    *,
    top_n: int = 10,
) -> list[FreeAgentRecommendation]:
    weakest_by_position = _weakest_rostered_by_position(roster, value_by_id)

    recommendations: list[FreeAgentRecommendation] = []
    for player_id in available_player_ids:
        row = value_by_id.get(player_id)
        if row is None:
            continue
        weakest = weakest_by_position.get(row.position)
        if weakest is None:
            continue
        weak_id, weak_name, weak_vorp = weakest
        if row.vorp_season > weak_vorp:
            recommendations.append(
                FreeAgentRecommendation(
                    player_id=player_id,
                    name=row.name,
                    position=row.position,
                    vorp_season=row.vorp_season,
                    upgrade_over_player_id=weak_id,
                    upgrade_over_name=weak_name,
                    vorp_delta=row.vorp_season - weak_vorp,
                )
            )

    recommendations.sort(key=lambda r: r.vorp_delta, reverse=True)
    return recommendations[:top_n]
