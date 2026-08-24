from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest
import requests

from sleeper_agent.draft_tools.bigboard import BigboardRow
from sleeper_agent.draft_tools.board import (
    RosterRequirement,
    bigboard_view,
    compute_tiers,
    my_roster_positions,
    position_tag,
    render_board,
    render_roster_summary,
    roster_requirement_from_draft,
    slot_for_pick,
    watch_board,
    watch_picks,
)
from sleeper_agent.draft_tools.keepers import (
    KeeperCandidate,
    build_season_chain,
    infer_total_rounds,
    rank_keeper_candidates,
    value_per_cost,
)
from sleeper_agent.models.sleeper import Draft, DraftPick
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.draft import (
    KeeperEligible,
    KeeperEligibleUndraftedDefault,
    KeeperIneligibleCostBelowRoundOne,
    KeeperIneligibleMaxYearsReached,
    keeper_history,
)
from sleeper_agent.sleeper_client.http import SleeperHTTPError
from sleeper_agent.storage.parquet_store import write_table
from sleeper_agent.value.team_changes import TeamChange

TOTAL_ROUNDS = 15


def make_pick(
    season_round: int,
    *,
    is_keeper: bool = False,
    player_id: str = "1",
    roster_id: int | None = 5,
    draft_slot: int = 1,
    player_name: str = "Test Player",
    player_team: str = "SF",
) -> DraftPick:
    return DraftPick(
        draft_id="did",
        round=season_round,
        pick_no=season_round * 12,
        draft_slot=draft_slot,
        roster_id=roster_id,
        player_id=player_id,
        is_keeper=is_keeper,
        picked_by="u1",
        player_name=player_name,
        player_position="RB",
        player_team=player_team,
    )


def test_keeper_history_never_kept_before_is_eligible_at_last_round_minus_one() -> None:
    picks_by_season = {"2025": [make_pick(4, is_keeper=False)]}

    status = keeper_history("1", 5, ["2025", "2024"], picks_by_season, TOTAL_ROUNDS)

    assert status == KeeperEligible(cost_round=3, last_round=4)


def test_keeper_history_kept_one_consecutive_year_is_eligible_again() -> None:
    picks_by_season = {
        "2025": [make_pick(3, is_keeper=True)],  # kept last year at round 3
        "2024": [make_pick(4, is_keeper=False)],  # originally drafted round 4
    }

    status = keeper_history(
        "1", 5, ["2025", "2024", "2023"], picks_by_season, TOTAL_ROUNDS
    )

    assert status == KeeperEligible(cost_round=2, last_round=3)


def test_keeper_history_kept_two_consecutive_years_is_ineligible_regardless_of_round() -> (
    None
):
    picks_by_season = {
        "2025": [make_pick(2, is_keeper=True)],
        "2024": [make_pick(3, is_keeper=True)],
        "2023": [make_pick(4, is_keeper=False)],
    }

    status = keeper_history(
        "1", 5, ["2025", "2024", "2023"], picks_by_season, TOTAL_ROUNDS
    )

    assert status == KeeperIneligibleMaxYearsReached(consecutive_kept_seasons=2)


def test_keeper_history_last_round_two_is_eligible_at_cost_round_one() -> None:
    picks_by_season = {"2025": [make_pick(2, is_keeper=False)]}

    status = keeper_history("1", 5, ["2025"], picks_by_season, TOTAL_ROUNDS)

    assert status == KeeperEligible(cost_round=1, last_round=2)


def test_keeper_history_last_round_one_is_ineligible_cost_would_be_zero() -> None:
    picks_by_season = {"2025": [make_pick(1, is_keeper=False)]}

    status = keeper_history("1", 5, ["2025"], picks_by_season, TOTAL_ROUNDS)

    assert status == KeeperIneligibleCostBelowRoundOne(last_round=1)


def test_keeper_history_no_draft_record_defaults_to_last_round() -> None:
    # Confirmed against real 2025 draft data: Sleeper keeps an undrafted
    # player (e.g. picked up via waiver) at the draft's final round rather
    # than marking them ineligible — see IMPLEMENTATION_PLAN.md Phase E.
    picks_by_season: dict[str, list[DraftPick]] = {
        "2025": [make_pick(1, player_id="other")]
    }

    status = keeper_history("1", 5, ["2025", "2024"], picks_by_season, TOTAL_ROUNDS)

    assert status == KeeperEligibleUndraftedDefault(cost_round=TOTAL_ROUNDS)


def test_keeper_history_walks_past_seasons_with_no_matching_pick_to_find_the_most_recent() -> (
    None
):
    # Player was kept every year since being acquired via trade in 2023 —
    # not drafted at all in 2024 or 2025 (no live pick, no keeper flag for
    # this roster in those years' data because they'd been kept prior).
    # This case models "the most recent record isn't in the newest season."
    picks_by_season = {
        "2024": [],
        "2023": [make_pick(5, is_keeper=False)],
    }

    status = keeper_history("1", 5, ["2024", "2023"], picks_by_season, TOTAL_ROUNDS)

    assert status == KeeperEligible(cost_round=4, last_round=5)


def test_keeper_history_stops_consecutive_count_when_chain_ends() -> None:
    picks_by_season = {"2025": [make_pick(3, is_keeper=True)]}

    status = keeper_history("1", 5, ["2025"], picks_by_season, TOTAL_ROUNDS)

    assert status == KeeperEligible(cost_round=2, last_round=3)


# --- build_season_chain --------------------------------------------------


def _write_drafts(repo_root: Path, season: str, picks: list[DraftPick]) -> None:
    write_table(
        sleeper_sync.draft_picks_to_dataframe(picks),
        repo_root / "data" / "sleeper" / "drafts" / f"{season}.parquet",
        schema_version=sleeper_sync.DRAFTS_SCHEMA_VERSION,
    )


