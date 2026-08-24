"""Tests for the wargame draft-state machine (`sleeper_agent.wargame.state`)."""

from __future__ import annotations

from sleeper_agent.wargame.state import (
    BotPersona,
    DraftComplete,
    DraftConfig,
    DraftState,
    NotYourTurn,
    PlayerUnavailable,
    SelectionMade,
    WargamePlayer,
)

LEAGUE_ID = "league1"
DRAFT_ID = "draft1"
SLOTS = {slot: ((slot + 4) % 12) + 1 for slot in range(1, 13)}  # stable scramble


def make_config() -> DraftConfig:
    return DraftConfig(league_id=LEAGUE_ID, draft_id=DRAFT_ID, slot_to_roster_id=SLOTS)


def make_board(count: int = 40) -> dict[str, WargamePlayer]:
    positions = ["RB", "WR", "QB", "TE"]
    return {
        str(i): WargamePlayer(
            player_id=str(i),
            name=f"Player {i}",
            position=positions[i % 4],
            vorp=100.0 - i,
        )
        for i in range(count)
    }


def make_state(
    *,
    board_count: int = 40,
    personas: dict[int, BotPersona] | None = None,
) -> DraftState:
    return DraftState(
        config=make_config(),
        board=make_board(board_count),
        personas=personas or {},
    )


def test_total_picks_and_next_pick_no() -> None:
    state = make_state()

    assert state.config.total_picks == 180
    assert state.next_pick_no() == 1


def test_on_clock_roster_follows_snake_order_through_slots() -> None:
    state = make_state()

    # Pick 1 -> round 1 -> slot 1 -> SLOTS[1]
    assert state.on_clock_roster_id() == SLOTS[1]
    state.picks.append(_pick_at(1))
    # Pick 2 -> slot 2
    assert state.on_clock_roster_id() == SLOTS[2]
    # Jump to pick 13 (round 2 starts): snake reverses, round-2 slot-1 pick is owned by slot 12
    state.picks.extend(_pick_at(n) for n in range(2, 13))
    assert state.on_clock_roster_id() == SLOTS[12]


def test_seed_keepers_occupies_owner_pick_in_cost_round() -> None:
    state = make_state()
    # Our slot: find slot whose roster_id is 8; keep at cost round 7.
    our_slot = next(s for s, r in SLOTS.items() if r == 8)
    recorded = state.seed_keepers([(our_slot, 7, "5")])

    expected_pos = our_slot if 7 % 2 == 1 else 13 - our_slot
    expected_pick_no = 6 * 12 + expected_pos
    assert len(recorded) == 1
    assert recorded[0].pick_no == expected_pick_no
    assert recorded[0].is_keeper is True
    assert recorded[0].roster_id == 8
    assert state.available_players().get("5") is None
    assert state.next_pick_no() == 1  # keeper doesn't consume early picks


def test_make_selection_success_then_bots_fill_until_human_turn() -> None:
    personas = {
        roster: BotPersona(name=f"bot{roster}", multipliers={"RB": 1.2})
        for roster in range(1, 13)
        if roster != 8 and roster in set(SLOTS.values())
    }
    # Remove one bot persona so bots stop when that team is on the clock.
    human_two = max(personas)
    del personas[human_two]
    state = make_state(personas=personas)

    on_clock = state.on_clock_roster_id()
    assert on_clock is not None
    result = state.make_selection(on_clock, "0")

    assert isinstance(result, SelectionMade)
    assert result.pick.player_id == "0"
    # Bots filled every subsequent turn until reaching the persona-less team.
    after = state.on_clock_roster_id()
    assert after not in personas
    assert all(pick.roster_id != 8 for pick in result.subsequent_bot_picks)


def test_make_selection_rejects_when_not_on_clock() -> None:
    state = make_state()
    not_on_clock = next(r for r in SLOTS.values() if r != state.on_clock_roster_id())

    result = state.make_selection(not_on_clock, "0")

    assert isinstance(result, NotYourTurn)
    assert result.on_clock_roster_id == state.on_clock_roster_id()
    assert state.picks == []


def test_make_selection_rejects_unavailable_player() -> None:
    state = make_state(board_count=5)
    state.seed_keepers([(next(s for s, r in SLOTS.items() if r == 8), 7, "3")])
    on_clock = state.on_clock_roster_id()
    assert on_clock is not None

    result = state.make_selection(on_clock, "3")  # already kept -> off board

    assert isinstance(result, PlayerUnavailable)
    assert result.player_id == "3"


def test_make_selection_rejects_unknown_player() -> None:
    state = make_state(board_count=5)

    on_clock = state.on_clock_roster_id()
    assert on_clock is not None
    result = state.make_selection(on_clock, "9999")

    assert isinstance(result, PlayerUnavailable)


def test_selection_after_last_pick_reports_draft_complete() -> None:
    state = make_state(board_count=200)
    # Fill every pick except the last.
    total = state.config.total_picks
    while len(state.picks) < total - 1:
        available = state.available_players()
        state._record(state.board[min(available)], keeper=False)

    final_roster = state.on_clock_roster_id()
    assert final_roster is not None
    result = state.make_selection(final_roster, min(state.available_players()))
    assert isinstance(result, SelectionMade)
    assert result.pick.pick_no == total  # the last pick was just taken

    # Any further selection attempt reports the draft is complete.
    assert isinstance(state.make_selection(final_roster, "0"), DraftComplete)
    assert state.next_pick_no() is None
    assert state.on_clock_roster_id() is None


def test_bot_autopick_respects_position_multiplier() -> None:
    # Board where "0" is RB/vorp 100 and "1" is QB/vorp 99. A QB-loving bot
    # must take the QB; everyone else takes the RB.
    board = {
        "0": WargamePlayer("0", "Run CMC", "RB", 100.0),
        "1": WargamePlayer("1", "Arm", "QB", 99.0),
    }
    qb_hoarder = BotPersona(name="qbhoarder", multipliers={"QB": 2.0})

    rb_state = make_state()
    rb_state.board = board
    rb_state._bot_autopick(roster_id=1, persona=BotPersona("bpa", {}))

    qb_state = make_state()
    qb_state.board = board
    qb_state._bot_autopick(roster_id=1, persona=qb_hoarder)

    assert rb_state.picks[-1].player_id == "0"
    assert qb_state.picks[-1].player_id == "1"


def test_bot_autopick_with_empty_board_is_noop() -> None:
    state = make_state(board_count=0)

    state._bot_autopick(roster_id=1, persona=BotPersona("bpa", {}))

    assert state.picks == []


def _pick_at(pick_no: int):
    from sleeper_agent.draft_tools.board import slot_for_pick

    config = make_config()
    slot = slot_for_pick(pick_no, config.num_teams)
    from sleeper_agent.wargame.state import WargamePick

    return WargamePick(
        round=(pick_no - 1) // config.num_teams + 1,
        pick_no=pick_no,
        draft_slot=slot,
        roster_id=config.slot_to_roster_id[slot],
        player_id="filler",
        player_name="Filler",
        position="RB",
        is_keeper=False,
    )
