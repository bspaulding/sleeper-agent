"""League resolution + sync: league/roster/user/transaction/traded-pick reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from sleeper_agent.models.sleeper import (
    League,
    LeagueRaw,
    Roster,
    Transaction,
    User,
    parse_league,
    parse_roster,
    parse_transaction,
    parse_user,
    raw_json_dict,
)
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL, get_json


@dataclass(frozen=True)
class LeagueResolved:
    league_id: str
    season: str


@dataclass(frozen=True)
class LeagueResolvedViaFallback:
    league_id: str
    requested_season: str
    resolved_season: str


ResolveResult = LeagueResolved | LeagueResolvedViaFallback


class NoLeagueFoundError(Exception):
    def __init__(
        self, user_id: str, requested_season: str, seasons_checked: int
    ) -> None:
        self.user_id = user_id
        self.requested_season = requested_season
        super().__init__(
            f"no league found for user {user_id} within {seasons_checked} season(s) "
            f"back from {requested_season}"
        )


def fetch_user_id(username: str, *, base_url: str = SLEEPER_BASE_URL) -> str:
    raw = raw_json_dict(get_json(f"{base_url}/user/{username}"))
    return str(raw["user_id"])


def _leagues_for_season(
    user_id: str, season: str, *, base_url: str
) -> list[dict[str, object]]:
    raw = get_json(f"{base_url}/user/{user_id}/leagues/nfl/{season}")
    return list(raw or [])


def resolve_league_id(
    user_id: str,
    requested_season: str,
    *,
    base_url: str = SLEEPER_BASE_URL,
    max_seasons_back: int = 5,
) -> ResolveResult:
    leagues = _leagues_for_season(user_id, requested_season, base_url=base_url)
    if leagues:
        league_id = str(leagues[0]["league_id"])
        return LeagueResolved(league_id=league_id, season=requested_season)

    season_int = int(requested_season)
    for offset in range(1, max_seasons_back + 1):
        candidate_season = str(season_int - offset)
        leagues = _leagues_for_season(user_id, candidate_season, base_url=base_url)
        if leagues:
            league_id = str(leagues[0]["league_id"])
            return LeagueResolvedViaFallback(
                league_id=league_id,
                requested_season=requested_season,
                resolved_season=candidate_season,
            )

    raise NoLeagueFoundError(user_id, requested_season, max_seasons_back)


def fetch_league(league_id: str, *, base_url: str = SLEEPER_BASE_URL) -> League:
    raw = raw_json_dict(get_json(f"{base_url}/league/{league_id}"))
    return parse_league(cast(LeagueRaw, raw))


def fetch_rosters(league_id: str, *, base_url: str = SLEEPER_BASE_URL) -> list[Roster]:
    raw = get_json(f"{base_url}/league/{league_id}/rosters")
    return [parse_roster(item) for item in raw or []]


def fetch_users(league_id: str, *, base_url: str = SLEEPER_BASE_URL) -> list[User]:
    raw = get_json(f"{base_url}/league/{league_id}/users")
    return [parse_user(item) for item in raw or []]


def fetch_transactions_for_week(
    league_id: str, week: int, *, base_url: str = SLEEPER_BASE_URL
) -> list[Transaction]:
    raw = get_json(f"{base_url}/league/{league_id}/transactions/{week}")
    return [parse_transaction(item) for item in raw or []]


def fetch_all_transactions(
    league_id: str, *, base_url: str = SLEEPER_BASE_URL, max_week: int = 18
) -> list[Transaction]:
    transactions: list[Transaction] = []
    for week in range(1, max_week + 1):
        transactions.extend(
            fetch_transactions_for_week(league_id, week, base_url=base_url)
        )
    return transactions


@dataclass(frozen=True)
class TradedPick:
    season: str
    round: int
    roster_id: int
    previous_owner_id: int
    owner_id: int


def fetch_traded_picks(
    league_id: str, *, base_url: str = SLEEPER_BASE_URL
) -> list[TradedPick]:
    raw = get_json(f"{base_url}/league/{league_id}/traded_picks")
    return [
        TradedPick(
            season=str(item["season"]),
            round=int(item["round"]),
            roster_id=int(item["roster_id"]),
            previous_owner_id=int(item["previous_owner_id"]),
            owner_id=int(item["owner_id"]),
        )
        for item in raw or []
    ]
