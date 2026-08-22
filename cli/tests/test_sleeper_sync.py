from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sleeper_agent.models.sleeper import (
    DraftPick,
    League,
    LeagueSettings,
    Roster,
    Transaction,
    User,
)
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.storage.parquet_store import read_table
from tests.support.mock_http import Request, Response, mock_http_server

FIXTURES = Path(__file__).parent / "fixtures" / "sleeper"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_bytes())


def make_league(*, season: str = "2025", num_teams: int = 12) -> League:
    return League(
        league_id="lid",
        name="Only Gold",
        season=season,
        status="complete",
        previous_league_id="prev",
        draft_id="did",
        scoring_settings={"rec": 1.0, "pass_yd": 0.04},
        roster_positions=("QB", "RB", "WR", "FLEX", "DEF"),
        settings=LeagueSettings(
            waiver_budget=100,
            trade_deadline=11,
            max_keepers=2,
            playoff_week_start=14,
            num_teams=num_teams,
            waiver_type=2,
            best_ball=True,
        ),
    )


def test_league_dataframe_round_trips() -> None:
    league = make_league()

    df = sleeper_sync.league_to_dataframe(league)
    result = sleeper_sync.dataframe_to_league(df)

    assert result == league


def test_rosters_dataframe_round_trips() -> None:
    rosters = [
        Roster(
            roster_id=1,
            owner_id="u1",
            league_id="lid",
            player_ids=("1", "2"),
            starter_ids=("1",),
            wins=6,
            losses=7,
            ties=0,
            points_for=1701.12,
            waiver_budget_used=37,
        )
    ]

    df = sleeper_sync.rosters_to_dataframe(rosters)
    result = sleeper_sync.dataframe_to_rosters(df)

    assert result == rosters


def test_users_dataframe_round_trips() -> None:
    users = [User(user_id="u1", display_name="yellldarb", team_name="The Juice")]

    df = sleeper_sync.users_to_dataframe(users)
    result = sleeper_sync.dataframe_to_users(df)

    assert result == users


def test_transactions_to_dataframe_serializes_adds_and_drops() -> None:
    transactions = [
        Transaction(
            transaction_id="t1",
            transaction_type="waiver",
            status="complete",
            week=1,
            roster_ids=(2,),
            adds={"12508": 2},
            drops={"7523": 2},
            waiver_bid=6,
        )
    ]

    df = sleeper_sync.transactions_to_dataframe(transactions)

    assert df["transaction_id"].to_list() == ["t1"]
    assert json.loads(df["adds_json"][0]) == {"12508": 2}
    assert json.loads(df["drops_json"][0]) == {"7523": 2}


def test_draft_picks_dataframe_round_trips() -> None:
    picks = [
        DraftPick(
            draft_id="did",
            round=1,
            pick_no=1,
            draft_slot=1,
            roster_id=3,
            player_id="7564",
            is_keeper=False,
            picked_by="u1",
            player_name="Ja'Marr Chase",
            player_position="WR",
            player_team="CIN",
        ),
        DraftPick(
            draft_id="did",
            round=4,
            pick_no=47,
            draft_slot=2,
            roster_id=8,
            player_id="6770",
            is_keeper=True,
            picked_by="u2",
            player_name="Joe Burrow",
            player_position="QB",
            player_team="CIN",
        ),
    ]

    df = sleeper_sync.draft_picks_to_dataframe(picks)
    result = sleeper_sync.dataframe_to_draft_picks(df)

    assert result == picks


def test_sync_league_fetches_and_writes_all_tables(tmp_path: Path) -> None:
    league_payload = load_fixture("league.json")
    rosters_payload = load_fixture("rosters.json")
    users_payload = load_fixture("users.json")
    draft_picks_payload = load_fixture("draft_picks.json")

    def handler(request: Request) -> Response:
        if request.path == "/league/1180391690551980032":
            body = json.dumps(league_payload).encode()
        elif request.path == "/league/1180391690551980032/rosters":
            body = json.dumps(rosters_payload).encode()
        elif request.path == "/league/1180391690551980032/users":
            body = json.dumps(users_payload).encode()
        elif request.path.startswith("/league/1180391690551980032/transactions/"):
            body = b"[]"
        elif request.path == "/draft/1180391690551980033/picks":
            body = json.dumps(draft_picks_payload).encode()
        else:
            raise AssertionError(f"unexpected path {request.path}")
        return Response(
            status=200, headers={"Content-Type": "application/json"}, body=body
        )

    with mock_http_server(handler) as base_url:
        result = sleeper_sync.sync_league(
            "1180391690551980032", "2025", tmp_path, base_url=base_url
        )

    assert result.roster_count == len(rosters_payload)
    assert result.user_count == len(users_payload)
    assert result.draft_pick_count == len(draft_picks_payload)

    league_df = read_table(
        tmp_path / "league" / "2025.parquet", expected_schema_version=1
    )
    assert sleeper_sync.dataframe_to_league(league_df).name == "Only Gold"


def test_sync_league_skips_draft_picks_when_league_has_no_draft_id(
    tmp_path: Path,
) -> None:
    league_payload = dict(load_fixture("league.json"))
    league_payload["draft_id"] = None

    def handler(request: Request) -> Response:
        if request.path == "/league/lid":
            body = json.dumps(league_payload).encode()
        elif request.path in (
            "/league/lid/rosters",
            "/league/lid/users",
        ) or request.path.startswith("/league/lid/transactions/"):
            body = b"[]"
        else:
            raise AssertionError(f"unexpected path {request.path}")
        return Response(
            status=200, headers={"Content-Type": "application/json"}, body=body
        )

    with mock_http_server(handler) as base_url:
        result = sleeper_sync.sync_league("lid", "2025", tmp_path, base_url=base_url)

    assert result.draft_pick_count == 0