def test_build_season_chain_reads_available_seasons_descending(tmp_path: Path) -> None:
    _write_drafts(tmp_path, "2025", [make_pick(3)])
    _write_drafts(tmp_path, "2024", [make_pick(4)])

    season_chain, picks_by_season = build_season_chain(tmp_path, "2026")

    assert season_chain == ["2025", "2024"]
    assert picks_by_season["2025"][0].round == 3
    assert picks_by_season["2024"][0].round == 4


def test_build_season_chain_stops_at_first_missing_season(tmp_path: Path) -> None:
    _write_drafts(tmp_path, "2025", [make_pick(3)])
    # 2024 is missing entirely; 2023 exists but shouldn't be reached.
    _write_drafts(tmp_path, "2023", [make_pick(5)])

    season_chain, _ = build_season_chain(tmp_path, "2026")

    assert season_chain == ["2025"]


def test_build_season_chain_respects_max_seasons_back(tmp_path: Path) -> None:
    for season in ("2025", "2024", "2023"):
        _write_drafts(tmp_path, season, [make_pick(1)])

    season_chain, _ = build_season_chain(tmp_path, "2026", max_seasons_back=2)

    assert season_chain == ["2025", "2024"]


# --- KeeperCandidate ranking ----------------------------------------------


def test_value_per_cost_computes_vorp_divided_by_cost() -> None:
    candidate = KeeperCandidate(
        player_id="1",
        name="A",
        position="RB",
        status=KeeperEligible(cost_round=2, last_round=3),
        vorp_season=20.0,
    )

    assert value_per_cost(candidate) == 10.0


def test_value_per_cost_is_negative_infinity_for_ineligible_or_missing_vorp() -> None:
    ineligible = KeeperCandidate(
        player_id="1",
        name="A",
        position="RB",
        status=KeeperIneligibleMaxYearsReached(consecutive_kept_seasons=2),
        vorp_season=20.0,
    )
    no_vorp = KeeperCandidate(
        player_id="2",
        name="B",
        position="RB",
        status=KeeperEligible(cost_round=2, last_round=3),
        vorp_season=None,
    )

    assert value_per_cost(ineligible) == float("-inf")
    assert value_per_cost(no_vorp) == float("-inf")


def test_rank_keeper_candidates_sorts_eligible_by_value_per_cost_then_lists_ineligible() -> (
    None
):
    cheap_but_valuable = KeeperCandidate(
        player_id="1",
        name="Cheap",
        position="RB",
        status=KeeperEligible(cost_round=9, last_round=10),
        vorp_season=90.0,
    )
    expensive = KeeperCandidate(
        player_id="2",
        name="Expensive",
        position="RB",
        status=KeeperEligible(cost_round=2, last_round=3),
        vorp_season=10.0,
    )
    ineligible = KeeperCandidate(
        player_id="3",
        name="Ineligible",
        position="RB",
        status=KeeperIneligibleMaxYearsReached(consecutive_kept_seasons=2),
        vorp_season=None,
    )

    ranked = rank_keeper_candidates([expensive, ineligible, cheap_but_valuable])

    assert [c.player_id for c in ranked] == ["1", "2", "3"]


def test_value_per_cost_treats_undrafted_default_as_eligible() -> None:
    candidate = KeeperCandidate(
        player_id="1",
        name="A",
        position="RB",
        status=KeeperEligibleUndraftedDefault(cost_round=15),
        vorp_season=30.0,
    )

    assert value_per_cost(candidate) == 2.0


def test_rank_keeper_candidates_ranks_undrafted_default_alongside_normal_eligible() -> (
    None
):
    undrafted = KeeperCandidate(
        player_id="1",
        name="Undrafted",
        position="RB",
        status=KeeperEligibleUndraftedDefault(cost_round=15),
        vorp_season=150.0,
    )
    normal = KeeperCandidate(
        player_id="2",
        name="Normal",
        position="RB",
        status=KeeperEligible(cost_round=5, last_round=6),
        vorp_season=25.0,
    )

    ranked = rank_keeper_candidates([normal, undrafted])

    assert [c.player_id for c in ranked] == ["1", "2"]  # 10/round beats 5/round


# --- infer_total_rounds ---------------------------------------------------


def test_infer_total_rounds_uses_max_round_from_most_recent_season() -> None:
    picks_by_season = {"2025": [make_pick(10), make_pick(15)], "2024": [make_pick(12)]}

    assert infer_total_rounds(["2025", "2024"], picks_by_season) == 15


def test_infer_total_rounds_falls_back_to_default_with_no_history() -> None:
    assert infer_total_rounds([], {}) == 15
    assert infer_total_rounds([], {}, default=12) == 12


def test_infer_total_rounds_falls_back_when_most_recent_season_has_no_picks() -> None:
    assert infer_total_rounds(["2025"], {"2025": []}, default=12) == 12


# --- draft board -----------------------------------------------------------


def _bigboard_row(
    *,
    rank: int,
    player_id: str,
    name: str | None = None,
    position: str = "RB",
    source: Literal["vorp", "rookie"] = "vorp",
    vorp: float | None = 0.0,
    draft_round: int | None = None,
    rationale: str = "",
    log_ref: str | None = None,
) -> BigboardRow:
    return BigboardRow(
        rank=rank,
        player_id=player_id,
        name=name or f"Player {player_id}",
        position=position,
        source=source,
        vorp=vorp,
        draft_round=draft_round,
        rationale=rationale,
        log_ref=log_ref,
    )


