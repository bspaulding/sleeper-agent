"""`trade evaluate` — parse a specific offer and compute a structured value comparison.

Offer parsing (comma-separated Sleeper player IDs and/or pick references like
`2026-R2`) and value/positional-delta computation are pure functions here;
the LLM is expected to quote the result directly into a decision log entry
(`PROJECT_PLAN.md` §6.4) rather than the CLI making the accept/reject call.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from sleeper_agent.waiver.recommend import PlayerValueRow


@dataclass(frozen=True)
class PlayerAsset:
    player_id: str


@dataclass(frozen=True)
class PickAsset:
    season: str
    round: int


TradeAsset = PlayerAsset | PickAsset

_PICK_PATTERN = re.compile(r"^(\d{4})-R(\d+)$")


class MalformedAssetError(Exception):
    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(
            f"can't parse trade asset: {token!r} (expected a player ID or YYYY-R<round>)"
        )


def parse_asset(token: str) -> TradeAsset:
    stripped = token.strip()
    match = _PICK_PATTERN.match(stripped)
    if match:
        return PickAsset(season=match.group(1), round=int(match.group(2)))
    if stripped.isdigit():
        return PlayerAsset(player_id=stripped)
    raise MalformedAssetError(token)


def parse_offer(text: str) -> list[TradeAsset]:
    stripped = text.strip()
    if not stripped:
        return []
    return [parse_asset(token) for token in stripped.split(",")]


def default_pick_value(round_number: int) -> float:
    """Approximate a draft pick's trade value from its round.

    A simple exponential-decay heuristic (round 1 ~= 100, round 8 ~= 20,
    round 15 ~= 4) — not derived from real trade data (this league's
    decision log doesn't have enough pick-involving trades yet to fit one).
    Revisit once there's real trade history to calibrate against, per
    IMPLEMENTATION_PLAN.md's Phase G deviation note.
    """
    return max(0.0, 100.0 * (0.8 ** (round_number - 1)))


@dataclass(frozen=True)
class TradeEvaluation:
    give_value: float
    get_value: float
    value_delta: (
        float  # get_value - give_value; positive favors the "give" side's owner
    )
    give_position_totals: dict[str, float]
    get_position_totals: dict[str, float]


def _asset_value_and_positions(
    assets: list[TradeAsset],
    value_by_id: dict[str, PlayerValueRow],
    pick_value_fn: Callable[[int], float],
) -> tuple[float, dict[str, float]]:
    total = 0.0
    by_position: dict[str, float] = {}
    for asset in assets:
        match asset:
            case PlayerAsset(player_id=player_id):
                row = value_by_id.get(player_id)
                value = row.vorp_season if row else 0.0
                position = row.position if row else "?"
            case PickAsset(round=round_number):
                value = pick_value_fn(round_number)
                position = "PICK"
            case (
                _
            ):  # pragma: no cover - TradeAsset is exhaustive over the two cases above
                raise AssertionError(f"unreachable: {asset!r}")
        total += value
        by_position[position] = by_position.get(position, 0.0) + value
    return total, by_position


def evaluate_trade(
    give: list[TradeAsset],
    get: list[TradeAsset],
    value_by_id: dict[str, PlayerValueRow],
    *,
    pick_value_fn: Callable[[int], float] = default_pick_value,
) -> TradeEvaluation:
    give_value, give_positions = _asset_value_and_positions(
        give, value_by_id, pick_value_fn
    )
    get_value, get_positions = _asset_value_and_positions(
        get, value_by_id, pick_value_fn
    )
    return TradeEvaluation(
        give_value=give_value,
        get_value=get_value,
        value_delta=get_value - give_value,
        give_position_totals=give_positions,
        get_position_totals=get_positions,
    )
