from __future__ import annotations

import json
from pathlib import Path

import pytest

from sleeper_agent.models.sleeper import raw_json_dict
from sleeper_agent.sleeper_client import draft as draft_client
from sleeper_agent.sleeper_client import league as league_client
from sleeper_agent.sleeper_client import trending as trending_client
from sleeper_agent.sleeper_client.http import SleeperHTTPError, get_json
from sleeper_agent.sleeper_client.trending import TrendingType
from tests.support.mock_http import Request, Response, mock_http_server

FIXTURES = Path(__file__).parent / "fixtures" / "sleeper"


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def json_response(payload: object) -> Response:
    return Response(
        status=200,
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload).encode(),
    )


# --- raw_json_dict -----------------------------------------------------


def test_raw_json_dict_accepts_a_dict() -> None:
    assert raw_json_dict({"a": 1}) == {"a": 1}


def test_raw_json_dict_rejects_non_dict_json() -> None:
    with pytest.raises(TypeError):
        raw_json_dict([1, 2, 3])


# --- http.get_json -----------------------------------------------------


def test_get_json_returns_parsed_body_on_success() -> None:
    def handler(request: Request) -> Response:
        return json_response({"ok": True})

    with mock_http_server(handler) as base_url:
        result = get_json(f"{base_url}/thing")

    assert result == {"ok": True}


def test_get_json_raises_immediately_on_non_retryable_status() -> None:
    def handler(request: Request) -> Response:
        return Response(status=404, body=b"not found")

    with (
        mock_http_server(handler) as base_url,
        pytest.raises(SleeperHTTPError) as excinfo,
    ):
        get_json(f"{base_url}/missing")

    assert excinfo.value.status_code == 404


def test_get_json_retries_retryable_status_then_succeeds() -> None:
    attempts: list[int] = []
    sleeps: list[float] = []

    def handler(request: Request) -> Response:
        attempts.append(1)
        if len(attempts) < 3:
            return Response(status=503, body=b"unavailable")
        return json_response({"ok": True})

    with mock_http_server(handler) as base_url:
        result = get_json(f"{base_url}/flaky", sleep=sleeps.append)

    assert result == {"ok": True}
    assert len(attempts) == 3
    assert sleeps == [1.0, 2.0]


def test_get_json_raises_after_exhausting_retries() -> None:
    sleeps: list[float] = []

    def handler(request: Request) -> Response:
        return Response(status=500, body=b"boom")

    with (
        mock_http_server(handler) as base_url,
        pytest.raises(SleeperHTTPError) as excinfo,
    ):
        get_json(f"{base_url}/always-down", sleep=sleeps.append, max_attempts=2)

    assert excinfo.value.status_code == 500
    assert sleeps == [1.0]


# --- league --------------------------------------------------------------


def test_fetch_user_id_reads_user_id_from_response() -> None:
    def handler(request: Request) -> Response:
        assert request.path == "/user/yellldarb"
        return json_response({"user_id": "469022928223072256"})

    with mock_http_server(handler) as base_url:
        user_id = league_client.fetch_user_id("yellldarb", base_url=base_url)

    assert user_id == "469022928223072256"


def test_resolve_league_id_finds_league_for_requested_season() -> None:
    def handler(request: Request) -> Response:
        assert request.path == "/user/u1/leagues/nfl/2026"
        return json_response([{"league_id": "abc"}])

    with mock_http_server(handler) as base_url:
        result = league_client.resolve_league_id("u1", "2026", base_url=base_url)

    assert result == league_client.LeagueResolved(league_id="abc", season="2026")


def test_resolve_league_id_falls_back_to_prior_season_when_current_is_empty() -> None:
    def handler(request: Request) -> Response:
        if request.path == "/user/u1/leagues/nfl/2026":
            return json_response([])
        if request.path == "/user/u1/leagues/nfl/2025":
            return json_response([{"league_id": "prior"}])
        raise AssertionError(f"unexpected path {request.path}")

    with mock_http_server(handler) as base_url:
        result = league_client.resolve_league_id("u1", "2026", base_url=base_url)

    assert result == league_client.LeagueResolvedViaFallback(
        league_id="prior", requested_season="2026", resolved_season="2025"
    )


def test_resolve_league_id_raises_when_no_season_has_a_league() -> None:
    def handler(request: Request) -> Response:
        return json_response([])

    with (
        mock_http_server(handler) as base_url,
        pytest.raises(league_client.NoLeagueFoundError),
    ):
        league_client.resolve_league_id(
            "u1", "2026", base_url=base_url, max_seasons_back=2
        )


def test_fetch_league_parses_real_fixture() -> None:
    payload = json.loads(load_fixture("league.json"))

    def handler(request: Request) -> Response:
        assert request.path == "/league/1180391690551980032"
        return json_response(payload)

    with mock_http_server(handler) as base_url:
        league = league_client.fetch_league("1180391690551980032", base_url=base_url)

    assert league.name == "Only Gold"
    assert league.season == "2025"
    assert league.settings.max_keepers == 2
    assert league.settings.waiver_budget == 100
    assert "RB" in league.roster_positions
    assert league.scoring_settings["rec"] == 1.0