def make_bigboard() -> list[BigboardRow]:
    return [
        _bigboard_row(
            rank=1, player_id="1", name="Player One", position="RB", vorp=50.0
        ),
        _bigboard_row(
            rank=2, player_id="2", name="Player Two", position="WR", vorp=30.0
        ),
        _bigboard_row(
            rank=3, player_id="3", name="Player Three", position="QB", vorp=10.0
        ),
    ]


def test_bigboard_view_excludes_drafted_and_kept_players() -> None:
    board = make_bigboard()
    picks = [make_pick(1, player_id="1"), make_pick(2, player_id="2", is_keeper=True)]

    result = bigboard_view(board, picks)

    assert [row.player_id for row in result] == ["3"]


def test_bigboard_view_respects_top_n() -> None:
    board = make_bigboard()

    result = bigboard_view(board, [], top_n=1)

    assert [row.player_id for row in result] == ["1"]


def test_bigboard_view_preserves_bigboard_rank_order_not_vorp_order() -> None:
    # rank order and VORP order deliberately disagree: rank=1 has the lower
    # VORP. bigboard_view must return bigboard rank order (the LLM-reviewed
    # ordinal ranking) — the old board_view re-sorted by vorp_season, which
    # this task's rewrite deliberately dropped.
    board = [
        _bigboard_row(rank=1, player_id="1", vorp=10.0),
        _bigboard_row(rank=2, player_id="2", vorp=50.0),
    ]

    result = bigboard_view(board, [])

    assert [row.player_id for row in result] == ["1", "2"]


def test_render_board_formats_ranked_lines() -> None:
    board = make_bigboard()[:1]

    rendered = render_board(board)

    assert "Best available by value:" in rendered
    assert " 1. Player One" in rendered


def test_render_board_without_annotation_is_unchanged() -> None:
    board = make_bigboard()[:1]

    rendered = render_board(board)

    assert rendered == (
        "Best available by value:\n 1. Player One                RB  vorp=   50.0"
    )


def test_render_board_with_annotation_adds_summary_tags_and_tiers() -> None:
    board = make_bigboard()  # RB=50.0, WR=30.0, QB=10.0 — one player each
    requirement = RosterRequirement(
        hard_min={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1}, flex_capacity=2
    )
    my_counts = {"RB": 5, "WR": 1}

    rendered = render_board(board, my_counts=my_counts, requirement=requirement)

    assert "My roster so far:" in rendered
    assert "RB 5/2" in rendered
    assert "WR 1/2" in rendered
    assert "(2 FLEX slots shared across RB/WR/TE)" in rendered
    # RB is drafted well past hard_min + flex_capacity (5 >= 2 + 2) -> SURPLUS
    assert "RB  vorp=   50.0 tier=1 [SURPLUS]" in rendered
    # WR is below hard_min (1 < 2) -> NEED
    assert "WR  vorp=   30.0 tier=1 [NEED]" in rendered


def test_render_roster_summary_omits_flex_note_when_no_flex_capacity() -> None:
    requirement = RosterRequirement(hard_min={"QB": 1, "DEF": 1}, flex_capacity=0)

    summary = render_roster_summary({"QB": 1}, requirement)

    assert summary == "My roster so far: QB 1/1  RB 0/0  WR 0/0  TE 0/0  DEF 0/1"
    assert "FLEX" not in summary


def test_render_board_annotation_requires_both_counts_and_requirement() -> None:
    board = make_bigboard()[:1]
    requirement = RosterRequirement(hard_min={"RB": 2}, flex_capacity=2)

    # my_counts given without requirement (or vice versa) is treated as "no annotation",
    # not a partial one -- avoids ever rendering tags with no requirement to check against.
    rendered = render_board(board, my_counts={"RB": 1}, requirement=None)

    assert "My roster so far" not in rendered
    assert "tier=" not in rendered
    rendered_other_way = render_board(board, my_counts=None, requirement=requirement)
    assert "My roster so far" not in rendered_other_way


def test_render_board_source_vorp_row_with_null_vorp_does_not_crash() -> None:
    # A hand-edited bigboard CSV could carry source="vorp" with an empty
    # `vorp` cell and still load fine (nothing in bigboard.py enforces the
    # pairing). render_board runs inside watch_board's live polling loop, so
    # this must render something rather than raise a bare TypeError.
    board = [_bigboard_row(rank=1, player_id="1", source="vorp", vorp=None)]

    rendered = render_board(board)

    assert "n/a" in rendered
    assert " 1. Player 1" in rendered


def test_render_board_renders_rookie_row_with_rookie_tag_not_vorp() -> None:
    board = [
        _bigboard_row(rank=1, player_id="1", source="rookie", vorp=None, draft_round=2),
    ]
    rendered = render_board(board)
    assert "[ROOKIE R2]" in rendered
    assert "vorp=" not in rendered


def test_render_board_rookie_row_gets_need_tag_but_no_tier() -> None:
    board = [
        _bigboard_row(
            rank=1,
            player_id="1",
            position="RB",
            source="rookie",
            vorp=None,
            draft_round=1,
        ),
    ]
    rendered = render_board(
        board,
        my_counts={},
        requirement=RosterRequirement(hard_min={"RB": 2}, flex_capacity=0),
    )
    assert "[NEED]" in rendered
    assert "tier=" not in rendered


def test_watch_board_only_rerenders_when_drafted_ids_change(tmp_path: Path) -> None:
    board = make_bigboard()
    call_log: list[list[DraftPick]] = [
        [],
        [],  # unchanged from previous iteration - should not re-render
        [make_pick(1, player_id="1")],  # changed - should re-render
    ]
    rendered_calls: list[str] = []
    sleeps: list[float] = []
    log_path = tmp_path / "draft-live.md"

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    watch_board(
        "did",
        board,
        sleep=sleeps.append,
        max_iterations=3,
        render=rendered_calls.append,
        fetch_picks=fake_fetch,
        log_path=log_path,
    )

    assert len(rendered_calls) == 2
    assert sleeps == [5.0, 5.0]
    assert log_path.exists()
    assert "Player Two" in log_path.read_text()


