from __future__ import annotations

from typing import Literal

import pytest

from sleeper_agent.draft_tools.bigboard import BigboardRow
from sleeper_agent.draft_tools.recap import (
    DraftNotCompleteError,
    build_team_recaps,
    check_draft_complete,
    recap_to_dict,
    render_recap_text,
)
from sleeper_agent.models.sleeper import Draft, DraftPick


def _draft(
    *,
    rounds: int = 2,
    num_teams: int = 2,
    draft_id: str = "did1",
    season: str = "2026",
) -> Draft:
    return Draft(
        draft_id=draft_id,
        league_id="",
        season=season,
        status="complete",
        draft_type="snake",
        rounds=rounds,
        num_teams=num_teams,
        start_time_ms=None,
        slots_qb=1,
        slots_rb=2,
        slots_wr=2,
        slots_te=1,
        slots_flex=2,
        slots_def=1,
        slot_to_roster_id={1: 5, 2: 6},
    )


def _pick(
    round_: int,
    pick_no: int,
    draft_slot: int,
    player_id: str,
    *,
    roster_id: int | None = None,
    is_keeper: bool = False,
    name: str | None = None,
    position: str | None = None,
) -> DraftPick:
    return DraftPick(
        draft_id="did1",
        round=round_,
        pick_no=pick_no,
        draft_slot=draft_slot,
        roster_id=roster_id,
        player_id=player_id,
        is_keeper=is_keeper,
        picked_by=None,
        player_name=name,
        player_position=position,
        player_team=None,
    )


def _bigboard_row(
    rank: int,
    player_id: str,
    *,
    vorp: float | None = 10.0,
    position: str = "RB",
    source: Literal["vorp", "rookie"] = "vorp",
) -> BigboardRow:
    return BigboardRow(
        rank=rank,
        player_id=player_id,
        name=f"Player {player_id}",
        position=position,
        source=source,
        vorp=vorp,
        draft_round=None,
        rationale="",
        log_ref=None,
    )


def test_check_draft_complete_passes_when_picks_match_expected() -> None:
    draft = _draft(rounds=2, num_teams=2)
    picks = [
        _pick(1, 1, 1, "a"),
        _pick(1, 2, 2, "b"),
        _pick(2, 3, 2, "c"),
        _pick(2, 4, 1, "d"),
    ]
    check_draft_complete(draft, picks)


def test_check_draft_complete_raises_when_picks_are_short() -> None:
    draft = _draft(rounds=2, num_teams=2)
    picks = [_pick(1, 1, 1, "a")]
    with pytest.raises(DraftNotCompleteError) as exc_info:
        check_draft_complete(draft, picks)
    assert exc_info.value.picks_made == 1
    assert exc_info.value.picks_expected == 4
    assert "did1" in str(exc_info.value)


def test_pick_recap_computes_positive_value_delta_for_a_value_pick() -> None:
    picks = [_pick(1, 8, 1, "p1", roster_id=5, name="Bijan Robinson", position="RB")]
    bigboard = [_bigboard_row(5, "p1", vorp=87.4)]
    teams = build_team_recaps(picks, bigboard, {})
    pick = teams[0].picks[0]
    assert pick.board_rank == 5
    assert pick.vorp == 87.4
    assert pick.value_delta == 3


def test_pick_recap_computes_negative_value_delta_for_a_reach() -> None:
    picks = [_pick(1, 8, 1, "p1")]
    bigboard = [_bigboard_row(15, "p1")]
    teams = build_team_recaps(picks, bigboard, {})
    assert teams[0].picks[0].value_delta == -7


def test_pick_recap_is_null_when_player_has_no_bigboard_row() -> None:
    picks = [_pick(1, 8, 1, "def1", name="Steelers", position="DEF")]
    teams = build_team_recaps(picks, [], {})
    pick = teams[0].picks[0]
    assert pick.board_rank is None
    assert pick.vorp is None
    assert pick.value_delta is None


def test_pick_recap_handles_null_vorp_on_rookie_rows() -> None:
    picks = [_pick(1, 3, 1, "r1")]
    bigboard = [_bigboard_row(2, "r1", vorp=None, source="rookie")]
    teams = build_team_recaps(picks, bigboard, {})
    pick = teams[0].picks[0]
    assert pick.board_rank == 2
    assert pick.vorp is None
    assert pick.value_delta == 1


def test_pick_recap_passes_through_is_keeper() -> None:
    picks = [_pick(1, 8, 1, "p1", is_keeper=True)]
    teams = build_team_recaps(picks, [_bigboard_row(1, "p1")], {})
    assert teams[0].picks[0].is_keeper is True


def test_build_team_recaps_groups_by_draft_slot_and_sorts_by_pick_no() -> None:
    picks = [
        _pick(2, 5, 1, "p2"),
        _pick(1, 1, 1, "p1"),
        _pick(1, 2, 2, "p3"),
    ]
    teams = build_team_recaps(picks, [], {})
    assert [t.draft_slot for t in teams] == [1, 2]
    assert [p.pick_no for p in teams[0].picks] == [1, 5]


