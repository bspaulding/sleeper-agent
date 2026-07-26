"""`waiver recommend` — ranked FAAB waiver targets with a suggested bid range.

Combines trending adds (actually being picked up right now) with VORP
(quality) to rank targets, and computes a suggested bid **range** rather
than a single number — final bid sizing (budget pacing across the season,
how much to protect against a bigger need later) is the judgment call
`.claude/skills/waivers.md` covers, not something to hardcode here.
"""

from __future__ import annotations

from dataclasses import dataclass

from sleeper_agent.sleeper_client.trending import TrendingPlayer


@dataclass(frozen=True)
class PlayerValueRow:
    name: str
    position: str
    vorp_season: float


@dataclass(frozen=True)
class WaiverTarget:
    player_id: str
    name: str
    position: str
    trending_count: int
    vorp_season: float | None
    bid_low: int
    bid_high: int


def suggested_bid_range(
    budget_remaining: int,
    weeks_remaining: int,
    value_fraction: float,
) -> tuple[int, int]:
    """A bid range scaled by budget pacing and relative value.

    `value_fraction` is 0..1 (1.0 = the best available target this run).
    Naive weekly pacing budget = budget_remaining / weeks_remaining; the
    range is a fraction of that, scaled by value, clamped to
    [0, budget_remaining].
    """
    weeks = max(weeks_remaining, 1)
    weekly_budget = budget_remaining / weeks
    fraction = max(0.0, min(1.0, value_fraction))
    low = round(weekly_budget * fraction * 0.6)
    high = round(weekly_budget * fraction * 1.8) + (1 if fraction > 0 else 0)
    low = max(0, min(low, budget_remaining))
    high = max(low, min(high, budget_remaining))
    return (low, high)


def recommend_waivers(
    trending: list[TrendingPlayer],
    rostered_player_ids: set[str],
    value_by_id: dict[str, PlayerValueRow],
    budget_remaining: int,
    weeks_remaining: int,
    *,
    top_n: int = 10,
) -> list[WaiverTarget]:
    available = [t for t in trending if t.player_id not in rostered_player_ids]
    ranked = sorted(
        available,
        key=lambda t: (
            value_by_id[t.player_id].vorp_season
            if t.player_id in value_by_id
            else float("-inf"),
            t.count,
        ),
        reverse=True,
    )[:top_n]

    max_vorp = max(
        (
            value_by_id[t.player_id].vorp_season
            for t in ranked
            if t.player_id in value_by_id
        ),
        default=0.0,
    )

    targets: list[WaiverTarget] = []
    for trending_player in ranked:
        row = value_by_id.get(trending_player.player_id)
        if row is not None and max_vorp > 0:
            fraction = max(0.05, min(1.0, row.vorp_season / max_vorp))
        else:
            fraction = 0.15  # unranked/low-signal player: small baseline bid range
        bid_low, bid_high = suggested_bid_range(
            budget_remaining, weeks_remaining, fraction
        )
        targets.append(
            WaiverTarget(
                player_id=trending_player.player_id,
                name=row.name if row else trending_player.player_id,
                position=row.position if row else "?",
                trending_count=trending_player.count,
                vorp_season=row.vorp_season if row else None,
                bid_low=bid_low,
                bid_high=bid_high,
            )
        )
    return targets
