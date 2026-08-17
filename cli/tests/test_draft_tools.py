from __future__ import annotations

from pathlib import Path

import polars as pl

from sleeper_agent.draft_tools.board import (
    RosterRequirement,
    board_view,
    compute_tiers,
    my_roster_positions,
    position_tag,
    render_board,
    roster_requirement_from_draft,
    watch_board,
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
from sleeper_agent.storage.parquet_store import write_table

TOTAL_ROUNDS = 15


def make_pick(
    season_round: int,
    *,
    is_keeper: bool = False,
    player_id: str = "1",
    roster_id: int = 5,
    player_name: str = "Test Player",
) -> DraftPick:
    return DraftPick(
        draft_id="did",
        round=season_round,
        pick_no=season_round * 12,
        draft_slot=1,
        roster_id=roster_id,
        player_id=player_id,
        is_keeper=is_keeper,
        picked_by="u1",
        player_name=player_name,
        player_position="RB",
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


def make_vorp_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "sleeper_id": ["1", "2", "3"],
            "name": ["Player One", "Player Two", "Player Three"],
            "position": ["RB", "WR", "QB"],
            "vorp_season": [50.0, 30.0, 10.0],
        }
    )


def test_board_view_excludes_drafted_and_kept_players() -> None:
    vorp_df = make_vorp_df()
    picks = [make_pick(1, player_id="1"), make_pick(2, player_id="2", is_keeper=True)]

    board = board_view(vorp_df, picks)

    assert board["sleeper_id"].to_list() == ["3"]


def test_board_view_respects_top_n() -> None:
    vorp_df = make_vorp_df()

    board = board_view(vorp_df, [], top_n=1)

    assert board["sleeper_id"].to_list() == ["1"]


def test_render_board_formats_ranked_lines() -> None:
    board = make_vorp_df().head(1)

    rendered = render_board(board)

    assert "Best available by value:" in rendered
    assert " 1. Player One" in rendered


def test_watch_board_only_rerenders_when_drafted_ids_change(tmp_path: Path) -> None:
    vorp_df = make_vorp_df()
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
        vorp_df,
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
    vorp_df = make_vorp_df()
    rendered_calls: list[str] = []

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return []

    watch_board(
        "did",
        vorp_df,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=fake_fetch,
    )

    assert len(rendered_calls) == 1


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
        )
    ]

    counts = my_roster_positions(picks, my_roster_id=5)

    assert counts == {"UNK": 1}


def test_my_roster_positions_empty_for_no_picks() -> None:
    assert my_roster_positions([], my_roster_id=5) == {}


# --- compute_tiers -------------------------------------------------------


def test_compute_tiers_increments_only_past_a_big_gap() -> None:
    board = pl.DataFrame(
        {
            "sleeper_id": ["1", "2", "3", "4"],
            "name": ["A", "B", "C", "D"],
            "position": ["RB", "RB", "RB", "RB"],
            # 100 -> 90 is a 10% drop (no break); 90 -> 50 is a ~44% drop (break)
            "vorp_season": [100.0, 90.0, 50.0, 45.0],
        }
    )

    tiers = compute_tiers(board)

    assert tiers == {"1": 1, "2": 1, "3": 2, "4": 2}


def test_compute_tiers_is_independent_per_position() -> None:
    board = pl.DataFrame(
        {
            "sleeper_id": ["1", "2"],
            "name": ["RB One", "WR One"],
            "position": ["RB", "WR"],
            "vorp_season": [100.0, 5.0],
        }
    )

    tiers = compute_tiers(board)

    # Each position's own list has only one player, so both are tier 1
    # regardless of the huge cross-position gap.
    assert tiers == {"1": 1, "2": 1}


def test_compute_tiers_treats_non_positive_vorp_as_always_a_break() -> None:
    board = pl.DataFrame(
        {
            "sleeper_id": ["1", "2", "3"],
            "name": ["A", "B", "C"],
            "position": ["RB", "RB", "RB"],
            "vorp_season": [10.0, 0.0, -5.0],
        }
    )

    tiers = compute_tiers(board)

    assert tiers == {"1": 1, "2": 2, "3": 3}