def test_watch_board_works_without_a_log_path() -> None:
    board = make_bigboard()
    rendered_calls: list[str] = []

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return []

    watch_board(
        "did",
        board,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=fake_fetch,
    )

    assert len(rendered_calls) == 1


def test_watch_board_annotates_when_my_roster_id_given(tmp_path: Path) -> None:
    board = make_bigboard()
    requirement = RosterRequirement(
        hard_min={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1}, flex_capacity=2
    )
    rendered_calls: list[str] = []

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return [make_pick(1, player_id="99", roster_id=5, player_name="Mine")]

    watch_board(
        "did",
        board,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=fake_fetch,
        my_roster_id=5,
        requirement=requirement,
    )

    assert len(rendered_calls) == 1
    assert "My roster so far:" in rendered_calls[0]
    assert "RB 1/2" in rendered_calls[0]


def test_watch_board_without_my_roster_id_is_unannotated(tmp_path: Path) -> None:
    board = make_bigboard()
    rendered_calls: list[str] = []

    watch_board(
        "did",
        board,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=lambda draft_id, *, base_url: [],
    )

    assert "My roster so far" not in rendered_calls[0]


def test_watch_board_threads_team_changes_through_to_render_board() -> None:
    board = make_bigboard()  # player_id "1" is RB/50.0
    rendered_calls: list[str] = []

    watch_board(
        "did",
        board,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=lambda draft_id, *, base_url: [],
        team_changes={
            "1": TeamChange(
                sleeper_id="1",
                name="Player One",
                position="RB",
                old_team="CAR",
                new_team="PIT",
                total_touches=200,
            )
        },
    )

    assert "[MOVED: CAR" in rendered_calls[0]


def test_watch_board_without_team_changes_omits_moved_tag() -> None:
    board = make_bigboard()
    rendered_calls: list[str] = []

    watch_board(
        "did",
        board,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=lambda draft_id, *, base_url: [],
    )

    assert "[MOVED" not in rendered_calls[0]


def test_render_board_injury_status_tags_only_flagged_players() -> None:
    board = make_bigboard()

    rendered = render_board(board, injury_statuses={"2": "PUP"})

    # flagged player gets the tag; unflagged players render exactly as before
    player_two_line = next(
        line for line in rendered.splitlines() if "Player Two" in line
    )
    assert "[INJ: PUP]" in player_two_line
    assert "[INJ" not in rendered.split("Player Two")[0]


def test_render_board_injury_tag_combines_with_moved_tag() -> None:
    board = make_bigboard()
    change = TeamChange(
        sleeper_id="1",
        name="Player One",
        position="RB",
        old_team="CAR",
        new_team="PIT",
        total_touches=200,
    )

    rendered = render_board(
        board, team_changes={"1": change}, injury_statuses={"1": "Questionable"}
    )

    assert "[MOVED: CAR→PIT] [INJ: Questionable]" in rendered


def test_render_board_without_injury_statuses_is_unchanged() -> None:
    board = make_bigboard()[:1]

    rendered = render_board(board, injury_statuses=None)

    assert "[INJ" not in rendered


def test_watch_board_threads_injury_statuses_through_to_render_board() -> None:
    board = make_bigboard()  # player_id "1" is RB/50.0
    rendered_calls: list[str] = []

    watch_board(
        "did",
        board,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=lambda draft_id, *, base_url: [],
        injury_statuses={"1": "IR"},
    )

    assert "[INJ: IR]" in rendered_calls[0]


def make_draft(
    draft_id: str = "did",
    league_id: str = "lid",
    season: str = "2026",
    status: str = "drafting",
    draft_type: str = "snake",
    rounds: int = 15,
    num_teams: int = 12,
    start_time_ms: int | None = None,
    slots_qb: int = 1,
    slots_rb: int = 2,
    slots_wr: int = 2,
    slots_te: int = 1,
    slots_flex: int = 2,
    slots_def: int = 1,
    slot_to_roster_id: dict[int, int] | None = None,
) -> Draft:
    return Draft(
        draft_id=draft_id,
        league_id=league_id,
        season=season,
        status=status,
        draft_type=draft_type,
        rounds=rounds,
        num_teams=num_teams,
        start_time_ms=start_time_ms,
        slots_qb=slots_qb,
        slots_rb=slots_rb,
        slots_wr=slots_wr,
        slots_te=slots_te,
        slots_flex=slots_flex,
        slots_def=slots_def,
        slot_to_roster_id=slot_to_roster_id or {1: 5},
    )


def test_roster_requirement_from_draft_reads_slot_counts() -> None:
    requirement = roster_requirement_from_draft(make_draft())

    assert requirement.hard_min == {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1}
    assert requirement.flex_capacity == 2


def test_position_tag_below_hard_min_is_need() -> None:
    requirement = RosterRequirement(hard_min={"RB": 2}, flex_capacity=2)

    assert position_tag("RB", 1, requirement) == "NEED"


def test_position_tag_exactly_at_hard_min_is_flex_not_need() -> None:
    requirement = RosterRequirement(hard_min={"RB": 2}, flex_capacity=2)

    assert position_tag("RB", 2, requirement) == "FLEX"


def test_position_tag_exactly_at_hard_min_plus_flex_is_surplus_not_flex() -> None:
    requirement = RosterRequirement(hard_min={"RB": 2}, flex_capacity=2)

    assert position_tag("RB", 4, requirement) == "SURPLUS"