def test_fetch_rosters_parses_real_fixture() -> None:
    payload = json.loads(load_fixture("rosters.json"))

    def handler(request: Request) -> Response:
        return json_response(payload)

    with mock_http_server(handler) as base_url:
        rosters = league_client.fetch_rosters("lid", base_url=base_url)

    assert len(rosters) == len(payload)
    assert rosters[0].roster_id == payload[0]["roster_id"]


def test_fetch_users_parses_real_fixture() -> None:
    payload = json.loads(load_fixture("users.json"))

    def handler(request: Request) -> Response:
        return json_response(payload)

    with mock_http_server(handler) as base_url:
        users = league_client.fetch_users("lid", base_url=base_url)

    assert len(users) == len(payload)
    assert users[0].user_id == payload[0]["user_id"]


def test_fetch_transactions_for_week_parses_real_fixture() -> None:
    payload = json.loads(load_fixture("transactions_week1.json"))

    def handler(request: Request) -> Response:
        assert request.path == "/league/lid/transactions/1"
        return json_response(payload)

    with mock_http_server(handler) as base_url:
        transactions = league_client.fetch_transactions_for_week(
            "lid", 1, base_url=base_url
        )

    assert len(transactions) == len(payload)


def test_fetch_all_transactions_concatenates_every_week() -> None:
    def handler(request: Request) -> Response:
        week = request.path.rsplit("/", 1)[-1]
        if week == "1":
            return json_response(
                [{"transaction_id": "t1", "type": "waiver", "status": "complete"}]
            )
        return json_response([])

    with mock_http_server(handler) as base_url:
        transactions = league_client.fetch_all_transactions(
            "lid", base_url=base_url, max_week=3
        )

    assert [t.transaction_id for t in transactions] == ["t1"]


def test_fetch_traded_picks_parses_response() -> None:
    def handler(request: Request) -> Response:
        return json_response(
            [
                {
                    "season": "2026",
                    "round": 2,
                    "roster_id": 1,
                    "previous_owner_id": 1,
                    "owner_id": 5,
                }
            ]
        )

    with mock_http_server(handler) as base_url:
        picks = league_client.fetch_traded_picks("lid", base_url=base_url)

    assert picks == [
        league_client.TradedPick(
            season="2026", round=2, roster_id=1, previous_owner_id=1, owner_id=5
        )
    ]


def test_fetch_traded_picks_handles_empty_response() -> None:
    def handler(request: Request) -> Response:
        return Response(
            status=200, headers={"Content-Type": "application/json"}, body=b"null"
        )

    with mock_http_server(handler) as base_url:
        picks = league_client.fetch_traded_picks("lid", base_url=base_url)

    assert picks == []


# --- draft -----------------------------------------------------------------


def test_fetch_draft_parses_real_fixture() -> None:
    payload = json.loads(load_fixture("draft.json"))

    def handler(request: Request) -> Response:
        return json_response(payload)

    with mock_http_server(handler) as base_url:
        draft = draft_client.fetch_draft("did", base_url=base_url)

    assert draft.draft_type == "snake"
    assert draft.rounds == 15
    assert draft.num_teams == 12
    assert draft.slots_qb == 1
    assert draft.slots_rb == 2
    assert draft.slots_wr == 2
    assert draft.slots_te == 1
    assert draft.slots_flex == 2
    assert draft.slots_def == 1
    assert draft.slot_to_roster_id == {
        1: 3,
        2: 8,
        3: 1,
        4: 4,
        5: 12,
        6: 6,
        7: 10,
        8: 7,
        9: 2,
        10: 9,
        11: 5,
        12: 11,
    }


def test_fetch_draft_picks_parses_real_fixture_including_keepers() -> None:
    payload = json.loads(load_fixture("draft_picks.json"))

    def handler(request: Request) -> Response:
        return json_response(payload)

    with mock_http_server(handler) as base_url:
        picks = draft_client.fetch_draft_picks("did", base_url=base_url)

    assert len(picks) == len(payload)
    keeper_picks = [p for p in picks if p.is_keeper]
    non_keeper_picks = [p for p in picks if not p.is_keeper]
    assert keeper_picks
    assert non_keeper_picks


# --- trending ----------------------------------------------------------


def test_fetch_trending_parses_response() -> None:
    def handler(request: Request) -> Response:
        assert request.path == "/players/nfl/trending/add?lookback_hours=48"
        return json_response([{"player_id": "123", "count": 42}])

    with mock_http_server(handler) as base_url:
        trending = trending_client.fetch_trending(
            TrendingType.ADD, hours=48, base_url=base_url
        )

    assert trending == [trending_client.TrendingPlayer(player_id="123", count=42)]
