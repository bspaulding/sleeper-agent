"""Trending adds/drops — not persisted to parquet, cheap enough to fetch live."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL, get_json


class TrendingType(Enum):
    ADD = "add"
    DROP = "drop"


@dataclass(frozen=True)
class TrendingPlayer:
    player_id: str
    count: int


def fetch_trending(
    trending_type: TrendingType,
    *,
    hours: int = 24,
    base_url: str = SLEEPER_BASE_URL,
) -> list[TrendingPlayer]:
    url = (
        f"{base_url}/players/nfl/trending/{trending_type.value}?lookback_hours={hours}"
    )
    raw = get_json(url)
    return [
        TrendingPlayer(player_id=str(item["player_id"]), count=int(item["count"]))
        for item in raw or []
    ]