def test_position_tag_non_flex_eligible_position_skips_flex_tier() -> None:
    # QB isn't FLEX-eligible in this league, so hitting hard_min goes straight to SURPLUS.
    requirement = RosterRequirement(hard_min={"QB": 1}, flex_capacity=2)

    assert position_tag("QB", 1, requirement) == "SURPLUS"


# --- my_roster_positions --------------------------------------------------


def test_my_roster_positions_counts_only_my_roster_id() -> None:
    picks = [
        make_pick(1, player_id="1", roster_id=5, player_name="A"),
        make_pick(2, player_id="2", roster_id=5, player_name="B"),
        make_pick(1, player_id="3", roster_id=8, player_name="C"),
    ]

    counts = my_roster_positions(picks, my_roster_id=5)

    assert counts == {"RB": 2}  # make_pick's default player_position is "RB"


def test_my_roster_positions_buckets_missing_position_as_unk() -> None:
    picks = [
        DraftPick(
            draft_id="did",
            round=1,
            pick_no=1,
            draft_slot=1,
            roster_id=5,
            player_id="1",
            is_keeper=False,
            picked_by="u1",
            player_name="No Position",
            player_position=None,
            player_team=None,
        )
    ]

    counts = my_roster_positions(picks, my_roster_id=5)

    assert counts == {"UNK": 1}


def test_my_roster_positions_empty_for_no_picks() -> None:
    assert my_roster_positions([], my_roster_id=5) == {}


def test_my_roster_positions_matches_by_draft_slot_when_roster_id_is_null() -> None:
    # Sleeper's mock-draft picks endpoint always returns roster_id: null.
    # `--draft-slot` resolves my_roster_id via slot_to_roster_id anyway
    # (a real int, e.g. 8) — but pick.roster_id being None would never equal
    # that, so ownership must fall back to draft_slot matching or every mock
    # draft silently counts zero of the caller's own picks.
    picks = [
        make_pick(1, player_id="1", roster_id=None, draft_slot=8, player_name="A"),
        make_pick(2, player_id="2", roster_id=None, draft_slot=8, player_name="B"),
        make_pick(1, player_id="3", roster_id=None, draft_slot=3, player_name="C"),
    ]

    counts = my_roster_positions(picks, my_roster_id=8, my_draft_slot=8)

    assert counts == {"RB": 2}


# --- compute_tiers -------------------------------------------------------


def test_compute_tiers_increments_only_past_a_big_gap() -> None:
    # 100 -> 90 is a 10% drop (no break); 90 -> 50 is a ~44% drop (break)
    board = [
        _bigboard_row(rank=1, player_id="1", name="A", position="RB", vorp=100.0),
        _bigboard_row(rank=2, player_id="2", name="B", position="RB", vorp=90.0),
        _bigboard_row(rank=3, player_id="3", name="C", position="RB", vorp=50.0),
        _bigboard_row(rank=4, player_id="4", name="D", position="RB", vorp=45.0),
    ]

    tiers = compute_tiers(board)

    assert tiers == {"1": 1, "2": 1, "3": 2, "4": 2}


def test_compute_tiers_is_independent_per_position() -> None:
    board = [
        _bigboard_row(rank=1, player_id="1", name="RB One", position="RB", vorp=100.0),
        _bigboard_row(rank=2, player_id="2", name="WR One", position="WR", vorp=5.0),
    ]

    tiers = compute_tiers(board)

    # Each position's own list has only one player, so both are tier 1
    # regardless of the huge cross-position gap.
    assert tiers == {"1": 1, "2": 1}


def test_compute_tiers_treats_non_positive_vorp_as_always_a_break() -> None:
    board = [
        _bigboard_row(rank=1, player_id="1", name="A", position="RB", vorp=10.0),
        _bigboard_row(rank=2, player_id="2", name="B", position="RB", vorp=0.0),
        _bigboard_row(rank=3, player_id="3", name="C", position="RB", vorp=-5.0),
    ]

    tiers = compute_tiers(board)

    assert tiers == {"1": 1, "2": 2, "3": 3}


def test_compute_tiers_skips_rookie_rows() -> None:
    board = [
        _bigboard_row(rank=1, player_id="1", position="RB", source="vorp", vorp=100.0),
        _bigboard_row(rank=2, player_id="2", position="RB", source="rookie", vorp=None),
    ]
    tiers = compute_tiers(board)
    assert "2" not in tiers
    assert tiers["1"] == 1


# --- slot_for_pick -------------------------------------------------------


def test_slot_for_pick_round_1_is_ascending() -> None:
    assert slot_for_pick(1, 12) == 1
    assert slot_for_pick(8, 12) == 8
    assert slot_for_pick(12, 12) == 12


def test_slot_for_pick_round_2_is_descending() -> None:
    assert slot_for_pick(13, 12) == 12
    assert slot_for_pick(17, 12) == 8
    assert slot_for_pick(24, 12) == 1


def test_slot_for_pick_round_3_returns_to_ascending() -> None:
    assert slot_for_pick(25, 12) == 1
    assert slot_for_pick(36, 12) == 12


def test_slot_for_pick_with_odd_num_teams() -> None:
    # 10-team draft: round 1 ascending 1..10, round 2 descending 10..1.
    assert slot_for_pick(1, 10) == 1
    assert slot_for_pick(10, 10) == 10
    assert slot_for_pick(11, 10) == 10
    assert slot_for_pick(20, 10) == 1
    assert slot_for_pick(21, 10) == 1


def test_load_triaged_rookies_best_effort_empty_when_draft_picks_missing(
    tmp_path: Path,
) -> None:
    from sleeper_agent.draft_tools.rookies import load_triaged_rookies

    assert load_triaged_rookies(tmp_path, "2026") == []


