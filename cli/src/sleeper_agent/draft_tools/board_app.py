"""`draft board` TUI — Textual app over the same model as `render_board`.

Live mode polls the draft's public picks endpoint, merges each response into
an accumulated `pick_no -> DraftPick` map (same semantics the old
`draft watch-picks` had: keeper picks arrive pre-filled at their real
`pick_no`, so keying by `pick_no` — never by count — is what makes a
transiently short response a structural no-op), clear/redraws the
best-available board whenever a new pick lands, and streams each new pick as
one line into a toggleable picks panel (`p`/`Tab`).

`DraftBoardModel` is a plain class with no Textual imports beyond the
rendering app below, so the merge/turn-detection/board-derivation logic is
unit-testable without a terminal.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import ClassVar

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, RichLog, Static

from sleeper_agent.draft_tools.bigboard import BigboardRow
from sleeper_agent.draft_tools.board import (
    RosterRequirement,
    bigboard_view,
    compute_tiers,
    my_roster_positions,
    next_unmade_pick_no,
    picks_in_order,
    position_tag,
    remaining_flex_capacity,
    render_pick_line,
    render_roster_summary,
    slot_for_pick,
)
from sleeper_agent.models.sleeper import DraftPick
from sleeper_agent.sleeper_client.draft import fetch_draft_picks
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL
from sleeper_agent.value.team_changes import TeamChange

AUTO_EXIT_AFTER_COMPLETE_SECONDS = 10.0


@dataclass(frozen=True)
class BoardRowView:
    """One row of the TUI's best-available table (render-board data, structured)."""

    rank: int
    name: str
    position: str
    detail: str  # "50.0" (vorp) or "ROOKIE R1"
    tag: str | None  # "NEED"/"SURPLUS"/"SURPLUS, FLEX" when "me" is resolved, else None
    tier: int | None
    flags: tuple[str, ...]  # "[MOVED: A→B]", "[INJ: ...]"


@dataclass(frozen=True)
class BoardUiState:
    """Everything the app needs to redraw after one poll."""

    roster_summary: str | None
    rows: tuple[BoardRowView, ...]
    new_pick_lines: tuple[str, ...]  # lines for picks unseen on every prior poll
    picks_seen: int
    total_picks: int | None
    next_pick_no: int | None
    my_turn: bool
    completed: bool


class DraftBoardModel:
    """Pick-merge + board-derivation state for the TUI.

    Feeding it each poll's picks yields the full UI state: which pick lines
    are *new* (for the stream panel), the derived best-available board rows
    (for the clear/redraw), roster-need annotation, snake turn detection, and
    completion. Idempotent across polls — a transiently short response can
    only fail to add entries, never drop or re-emit ones already seen.
    """

    def __init__(
        self,
        bigboard_rows: Sequence[BigboardRow],
        *,
        top_n: int,
        num_teams: int,
        draft_type: str,
        total_picks: int | None,
        my_roster_id: int | None = None,
        my_draft_slot: int | None = None,
        requirement: RosterRequirement | None = None,
        team_changes: dict[str, TeamChange] | None = None,
        injury_statuses: dict[str, str] | None = None,
    ) -> None:
        self._bigboard_rows = list(bigboard_rows)
        self._top_n = top_n
        self._num_teams = num_teams
        self._draft_type = draft_type
        self._total_picks = total_picks
        self._my_roster_id = my_roster_id
        self._my_draft_slot = my_draft_slot
        self._requirement = requirement
        self._team_changes = team_changes or {}
        self._injury_statuses = injury_statuses or {}
        self._picks_by_no: dict[int, DraftPick] = {}

    def feed(self, picks: Sequence[DraftPick]) -> BoardUiState:
        new_picks: list[DraftPick] = []
        for pick in sorted(picks, key=lambda p: p.pick_no):
            if pick.pick_no not in self._picks_by_no:
                self._picks_by_no[pick.pick_no] = pick
                new_picks.append(pick)

        ordered = picks_in_order(self._picks_by_no)
        rows, roster_summary = self._board_view(ordered)

        next_pick_no: int | None = None
        my_turn = False
        if (
            self._draft_type == "snake"
            and self._my_draft_slot is not None
            and self._total_picks is not None
        ):
            next_pick_no = next_unmade_pick_no(self._picks_by_no, self._total_picks)
            my_turn = (
                next_pick_no is not None
                and slot_for_pick(next_pick_no, self._num_teams) == self._my_draft_slot
            )
        completed = (
            self._total_picks is not None
            and len(self._picks_by_no) >= self._total_picks
        )
        return BoardUiState(
            roster_summary=roster_summary,
            rows=tuple(rows),
            new_pick_lines=tuple(
                render_pick_line(pick, self._my_draft_slot) for pick in new_picks
            ),
            picks_seen=len(self._picks_by_no),
            total_picks=self._total_picks,
            next_pick_no=next_pick_no,
            my_turn=my_turn,
            completed=completed,
        )

    def _board_view(
        self, picks: list[DraftPick]
    ) -> tuple[list[BoardRowView], str | None]:
        board = bigboard_view(self._bigboard_rows, picks, top_n=self._top_n)
        if self._my_roster_id is not None and self._requirement is not None:
            my_counts = my_roster_positions(
                picks, self._my_roster_id, my_draft_slot=self._my_draft_slot
            )
            requirement = self._requirement
            tiers = compute_tiers(board)
            remaining_flex = remaining_flex_capacity(my_counts, requirement)
        else:
            my_counts = None
            requirement = None
            tiers = {}
            remaining_flex = 0
        rows: list[BoardRowView] = []
        for rank, row in enumerate(board, start=1):
            if row.source == "rookie":
                detail = f"ROOKIE R{row.draft_round}"
            else:
                # A hand-edited bigboard CSV can carry source="vorp" with an
                # empty `vorp` cell and still load — render visibly, don't
                # crash the live loop (same convention as render_board).
                detail = f"{row.vorp:.1f}" if row.vorp is not None else "n/a"
            flags: list[str] = []
            change = self._team_changes.get(row.player_id)
            if change is not None:
                flags.append(f"[MOVED: {change.old_team}→{change.new_team}]")
            status = self._injury_statuses.get(row.player_id)
            if status is not None:
                flags.append(f"[INJ: {status}]")
            if my_counts is not None and requirement is not None:
                tag = position_tag(
                    row.position,
                    my_counts.get(row.position, 0),
                    requirement,
                    remaining_flex,
                )
                tier = tiers.get(row.player_id) if row.source == "vorp" else None
            else:
                tag = None
                tier = None
            rows.append(
                BoardRowView(
                    rank=rank,
                    name=row.name,
                    position=row.position,
                    detail=detail,
                    tag=tag,
                    tier=tier,
                    flags=tuple(flags),
                )
            )
        roster_summary = (
            render_roster_summary(my_counts, requirement)
            if my_counts is not None and requirement is not None
            else None
        )
        return rows, roster_summary


