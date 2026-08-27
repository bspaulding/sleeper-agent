"""Headless tests for the `draft board` Textual app.

Drives the real app through `App.run_test` with a fake picks fetch: verifies
poll -> merge -> clear/redraw, the picks stream, the panel toggle, fetch
failure surfacing, and auto-exit on completion. These exist to catch Textual
API drift (this project has already tripped over two breaking changes in
textual 8.x: `@on`-decorated message handlers and the delay-less
`call_later`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import requests
from rich.text import Text
from textual.widgets import DataTable, RichLog, Static

from sleeper_agent.draft_tools.bigboard import BigboardRow
from sleeper_agent.draft_tools.board import RosterRequirement
from sleeper_agent.draft_tools.board_app import DraftBoardApp, DraftBoardModel
from sleeper_agent.models.sleeper import DraftPick
from sleeper_agent.sleeper_client.http import SleeperHTTPError

POLL_SECONDS = 0.05


def _bigboard(n: int) -> list[BigboardRow]:
    return [
        BigboardRow(
            rank=i + 1,
            player_id=str(i + 1),
            name=f"Player {i + 1}",
            position="RB",
            source="vorp",
            vorp=float(50 - i),
            draft_round=None,
            rationale="",
            log_ref=None,
        )
        for i in range(n)
    ]


def _pick(
    pick_no: int, draft_slot: int, *, player_id: str | None = None
) -> DraftPick:
    return DraftPick(
        draft_id="d1",
        round=1,
        pick_no=pick_no,
        draft_slot=draft_slot,
        roster_id=draft_slot,
        player_id=player_id or str(pick_no),
        is_keeper=False,
        picked_by=f"u{draft_slot}",
        player_name=f"Player {player_id or pick_no}",
        player_position="RB",
        player_team="SF",
    )


def _model(
    bigboard: list[BigboardRow],
    *,
    total_picks: int = 180,
    my_draft_slot: int | None = None,
    my_roster_id: int | None = None,
) -> DraftBoardModel:
    requirement = RosterRequirement(
        hard_min={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1}, flex_capacity=2
    )
    return DraftBoardModel(
        bigboard,
        top_n=len(bigboard),
        num_teams=12,
        draft_type="snake",
        total_picks=total_picks,
        my_roster_id=my_roster_id,
        my_draft_slot=my_draft_slot,
        requirement=requirement,
    )


def _run_until_done(
    app: DraftBoardApp,
    condition: Callable[[], bool],
    check: Callable[[DraftBoardApp], None],
    pauses: int = 100,
) -> None:
    """Run the app headlessly, pausing until `condition` holds; `check` then
    runs *inside* the app context (afterwards the DOM tree is torn down, so
    widget queries are only valid in there)."""

    async def drive() -> None:
        async with app.run_test(size=(100, 28)) as pilot:
            for _ in range(pauses):
                if condition():
                    check(app)
                    return
                await pilot.pause(POLL_SECONDS)

    asyncio.run(drive())


def _picks_panel_lines(app: DraftBoardApp) -> list[str]:
    panel = app.query_one("#picks", RichLog)
    return [line.text for line in panel.lines]


def _status_text(app: DraftBoardApp) -> str:
    content = app.query_one("#status", Static).content
    assert isinstance(content, Text)
    return content.plain


def _board_row_count(app: DraftBoardApp) -> int:
    return app.query_one("#board", DataTable).row_count


def test_app_redraws_board_and_streams_picks() -> None:
    bigboard = _bigboard(5)
    calls: list[int] = []

    def fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        calls.append(len(calls) + 1)
        return [_pick(n, n) for n in range(1, len(calls) + 1)]

    app = DraftBoardApp(
        _model(bigboard),
        draft_id="d1",
        poll_seconds=POLL_SECONDS,
        show_picks=True,
        fetch_picks=fetch,
    )

    def done() -> bool:
        # 3 of the 5 bigboard players drafted -> board shows 2
        return len(calls) >= 3 and _board_row_count(app) == 2

    def check(app: DraftBoardApp) -> None:
        assert _board_row_count(app) == 2
        lines = _picks_panel_lines(app)
        assert len(lines) >= 3
        assert "Pick 1 (slot 1): Player 1 (RB, SF)" in lines[0]

    _run_until_done(app, done, check)


def test_app_streams_my_pick_and_flags_turn() -> None:
    bigboard = _bigboard(12)
    # Picks 1..7 land; slot 8 is mine -> pick 8 is next -> "YOUR PICK"
    fetch = lambda draft_id, base_url: [_pick(n, n) for n in range(1, 8)]

    app = DraftBoardApp(
        _model(bigboard, my_draft_slot=8),
        draft_id="d1",
        poll_seconds=POLL_SECONDS,
        fetch_picks=fetch,
    )

    def done() -> bool:
        return "YOUR PICK — pick 8" in _status_text(app)

    def check(app: DraftBoardApp) -> None:
        assert "YOUR PICK — pick 8" in _status_text(app)

    _run_until_done(app, done, check)


def test_app_toggles_picks_panel_with_p_key() -> None:
    app = DraftBoardApp(
        _model(_bigboard(1)),
        draft_id="d1",
        poll_seconds=POLL_SECONDS,
        show_picks=True,
        fetch_picks=lambda draft_id, base_url: [],
    )

    async def drive() -> None:
        async with app.run_test(size=(100, 28)) as pilot:
            await pilot.pause()
            panel = app.query_one("#picks", RichLog)
            assert not panel.has_class("hidden")
            await pilot.press("p")
            await pilot.pause()
            assert panel.has_class("hidden")
            await pilot.press("p")
            await pilot.pause()
            assert not panel.has_class("hidden")

    asyncio.run(drive())


def test_app_survives_fetch_failure_and_shows_it_in_status() -> None:
    bigboard = _bigboard(3)
    calls: list[int] = []

    def fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        calls.append(len(calls))
        if len(calls) == 1:
            raise SleeperHTTPError("http://x", 503)
        return [_pick(1, 1)]

    app = DraftBoardApp(
        _model(bigboard),
        draft_id="d1",
        poll_seconds=POLL_SECONDS,
        fetch_picks=fetch,
    )

    def done() -> bool:
        # failure shown on poll 1, recovered on poll 2
        return len(calls) >= 2 and "last fetch failed" not in _status_text(app)

    def check(app: DraftBoardApp) -> None:
        assert len(calls) >= 2
        assert "picks 1/180" in _status_text(app)
        assert _board_row_count(app) == 2  # drafted player 1 dropped from board

    _run_until_done(app, done, check)


def test_app_exits_when_draft_completes() -> None:
    app = DraftBoardApp(
        _model(_bigboard(2), total_picks=2),
        draft_id="d1",
        poll_seconds=POLL_SECONDS,
        fetch_picks=lambda draft_id, base_url: [_pick(1, 1), _pick(2, 2)],
        complete_exit_seconds=0.2,
    )

    async def drive() -> None:
        async with app.run_test(size=(100, 28)) as pilot:
            for _ in range(200):
                if not app.is_running:
                    return
                await pilot.pause(POLL_SECONDS)

    asyncio.run(drive())
    assert not app.is_running


def test_app_request_exception_is_treated_like_http_error() -> None:
    def fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        raise requests.exceptions.ConnectionError("conn reset")

    app = DraftBoardApp(
        _model(_bigboard(1)),
        draft_id="d1",
        poll_seconds=POLL_SECONDS,
        fetch_picks=fetch,
    )

    def done() -> bool:
        return "last fetch failed: conn reset" in _status_text(app)

    def check(app: DraftBoardApp) -> None:
        assert app.is_running  # a blip must not kill the session

    _run_until_done(app, done, check)