# --- role-changer (FA/trade) [MOVED] tag -------------------------------------


def make_team_change(
    sleeper_id: str = "1", old_team: str = "CAR", new_team: str = "PIT"
) -> TeamChange:
    return TeamChange(
        sleeper_id=sleeper_id,
        name="Player One",
        position="RB",
        old_team=old_team,
        new_team=new_team,
        total_touches=200,
    )


def test_render_board_without_team_changes_is_unchanged() -> None:
    board = make_bigboard()[:1]

    rendered = render_board(board)

    assert rendered == (
        "Best available by value:\n 1. Player One                RB  vorp=   50.0"
    )


def test_render_board_tags_only_the_matching_player() -> None:
    board = make_bigboard()  # player_id 1, 2, 3
    team_changes = {"1": make_team_change(sleeper_id="1")}

    rendered = render_board(board, team_changes=team_changes)

    lines = rendered.splitlines()
    assert "[MOVED: CAR" in lines[1]
    assert "PIT]" in lines[1]
    assert "[MOVED" not in lines[2]
    assert "[MOVED" not in lines[3]


def test_render_board_moved_tag_does_not_change_sort_order_or_vorp_values() -> None:
    board = make_bigboard()
    team_changes = {"3": make_team_change(sleeper_id="3")}  # lowest-vorp player

    rendered = render_board(board, team_changes=team_changes)

    lines = rendered.splitlines()
    # unchanged rank order: Player One, Player Two, Player Three
    assert "Player One" in lines[1]
    assert "Player Two" in lines[2]
    assert "Player Three" in lines[3]
    assert "vorp=   50.0" in lines[1]
    assert "vorp=   30.0" in lines[2]
    assert "vorp=   10.0" in lines[3]
    assert "[MOVED" not in lines[1]
    assert "[MOVED" not in lines[2]
    assert "[MOVED" in lines[3]


def test_render_board_moved_tag_combines_with_roster_need_annotation() -> None:
    board = make_bigboard()
    requirement = RosterRequirement(
        hard_min={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1}, flex_capacity=2
    )
    team_changes = {"1": make_team_change(sleeper_id="1")}

    rendered = render_board(
        board, my_counts={}, requirement=requirement, team_changes=team_changes
    )

    # roster summary, blank, "Best available by value:", then rank 1
    line = rendered.splitlines()[3]
    assert "[NEED]" in line
    assert "[MOVED: CAR" in line


def test_render_board_omits_moved_tag_when_no_team_changes_given() -> None:
    board = make_bigboard()[:1]

    rendered = render_board(board)

    assert "[MOVED" not in rendered


# --- watch_picks -------------------------------------------------------


def _wp(
    pick_no: int,
    draft_slot: int,
    *,
    name: str = "Player",
    position: str = "RB",
    is_keeper: bool = False,
) -> DraftPick:
    return DraftPick(
        draft_id="did",
        round=1,
        pick_no=pick_no,
        draft_slot=draft_slot,
        roster_id=draft_slot,
        player_id=str(pick_no),
        is_keeper=is_keeper,
        picked_by=f"u{draft_slot}",
        player_name=name,
        player_position=position,
        player_team="SF",
    )


def test_watch_picks_prints_one_line_per_new_pick() -> None:
    call_log: list[list[DraftPick]] = [
        [_wp(1, 1, name="Alpha")],
        [_wp(1, 1, name="Alpha"), _wp(2, 2, name="Beta")],
    ]
    rendered: list[str] = []

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    watch_picks(
        "did",
        num_teams=12,
        draft_type="snake",
        my_draft_slot=None,
        total_picks=180,
        render_full_board=lambda picks: "BOARD",
        sleep=lambda seconds: None,
        max_iterations=2,
        render=rendered.append,
        fetch_picks=fake_fetch,
    )

    assert rendered == [
        "Pick 1 (slot 1): Alpha (RB, SF)",
        "Pick 2 (slot 2): Beta (RB, SF)",
    ]


def test_watch_picks_marks_my_pick() -> None:
    call_log: list[list[DraftPick]] = [
        [_wp(1, 1, name="Alpha"), _wp(2, 8, name="Beta")],
    ]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    rendered: list[str] = []
    watch_picks(
        "did",
        num_teams=12,
        draft_type="snake",
        my_draft_slot=8,
        total_picks=180,
        render_full_board=lambda picks: "BOARD",
        sleep=lambda seconds: None,
        max_iterations=1,
        render=rendered.append,
        fetch_picks=fake_fetch,
    )

    assert len(rendered) == 2
    assert rendered[0] == "Pick 1 (slot 1): Alpha (RB, SF)"
    assert rendered[1] == "Pick 2 (slot 8): Beta (RB, SF) <== MY PICK"


def test_watch_picks_renders_board_once_when_next_pick_is_mine() -> None:
    # 7 picks made (slots 1-7); pick 8 (slot 8, my slot) is next.
    seven_picks = [_wp(n, n, name=f"Player{n}") for n in range(1, 8)]
    call_log: list[list[DraftPick]] = [
        seven_picks,  # my turn is next -> board should render
        seven_picks,  # unchanged - still my turn, already announced -> no re-render
        seven_picks + [_wp(8, 8, name="Mine")],  # my pick lands
    ]
    board_calls: list[list[DraftPick]] = []

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    def fake_render_full_board(picks: list[DraftPick]) -> str:
        board_calls.append(picks)
        return "BOARD"

    rendered: list[str] = []
    watch_picks(
        "did",
        num_teams=12,
        draft_type="snake",
        my_draft_slot=8,
        total_picks=180,
        render_full_board=fake_render_full_board,
        sleep=lambda seconds: None,
        max_iterations=3,
        render=rendered.append,
        fetch_picks=fake_fetch,
    )

    assert len(board_calls) == 1
    assert rendered.count("BOARD") == 1
    assert "Pick 8 (slot 8): Mine (RB, SF) <== MY PICK" in rendered


