"""Orchestrates `sleeper league sync`: fetch + persist league/roster/user/
transaction/draft-pick tables to `data/sleeper/*/<season>.parquet`.

Table <-> dataclass conversion lives here rather than in `models/sleeper.py`
since it's specifically about the parquet persistence boundary, not the
Sleeper API boundary those dataclasses/parsers already cover.

`scoring_settings` is stored as a JSON string column rather than a nested
Struct column: Sleeper's scoring_settings dict has ~90 keys that have grown
over time, and a JSON string sidesteps parquet struct-schema fragility if
that key set ever changes between seasons — a deliberate simplicity
tradeoff over a fully-typed nested column.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sleeper_agent.models.sleeper import (
    DraftPick,
    League,
    LeagueSettings,
    Roster,
    Transaction,
    User,
)
from sleeper_agent.sleeper_client import draft as draft_client
from sleeper_agent.sleeper_client import league as league_client
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL
from sleeper_agent.storage.parquet_store import write_table

LEAGUE_SCHEMA_VERSION = 1
ROSTERS_SCHEMA_VERSION = 1
USERS_SCHEMA_VERSION = 1
TRANSACTIONS_SCHEMA_VERSION = 1
DRAFTS_SCHEMA_VERSION = 1


def league_to_dataframe(league: League) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "league_id": [league.league_id],
            "name": [league.name],
            "season": [league.season],
            "status": [league.status],
            "previous_league_id": [league.previous_league_id],
            "draft_id": [league.draft_id],
            "roster_positions": [list(league.roster_positions)],
            "scoring_settings_json": [json.dumps(league.scoring_settings)],
            "waiver_budget": [league.settings.waiver_budget],
            "trade_deadline": [league.settings.trade_deadline],
            "max_keepers": [league.settings.max_keepers],
            "playoff_week_start": [league.settings.playoff_week_start],
            "num_teams": [league.settings.num_teams],
            "waiver_type": [league.settings.waiver_type],
            "best_ball": [league.settings.best_ball],
        }
    )


def dataframe_to_league(df: pl.DataFrame) -> League:
    row = df.to_dicts()[0]
    settings = LeagueSettings(
        waiver_budget=row["waiver_budget"],
        trade_deadline=row["trade_deadline"],
        max_keepers=row["max_keepers"],
        playoff_week_start=row["playoff_week_start"],
        num_teams=row["num_teams"],
        waiver_type=row["waiver_type"],
        best_ball=row["best_ball"],
    )
    return League(
        league_id=row["league_id"],
        name=row["name"],
        season=row["season"],
        status=row["status"],
        previous_league_id=row["previous_league_id"],
        draft_id=row["draft_id"],
        scoring_settings=json.loads(row["scoring_settings_json"]),
        roster_positions=tuple(row["roster_positions"]),
        settings=settings,
    )


def rosters_to_dataframe(rosters: list[Roster]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "roster_id": [r.roster_id for r in rosters],
            "owner_id": [r.owner_id for r in rosters],
            "league_id": [r.league_id for r in rosters],
            "player_ids": [list(r.player_ids) for r in rosters],
            "starter_ids": [list(r.starter_ids) for r in rosters],
            "wins": [r.wins for r in rosters],
            "losses": [r.losses for r in rosters],
            "ties": [r.ties for r in rosters],
            "points_for": [r.points_for for r in rosters],
            "waiver_budget_used": [r.waiver_budget_used for r in rosters],
        }
    )


def dataframe_to_rosters(df: pl.DataFrame) -> list[Roster]:
    return [
        Roster(
            roster_id=row["roster_id"],
            owner_id=row["owner_id"],
            league_id=row["league_id"],
            player_ids=tuple(row["player_ids"]),
            starter_ids=tuple(row["starter_ids"]),
            wins=row["wins"],
            losses=row["losses"],
            ties=row["ties"],
            points_for=row["points_for"],
            waiver_budget_used=row["waiver_budget_used"],
        )
        for row in df.to_dicts()
    ]


def users_to_dataframe(users: list[User]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "user_id": [u.user_id for u in users],
            "display_name": [u.display_name for u in users],
            "team_name": [u.team_name for u in users],
        }
    )


def dataframe_to_users(df: pl.DataFrame) -> list[User]:
    return [
        User(
            user_id=row["user_id"],
            display_name=row["display_name"],
            team_name=row["team_name"],
        )
        for row in df.to_dicts()
    ]


def transactions_to_dataframe(transactions: list[Transaction]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "transaction_id": [t.transaction_id for t in transactions],
            "transaction_type": [t.transaction_type for t in transactions],
            "status": [t.status for t in transactions],
            "week": [t.week for t in transactions],
            "roster_ids": [list(t.roster_ids) for t in transactions],
            "adds_json": [json.dumps(t.adds) for t in transactions],
            "drops_json": [json.dumps(t.drops) for t in transactions],
            "waiver_bid": [t.waiver_bid for t in transactions],
        }
    )


def draft_picks_to_dataframe(picks: list[DraftPick]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "draft_id": [p.draft_id for p in picks],
            "round": [p.round for p in picks],
            "pick_no": [p.pick_no for p in picks],
            "draft_slot": [p.draft_slot for p in picks],
            "roster_id": [p.roster_id for p in picks],
            "player_id": [p.player_id for p in picks],
            "is_keeper": [p.is_keeper for p in picks],
            "picked_by": [p.picked_by for p in picks],
            "player_name": [p.player_name for p in picks],
            "player_position": [p.player_position for p in picks],
        }
    )


def dataframe_to_draft_picks(df: pl.DataFrame) -> list[DraftPick]:
    return [
        DraftPick(
            draft_id=row["draft_id"],
            round=row["round"],
            pick_no=row["pick_no"],
            draft_slot=row["draft_slot"],
            roster_id=row["roster_id"],
            player_id=row["player_id"],
            is_keeper=row["is_keeper"],
            picked_by=row["picked_by"],
            player_name=row["player_name"],
            player_position=row["player_position"],
        )
        for row in df.to_dicts()
    ]


@dataclass(frozen=True)
class LeagueSyncResult:
    league_id: str
    season: str
    roster_count: int
    user_count: int
    transaction_count: int
    draft_pick_count: int


def sync_league(
    league_id: str,
    season: str,
    sleeper_dir: Path,
    *,
    base_url: str = SLEEPER_BASE_URL,
) -> LeagueSyncResult:
    league = league_client.fetch_league(league_id, base_url=base_url)
    rosters = league_client.fetch_rosters(league_id, base_url=base_url)
    users = league_client.fetch_users(league_id, base_url=base_url)
    transactions = league_client.fetch_all_transactions(league_id, base_url=base_url)
    draft_picks = (
        draft_client.fetch_draft_picks(league.draft_id, base_url=base_url)
        if league.draft_id
        else []
    )

    write_table(
        league_to_dataframe(league),
        sleeper_dir / "league" / f"{season}.parquet",
        schema_version=LEAGUE_SCHEMA_VERSION,
    )
    write_table(
        rosters_to_dataframe(rosters),
        sleeper_dir / "rosters" / f"{season}.parquet",
        schema_version=ROSTERS_SCHEMA_VERSION,
    )
    write_table(
        users_to_dataframe(users),
        sleeper_dir / "users" / f"{season}.parquet",
        schema_version=USERS_SCHEMA_VERSION,
    )
    write_table(
        transactions_to_dataframe(transactions),
        sleeper_dir / "transactions" / f"{season}.parquet",
        schema_version=TRANSACTIONS_SCHEMA_VERSION,
    )
    write_table(
        draft_picks_to_dataframe(draft_picks),
        sleeper_dir / "drafts" / f"{season}.parquet",
        schema_version=DRAFTS_SCHEMA_VERSION,
    )

    return LeagueSyncResult(
        league_id=league_id,
        season=season,
        roster_count=len(rosters),
        user_count=len(users),
        transaction_count=len(transactions),
        draft_pick_count=len(draft_picks),
    )