class DraftBoardApp(App[None]):
    """Best-available-by-value draft board with a live picks stream."""

    TITLE = "Sleeper draft board"
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_picks", "Toggle picks"),
        Binding("tab", "toggle_picks", "Toggle picks"),
        Binding("s", "toggle_surplus", "Hide surplus"),
    ]
    CSS: ClassVar[str] = """
    #status {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    #picks {
        width: 45%;
        border: round $accent;
    }
    #picks.hidden {
        display: none;
    }
    """

    class PicksFetched(Message):
        def __init__(self, picks: list[DraftPick]) -> None:
            self.picks = picks
            super().__init__()

    class FetchFailed(Message):
        def __init__(self, error: str) -> None:
            self.error = error
            super().__init__()

    def __init__(
        self,
        model: DraftBoardModel,
        *,
        draft_id: str,
        poll_seconds: float,
        show_picks: bool = False,
        base_url: str = SLEEPER_BASE_URL,
        fetch_picks: Callable[..., list[DraftPick]] = fetch_draft_picks,
        complete_exit_seconds: float = AUTO_EXIT_AFTER_COMPLETE_SECONDS,
    ) -> None:
        super().__init__()
        self._model = model
        self._draft_id = draft_id
        self._poll_seconds = poll_seconds
        self._show_picks = show_picks
        self._base_url = base_url
        self._fetch_picks = fetch_picks
        self._complete_exit_seconds = complete_exit_seconds
        self._last_state: BoardUiState | None = None
        self._last_error: str | None = None
        # Guards against overlapping polls: `@work(exclusive=False)` on the
        # fetch worker lets Textual launch a new one every tick regardless of
        # whether the previous fetch has returned. If a round-trip to Sleeper
        # ever runs longer than `poll_seconds`, that piles up concurrent
        # in-flight requests whose responses land in a burst — every redraw
        # in the burst is individually correct, but Textual only paints the
        # terminal once per idle cycle, so the visible effect is the board
        # looking frozen and then jumping straight to the final state. Skip
        # (not cancel) a tick while one is already in flight instead: unlike
        # `exclusive=True`, this can never starve a slow-but-eventually-
        # successful fetch by repeatedly cancelling it before it completes.
        self._poll_in_flight = False
        self._hide_surplus = False
        # Cached at on_mount: querying the DOM on every poll would be slow and
        # can transiently NoMatches while the screen tree is mid-update — the
        # references themselves are stable once mounted.
        self._board_widget: DataTable | None = None
        self._picks_widget: RichLog | None = None
        self._status_widget: Static | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("polling for picks…", id="status")
        yield Horizontal(
            DataTable(
                id="board",
                cursor_type="none",
                show_cursor=False,
            ),
            RichLog(
                id="picks",
                min_width=20,
                markup=False,
                wrap=True,
                highlight=False,
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        self._board_widget = self.query_one("#board", DataTable)
        self._picks_widget = self.query_one("#picks", RichLog)
        self._status_widget = self.query_one("#status", Static)
        self._board_widget.add_columns(
            "rank", "player", "pos", "value", "tier", "need", "notes"
        )
        if not self._show_picks:
            self._picks_widget.add_class("hidden")
        self._apply_state(self._model.feed([]))
        self.set_interval(self._poll_seconds, self._poll_once)

    def _board(self) -> DataTable:
        assert self._board_widget is not None
        return self._board_widget

    def _picks(self) -> RichLog:
        assert self._picks_widget is not None
        return self._picks_widget

    def _status(self) -> Static:
        assert self._status_widget is not None
        return self._status_widget

    def _poll_once(self) -> None:
        """`set_interval` tick handler. Only launches a new fetch if the
        previous one has already returned — see `_poll_in_flight`'s docstring
        in `__init__`."""
        if self._poll_in_flight:
            return
        self._poll_in_flight = True
        self._fetch_picks_worker()

    @work(exclusive=False, group="board-poll", thread=True)
    def _fetch_picks_worker(self) -> None:
        try:
            picks = self._fetch_picks(self._draft_id, base_url=self._base_url)
        except Exception as exc:  # noqa: BLE001
            # A single blip of *any* kind (timeout, DNS, malformed body, even a
            # response-parsing bug) must not end a live draft session. This is
            # deliberately broader than the old line-mode loops' catch of
            # (SleeperHTTPError, RequestException): in Textual 8 an uncaught
            # worker exception becomes a WorkerFailed that terminates the whole
            # app. Surface it in the status line and retry on the next poll.
            self.post_message(DraftBoardApp.FetchFailed(str(exc)))
        else:
            self.post_message(DraftBoardApp.PicksFetched(picks))

    @on(PicksFetched)
    def handle_picks_fetched(self, event: PicksFetched) -> None:
        self._poll_in_flight = False
        self._last_error = None
        self._apply_state(self._model.feed(event.picks))

    @on(FetchFailed)
    def handle_fetch_failed(self, event: FetchFailed) -> None:
        self._poll_in_flight = False
        self._last_error = event.error
        self._update_status()

    def action_toggle_picks(self) -> None:
        self._picks().toggle_class("hidden")

    def action_toggle_surplus(self) -> None:
        self._hide_surplus = not self._hide_surplus
        if self._last_state is not None:
            # Re-render immediately from the cached state rather than waiting
            # for the next poll — the toggle should feel instant.
            self._redraw_board(self._last_state)

    def _apply_state(self, state: BoardUiState) -> None:
        self._last_state = state
        for line in state.new_pick_lines:
            style = "bold" if "MY PICK" in line else ""
            self._picks().write(Text(line, style=style))
        self._redraw_board(state)
        self._update_status()
        if state.completed:
            # Consistent with the old `watch_picks` auto-return on completion;
            # give the final board a moment to be read first.
            self.set_timer(self._complete_exit_seconds, self.exit)

    def _redraw_board(self, state: BoardUiState) -> None:
        table = self._board()
        table.clear()
        rows = (
            [row for row in state.rows if row.tag != "SURPLUS"]
            if self._hide_surplus
            else state.rows
        )
        for row in rows:
            table.add_row(
                str(row.rank),
                row.name,
                row.position,
                row.detail,
                str(row.tier) if row.tier is not None else "",
                row.tag or "",
                " ".join(row.flags),
            )

    def _update_status(self) -> None:
        parts: list[str] = []
        state = self._last_state
        if state is not None:
            # Pick/turn status first: it's what you scan during the draft,
            # and the roster summary can be long enough to push it off-screen.
            if state.total_picks is not None:
                parts.append(f"picks {state.picks_seen}/{state.total_picks}")
                if state.completed:
                    parts.append("draft complete")
                elif state.my_turn:
                    parts.append(f"YOUR PICK — pick {state.next_pick_no}")
                elif state.next_pick_no is not None:
                    parts.append(f"next: pick {state.next_pick_no}")
            if state.roster_summary is not None:
                parts.append(state.roster_summary)
        if self._last_error is not None:
            parts.append(f"last fetch failed: {self._last_error} (retrying)")
        status = Text()
        for i, part in enumerate(parts):
            if i:
                status.append("  |  ")
            # Your-turn banner is the one thing you're scanning for on the
            # clock — make it loud.
            status.append(
                part, style="bold red" if part.startswith("YOUR PICK") else ""
            )
        self._status().update(status)