def test_watch_picks_stops_when_draft_is_complete() -> None:
    call_log: list[list[DraftPick]] = [
        [_wp(1, 1)],
        [_wp(1, 1), _wp(2, 2)],
    ]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    sleeps: list[float] = []
    watch_picks(
        "did",
        num_teams=2,
        draft_type="snake",
        my_draft_slot=None,
        total_picks=2,
        render_full_board=lambda picks: "BOARD",
        sleep=sleeps.append,
        max_iterations=None,  # would loop forever without the completion check
        render=lambda line: None,
        fetch_picks=fake_fetch,
    )

    assert call_log == []  # exactly 2 fetches happened, then it returned


def test_watch_picks_skips_board_for_non_snake_draft_type() -> None:
    call_log: list[list[DraftPick]] = [[], [_wp(1, 8)]]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    board_calls: list[list[DraftPick]] = []
    rendered: list[str] = []
    watch_picks(
        "did",
        num_teams=12,
        draft_type="linear",
        my_draft_slot=8,
        total_picks=180,
        render_full_board=lambda picks: board_calls.append(picks) or "BOARD",
        sleep=lambda seconds: None,
        max_iterations=2,
        render=rendered.append,
        fetch_picks=fake_fetch,
    )

    assert board_calls == []
    assert len(rendered) == 1  # per-pick line still rendered
    assert "Pick 1 (slot 8): Player (RB, SF)" in rendered[0]


def test_watch_picks_without_my_draft_slot_never_renders_board() -> None:
    call_log: list[list[DraftPick]] = [[], [_wp(1, 1)]]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    board_calls: list[list[DraftPick]] = []
    watch_picks(
        "did",
        num_teams=12,
        draft_type="snake",
        my_draft_slot=None,
        total_picks=180,
        render_full_board=lambda picks: board_calls.append(picks) or "BOARD",
        sleep=lambda seconds: None,
        max_iterations=2,
        render=lambda line: None,
        fetch_picks=fake_fetch,
    )

    assert board_calls == []


def test_watch_picks_ignores_transiently_shorter_response() -> None:
    # Simulate a network blip: fetch 2 picks, then transiently return only 1,
    # then return 3 (2 original + 1 new). The transiently shorter response
    # should not cause a duplicate print or state change.
    two_picks = [_wp(1, 1, name="Alpha"), _wp(2, 2, name="Beta")]
    call_log: list[list[DraftPick]] = [
        two_picks,  # fetch 1: 2 picks
        [two_picks[0]],  # fetch 2: network blip, only 1 pick (should be ignored)
        two_picks + [_wp(3, 3, name="Gamma")],  # fetch 3: back to normal, 3 picks
    ]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    rendered: list[str] = []
    watch_picks(
        "did",
        num_teams=12,
        draft_type="snake",
        my_draft_slot=None,
        total_picks=180,
        render_full_board=lambda picks: "BOARD",
        sleep=lambda seconds: None,
        max_iterations=3,
        render=rendered.append,
        fetch_picks=fake_fetch,
    )

    # Should have exactly 3 picks rendered (Alpha, Beta, Gamma), no duplicates
    assert len(rendered) == 3
    assert rendered[0] == "Pick 1 (slot 1): Alpha (RB, SF)"
    assert rendered[1] == "Pick 2 (slot 2): Beta (RB, SF)"
    assert rendered[2] == "Pick 3 (slot 3): Gamma (RB, SF)"


# Shaped like the real captured fixture tests/fixtures/sleeper/draft_picks.json:
# live picks at pick_no 1/2/3 alongside pre-filled `is_keeper: true` picks at
# pick_no 47/48, all present in the very first response. 4 rounds x 12 teams =
# 48 total picks, so 47/48 are the last two picks of the (even, reversed)
# round 4: slot_for_pick(47, 12) == 2 and slot_for_pick(48, 12) == 1.
def _keeper_league_first_fetch() -> list[DraftPick]:
    # Deliberately NOT in pick_no order — Sleeper makes no ordering promise, and
    # printing must still come out ascending.
    return [
        _wp(47, 2, name="KeeperA", is_keeper=True),
        _wp(2, 2, name="Beta"),
        _wp(48, 1, name="KeeperB", is_keeper=True),
        _wp(1, 1, name="Alpha"),
        _wp(3, 3, name="Gamma"),
    ]


def test_watch_picks_handles_prefilled_keeper_picks() -> None:
    first = _keeper_league_first_fetch()
    fourth = _wp(4, 4, name="Delta")
    call_log: list[list[DraftPick]] = [
        list(first),  # keepers + picks 1-3; next live pick is 4 (mine)
        list(first),  # unchanged poll -> no reprints, no re-render
        [*first, fourth],  # pick 4 lands
    ]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    board_calls: list[list[DraftPick]] = []
    rendered: list[str] = []
    watch_picks(
        "did",
        num_teams=12,
        draft_type="snake",
        my_draft_slot=4,  # slot_for_pick(4, 12) == 4
        total_picks=48,
        render_full_board=lambda picks: board_calls.append(picks) or "BOARD",
        sleep=lambda seconds: None,
        max_iterations=3,
        render=rendered.append,
        fetch_picks=fake_fetch,
    )

    # (a) every pick, keepers included, printed exactly once, in ascending
    # pick_no order regardless of the order the fetch returned them in.
    assert rendered == [
        "Pick 1 (slot 1): Alpha (RB, SF)",
        "Pick 2 (slot 2): Beta (RB, SF)",
        "Pick 3 (slot 3): Gamma (RB, SF)",
        "Pick 47 (slot 2): KeeperA (RB, SF)",
        "Pick 48 (slot 1): KeeperB (RB, SF)",
        # (b)/(c) next live pick is 4 (not 6 = len+1, not 49 = max+1), and 4 is
        # my slot -> board renders exactly here.
        "BOARD",
        "Pick 4 (slot 4): Delta (RB, SF) <== MY PICK",
    ]
    # ...and does not re-render on the unchanged second poll.
    assert len(board_calls) == 1
    # The board sees every pick known so far, keepers included, in pick order —
    # so both keepers are already excluded from "available" while I'm on the
    # clock for pick 4.
    assert [pick.pick_no for pick in board_calls[0]] == [1, 2, 3, 47, 48]


