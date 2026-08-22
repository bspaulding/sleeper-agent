"""Domain types for Sleeper API data: frozen dataclasses + raw TypedDicts.

Each `parse_*` function is a hand-written boundary parser from the raw
external JSON shape (`*Raw` TypedDict) to the domain dataclass, per
PROJECT_PLAN.md §10.2 ("validate at the boundary... as ordinary, readable,
testable Python instead of a decorator/metaclass-driven validation
library"). Only fields this codebase actually uses are modeled; unmodeled
raw fields are dropped during parsing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


class LeagueSettingsRaw(TypedDict, total=False):
    waiver_budget: int
    trade_deadline: int
    max_keepers: int
    playoff_week_start: int
    num_teams: int
    waiver_type: int
    best_ball: int


class LeagueRaw(TypedDict, total=False):
    league_id: str
    name: str
    season: str
    status: str
    previous_league_id: str | None
    draft_id: str | None
    scoring_settings: dict[str, float]
    roster_positions: list[str]
    settings: LeagueSettingsRaw


class RosterSettingsRaw(TypedDict, total=False):
    wins: int
    losses: int
    ties: int
    fpts: int
    fpts_decimal: int
    waiver_budget_used: int


class RosterRaw(TypedDict, total=False):
    roster_id: int
    owner_id: str | None
    league_id: str
    players: list[str] | None
    starters: list[str] | None
    settings: RosterSettingsRaw


class UserMetadataRaw(TypedDict, total=False):
    team_name: str


class UserRaw(TypedDict, total=False):
    user_id: str
    display_name: str
    metadata: UserMetadataRaw | None


class DraftSettingsRaw(TypedDict, total=False):
    rounds: int
    teams: int
    slots_qb: int
    slots_rb: int
    slots_wr: int
    slots_te: int
    slots_flex: int
    slots_def: int


class DraftRaw(TypedDict, total=False):
    draft_id: str
    league_id: str
    season: str
    status: str
    type: str
    start_time: int | None
    settings: DraftSettingsRaw
    slot_to_roster_id: dict[str, int]


class DraftPickMetadataRaw(TypedDict, total=False):
    first_name: str
    last_name: str
    position: str
    team: str


class DraftPickRaw(TypedDict, total=False):
    draft_id: str
    round: int
    pick_no: int
    draft_slot: int
    roster_id: int
    player_id: str
    is_keeper: bool | None
    picked_by: str | None
    metadata: DraftPickMetadataRaw | None


class TransactionRaw(TypedDict, total=False):
    transaction_id: str
    type: str
    status: str
    leg: int
    roster_ids: list[int]
    adds: dict[str, int] | None
    drops: dict[str, int] | None
    settings: dict[str, int] | None
    creator: str | None


class PlayerRaw(TypedDict, total=False):
    player_id: str
    first_name: str
    last_name: str
    full_name: str | None
    position: str | None
    team: str | None
    status: str | None
    injury_status: str | None
    fantasy_positions: list[str] | None
    years_exp: int | None


@dataclass(frozen=True)
class LeagueSettings:
    waiver_budget: int
    trade_deadline: int
    max_keepers: int
    playoff_week_start: int
    num_teams: int
    waiver_type: int
    best_ball: bool


@dataclass(frozen=True)
class League:
    league_id: str
    name: str
    season: str
    status: str
    previous_league_id: str | None
    draft_id: str | None
    scoring_settings: dict[str, float]
    roster_positions: tuple[str, ...]
    settings: LeagueSettings


@dataclass(frozen=True)
class Roster:
    roster_id: int
    owner_id: str | None
    league_id: str
    player_ids: tuple[str, ...]
    starter_ids: tuple[str, ...]
    wins: int
    losses: int
    ties: int
    points_for: float
    waiver_budget_used: int


@dataclass(frozen=True)
class User:
    user_id: str
    display_name: str
    team_name: str | None


@dataclass(frozen=True)
class Draft:
    draft_id: str
    league_id: str
    season: str
    status: str
    draft_type: str
    rounds: int
    num_teams: int
    start_time_ms: int | None
    slots_qb: int
    slots_rb: int
    slots_wr: int
    slots_te: int
    slots_flex: int
    slots_def: int
    slot_to_roster_id: dict[int, int]


@dataclass(frozen=True)
class DraftPick:
    draft_id: str
    round: int
    pick_no: int
    draft_slot: int
    # Sleeper returns `roster_id: null` for every pick in a mock draft (no real
    # league roster backs it) — always populated in league drafts, always null
    # in mock ones. `draft_slot` is populated in both, so ownership matching
    # (`board.my_roster_positions`) prefers it whenever available.
    roster_id: int | None
    player_id: str
    is_keeper: bool
    picked_by: str | None
    player_name: str | None
    player_position: str | None


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    transaction_type: str
    status: str
    week: int
    roster_ids: tuple[int, ...]
    adds: dict[str, int]
    drops: dict[str, int]
    waiver_bid: int | None


@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    position: str | None
    team: str | None
    status: str | None
    injury_status: str | None
    fantasy_positions: tuple[str, ...]
    years_exp: int | None


def parse_league(raw: LeagueRaw) -> League:
    settings_raw = raw.get("settings") or {}
    settings = LeagueSettings(
        waiver_budget=settings_raw.get("waiver_budget", 0),
        trade_deadline=settings_raw.get("trade_deadline", 0),
        max_keepers=settings_raw.get("max_keepers", 0),
        playoff_week_start=settings_raw.get("playoff_week_start", 0),
        num_teams=settings_raw.get("num_teams", 0),
        waiver_type=settings_raw.get("waiver_type", 0),
        best_ball=bool(settings_raw.get("best_ball", 0)),
    )
    return League(
        league_id=raw["league_id"],
        name=raw.get("name", ""),
        season=raw["season"],
        status=raw.get("status", ""),
        previous_league_id=raw.get("previous_league_id"),
        draft_id=raw.get("draft_id"),
        scoring_settings=dict(raw.get("scoring_settings") or {}),
        roster_positions=tuple(raw.get("roster_positions") or ()),
        settings=settings,
    )


def parse_roster(raw: RosterRaw) -> Roster:
    settings_raw = raw.get("settings") or {}
    fpts = settings_raw.get("fpts", 0) + settings_raw.get("fpts_decimal", 0) / 100
    return Roster(
        roster_id=raw["roster_id"],
        owner_id=raw.get("owner_id"),
        league_id=raw.get("league_id", ""),
        player_ids=tuple(raw.get("players") or ()),
        starter_ids=tuple(raw.get("starters") or ()),
        wins=settings_raw.get("wins", 0),
        losses=settings_raw.get("losses", 0),
        ties=settings_raw.get("ties", 0),
        points_for=fpts,
        waiver_budget_used=settings_raw.get("waiver_budget_used", 0),
    )


def parse_user(raw: UserRaw) -> User:
    metadata = raw.get("metadata") or {}
    return User(
        user_id=raw["user_id"],
        display_name=raw.get("display_name", ""),
        team_name=metadata.get("team_name"),
    )


def parse_draft(raw: DraftRaw) -> Draft:
    settings_raw = raw.get("settings") or {}
    return Draft(
        draft_id=raw["draft_id"],
        league_id=raw.get("league_id", ""),
        season=raw.get("season", ""),
        status=raw.get("status", ""),
        draft_type=raw.get("type", ""),
        rounds=settings_raw.get("rounds", 0),
        num_teams=settings_raw.get("teams", 0),
        start_time_ms=raw.get("start_time"),
        slots_qb=settings_raw.get("slots_qb", 0),
        slots_rb=settings_raw.get("slots_rb", 0),
        slots_wr=settings_raw.get("slots_wr", 0),
        slots_te=settings_raw.get("slots_te", 0),
        slots_flex=settings_raw.get("slots_flex", 0),
        slots_def=settings_raw.get("slots_def", 0),
        slot_to_roster_id={
            int(slot): roster_id
            for slot, roster_id in (raw.get("slot_to_roster_id") or {}).items()
        },
    )


def parse_draft_pick(raw: DraftPickRaw) -> DraftPick:
    metadata = raw.get("metadata") or {}
    first_name = metadata.get("first_name")
    last_name = metadata.get("last_name")
    player_name = f"{first_name} {last_name}" if first_name or last_name else None
    return DraftPick(
        draft_id=raw.get("draft_id", ""),
        round=raw["round"],
        pick_no=raw["pick_no"],
        draft_slot=raw.get("draft_slot", 0),
        roster_id=raw["roster_id"],
        player_id=raw["player_id"],
        is_keeper=bool(raw.get("is_keeper")),
        picked_by=raw.get("picked_by"),
        player_name=player_name,
        player_position=metadata.get("position"),
    )


def parse_transaction(raw: TransactionRaw) -> Transaction:
    settings_raw = raw.get("settings") or {}
    waiver_bid = settings_raw.get("waiver_bid")
    return Transaction(
        transaction_id=raw["transaction_id"],
        transaction_type=raw.get("type", ""),
        status=raw.get("status", ""),
        week=raw.get("leg", 0),
        roster_ids=tuple(raw.get("roster_ids") or ()),
        adds=dict(raw.get("adds") or {}),
        drops=dict(raw.get("drops") or {}),
        waiver_bid=waiver_bid,
    )


def parse_player(player_id: str, raw: PlayerRaw) -> Player:
    name = raw.get("full_name")
    if not name:
        first = raw.get("first_name", "")
        last = raw.get("last_name", "")
        name = f"{first} {last}".strip()
    return Player(
        player_id=player_id,
        name=name,
        position=raw.get("position"),
        team=raw.get("team"),
        status=raw.get("status"),
        injury_status=raw.get("injury_status"),
        fantasy_positions=tuple(raw.get("fantasy_positions") or ()),
        years_exp=raw.get("years_exp"),
    )


def raw_json_dict(value: Any) -> dict[str, Any]:
    """Narrow an untyped JSON value known to be a dict at a boundary call site."""
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object, got {type(value).__name__}")
    return value