def test_build_team_recaps_mean_value_delta_averages_only_non_null_deltas() -> None:
    picks = [_pick(1, 1, 1, "p1"), _pick(2, 2, 1, "p2")]
    bigboard = [_bigboard_row(3, "p1"), _bigboard_row(1, "p2")]
    teams = build_team_recaps(picks, bigboard, {})
    assert teams[0].mean_value_delta == -0.5


def test_build_team_recaps_mean_value_delta_is_none_with_no_resolvable_picks() -> None:
    picks = [_pick(1, 1, 1, "def1")]
    teams = build_team_recaps(picks, [], {})
    assert teams[0].mean_value_delta is None


def test_build_team_recaps_uses_real_team_name_when_provided() -> None:
    picks = [_pick(1, 1, 1, "p1")]
    teams = build_team_recaps(picks, [], {1: "Only Gold's Finest"})
    assert teams[0].team_name == "Only Gold's Finest"


def test_build_team_recaps_falls_back_to_slot_label_when_name_missing() -> None:
    picks = [_pick(1, 1, 3, "p1")]
    teams = build_team_recaps(picks, [], {})
    assert teams[0].team_name == "Slot 3"


def test_build_team_recaps_carries_roster_id_from_first_pick() -> None:
    picks = [_pick(1, 1, 1, "p1", roster_id=5), _pick(2, 2, 1, "p2", roster_id=5)]
    teams = build_team_recaps(picks, [], {})
    assert teams[0].roster_id == 5


def test_build_team_recaps_roster_id_is_none_for_mock_draft_picks() -> None:
    picks = [_pick(1, 1, 1, "p1", roster_id=None)]
    teams = build_team_recaps(picks, [], {})
    assert teams[0].roster_id is None


def test_recap_to_dict_matches_schema() -> None:
    draft = _draft(draft_id="did1", season="2026")
    picks = [_pick(1, 8, 1, "p1", roster_id=5, name="Bijan Robinson", position="RB")]
    bigboard = [_bigboard_row(5, "p1", vorp=87.4)]
    teams = build_team_recaps(picks, bigboard, {1: "Only Gold's Finest"})
    result = recap_to_dict(draft, "2025", teams)
    assert result == {
        "draft_id": "did1",
        "draft_season": "2026",
        "value_season": "2025",
        "num_teams": 2,
        "teams": [
            {
                "draft_slot": 1,
                "roster_id": 5,
                "team_name": "Only Gold's Finest",
                "mean_value_delta": 3.0,
                "picks": [
                    {
                        "round": 1,
                        "pick_no": 8,
                        "player_id": "p1",
                        "name": "Bijan Robinson",
                        "position": "RB",
                        "is_keeper": False,
                        "board_rank": 5,
                        "vorp": 87.4,
                        "value_delta": 3,
                    }
                ],
            }
        ],
    }


def test_render_recap_text_includes_value_delta_and_no_data_marker() -> None:
    picks = [
        _pick(1, 8, 1, "p1", name="Bijan Robinson", position="RB"),
        _pick(1, 9, 1, "def1", name="Steelers", position="DEF"),
    ]
    bigboard = [_bigboard_row(5, "p1", vorp=87.4)]
    teams = build_team_recaps(picks, bigboard, {1: "Slot 1"})
    text = render_recap_text(teams)
    assert "Bijan Robinson" in text
    assert "Δ=+3" in text
    assert "no board data" in text


def test_render_recap_text_shows_n_a_mean_when_no_resolvable_picks() -> None:
    picks = [_pick(1, 8, 1, "def1", name="Steelers", position="DEF")]
    teams = build_team_recaps(picks, [], {})
    text = render_recap_text(teams)
    assert "n/a" in text


def test_render_recap_text_shows_vorp_dashes_when_rank_known_but_vorp_missing() -> None:
    picks = [_pick(1, 3, 1, "r1", name="Rookie McRookieface", position="RB")]
    bigboard = [_bigboard_row(2, "r1", vorp=None, source="rookie")]
    teams = build_team_recaps(picks, bigboard, {})
    text = render_recap_text(teams)
    assert "vorp=--" in text
    assert "rank=2" in text


def test_render_recap_text_tags_keeper_picks() -> None:
    picks = [_pick(1, 8, 1, "p1", is_keeper=True, name="Stefon Diggs", position="WR")]
    teams = build_team_recaps(picks, [_bigboard_row(5, "p1")], {})
    text = render_recap_text(teams)
    assert "[KEEPER]" in text


def test_render_recap_text_falls_back_to_player_id_and_unknown_position_when_missing() -> (
    None
):
    picks = [_pick(1, 8, 1, "p1", name=None, position=None)]
    teams = build_team_recaps(picks, [_bigboard_row(5, "p1")], {})
    text = render_recap_text(teams)
    assert "p1" in text
    assert "(?)" in text