def test_watch_picks_keeper_gap_does_not_shift_turn_detection() -> None:
    # Same 5-pick keeper-league state, but "my" slot is 6 — the slot the old
    # positional `printed_count + 1` logic would have wrongly called next
    # (5 picks seen -> next_pick_no 6). Nothing should render.
    call_log: list[list[DraftPick]] = [_keeper_league_first_fetch()]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    board_calls: list[list[DraftPick]] = []
    watch_picks(
        "did",
        num_teams=12,
        draft_type="snake",
        my_draft_slot=6,
        total_picks=48,
        render_full_board=lambda picks: board_calls.append(picks) or "BOARD",
        sleep=lambda seconds: None,
        max_iterations=1,
        render=lambda line: None,
        fetch_picks=fake_fetch,
    )

    assert board_calls == []


def test_watch_picks_shorter_response_is_a_no_op_for_turn_detection() -> None:
    # A transiently short/partial response can only fail to add picks; it must
    # never drop, re-print, or shift `next_pick_no` back onto an already-made
    # pick. Here fetch 2 returns only pick 1 while picks 1-3 are already known:
    # `next_pick_no` must stay 4 (my slot) and the board must render once, not
    # snap back to 2 (slot 2) and render nothing / render again later.
    three = [_wp(1, 1, name="Alpha"), _wp(2, 2, name="Beta"), _wp(3, 3, name="Gamma")]
    call_log: list[list[DraftPick]] = [
        list(three),
        [three[0]],  # blip: partial response
        list(three),
    ]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    board_calls: list[list[DraftPick]] = []
    rendered: list[str] = []
    watch_picks(
        "did",
        num_teams=12,
        draft_type="snake",
        my_draft_slot=4,
        total_picks=48,
        render_full_board=lambda picks: board_calls.append(picks) or "BOARD",
        sleep=lambda seconds: None,
        max_iterations=3,
        render=rendered.append,
        fetch_picks=fake_fetch,
    )

    assert rendered == [
        "Pick 1 (slot 1): Alpha (RB, SF)",
        "Pick 2 (slot 2): Beta (RB, SF)",
        "Pick 3 (slot 3): Gamma (RB, SF)",
        "BOARD",
    ]
    assert len(board_calls) == 1
    # The board was built from the full accumulated set, not the 1-pick blip —
    # otherwise Beta/Gamma would look available again.
    assert [pick.pick_no for pick in board_calls[0]] == [1, 2, 3]


@pytest.mark.parametrize(
    ("error", "expected_fragment"),
    [
        (requests.ConnectionError("connection reset"), "connection reset"),
        (SleeperHTTPError("https://x/draft/did/picks", 503), "status 503"),
    ],
)
def test_watch_picks_survives_transient_fetch_failure(
    error: Exception, expected_fragment: str
) -> None:
    call_log: list[list[DraftPick] | Exception] = [
        [_wp(1, 1, name="Alpha")],
        error,
        [_wp(1, 1, name="Alpha"), _wp(2, 2, name="Beta")],
    ]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        item = call_log.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    sleeps: list[float] = []
    rendered: list[str] = []
    watch_picks(
        "did",
        num_teams=12,
        draft_type="snake",
        my_draft_slot=None,
        total_picks=48,
        render_full_board=lambda picks: "BOARD",
        poll_seconds=2.5,
        sleep=sleeps.append,
        max_iterations=3,
        render=rendered.append,
        fetch_picks=fake_fetch,
    )

    assert len(rendered) == 3
    assert rendered[0] == "Pick 1 (slot 1): Alpha (RB, SF)"
    assert rendered[1].startswith("fetch failed, retrying: ")
    assert expected_fragment in rendered[1]
    # Recovered cleanly: Alpha is not re-printed, Beta still arrives.
    assert rendered[2] == "Pick 2 (slot 2): Beta (RB, SF)"
    # The failed iteration still waited out the normal poll interval.
    assert sleeps == [2.5, 2.5]


def test_watch_picks_stops_on_completion_with_turn_detection_on() -> None:
    # Draft runs to its last pick while my_draft_slot is set: there is no
    # "next" pick left, so turn detection must simply not fire.
    call_log: list[list[DraftPick]] = [[_wp(1, 1), _wp(2, 2)]]

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return call_log.pop(0)

    board_calls: list[list[DraftPick]] = []
    watch_picks(
        "did",
        num_teams=2,
        draft_type="snake",
        my_draft_slot=1,
        total_picks=2,
        render_full_board=lambda picks: board_calls.append(picks) or "BOARD",
        sleep=lambda seconds: None,
        max_iterations=None,  # would loop forever without the completion check
        render=lambda line: None,
        fetch_picks=fake_fetch,
    )

    assert call_log == []
    assert board_calls == []
