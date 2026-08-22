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
    render_roster_summary,
    rookie_watch_rows,
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
from sleeper_agent.draft_tools.rookies import TriagedRookie
from sleeper_agent.models.sleeper import Draft, DraftPick, Player
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.draft import (
    KeeperEligible,
    KeeperEligibleUndraftedDefault,
    KeeperIneligibleCostBelowRoundOne,
    KeeperIneligibleMaxYearsReached,
    keeper_history,
)
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


def test_render_board_without_annotation_is_unchanged() -> None:
    board = make_vorp_df().head(1)

    rendered = render_board(board)

    assert rendered == (
        "Best available by value:\n 1. Player One                RB  vorp=   50.0"
    )


def test_render_board_with_annotation_adds_summary_tags_and_tiers() -> None:
    board = make_vorp_df()  # RB=50.0, WR=30.0, QB=10.0 — one player each
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
    board = make_vorp_df().head(1)
    requirement = RosterRequirement(hard_min={"RB": 2}, flex_capacity=2)

    # my_counts given without requirement (or vice versa) is treated as "no annotation",
    # not a partial one -- avoids ever rendering tags with no requirement to check against.
    rendered = render_board(board, my_counts={"RB": 1}, requirement=None)

    assert "My roster so far" not in rendered
    assert "tier=" not in rendered
    rendered_other_way = render_board(board, my_counts=None, requirement=requirement)
    assert "My roster so far" not in rendered_other_way


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


def test_watch_board_annotates_when_my_roster_id_given(tmp_path: Path) -> None:
    vorp_df = make_vorp_df()
    requirement = RosterRequirement(
        hard_min={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1}, flex_capacity=2
    )
    rendered_calls: list[str] = []

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return [make_pick(1, player_id="99", roster_id=5, player_name="Mine")]

    watch_board(
        "did",
        vorp_df,
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
    vorp_df = make_vorp_df()
    rendered_calls: list[str] = []

    watch_board(
        "did",
        vorp_df,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=lambda draft_id, *, base_url: [],
    )

    assert "My roster so far" not in rendered_calls[0]


def test_watch_board_threads_rookie_watch_through_and_excludes_drafted_ones() -> None:
    vorp_df = make_vorp_df()
    available_rookie = make_rookie(player_id="9001")
    drafted_rookie = make_rookie(player_id="9002", name="Drafted Rookie")
    rendered_calls: list[str] = []

    def fake_fetch(draft_id: str, *, base_url: str) -> list[DraftPick]:
        return [make_pick(1, player_id="9002", player_name="Drafted Rookie")]

    watch_board(
        "did",
        vorp_df,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=fake_fetch,
        triaged_rookies=[available_rookie, drafted_rookie],
    )

    assert "Rookie watch" in rendered_calls[0]
    assert "Rookie One" in rendered_calls[0]
    assert "Drafted Rookie" not in rendered_calls[0]


def test_watch_board_without_triaged_rookies_omits_rookie_watch() -> None:
    vorp_df = make_vorp_df()
    rendered_calls: list[str] = []

    watch_board(
        "did",
        vorp_df,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=lambda draft_id, *, base_url: [],
    )

    assert "Rookie watch" not in rendered_calls[0]


def test_watch_board_threads_team_changes_through_to_render_board() -> None:
    vorp_df = make_vorp_df()  # sleeper_id "1" is RB/50.0
    rendered_calls: list[str] = []

    watch_board(
        "did",
        vorp_df,
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
    vorp_df = make_vorp_df()
    rendered_calls: list[str] = []

    watch_board(
        "did",
        vorp_df,
        sleep=lambda _seconds: None,
        max_iterations=1,
        render=rendered_calls.append,
        fetch_picks=lambda draft_id, *, base_url: [],
    )

    assert "[MOVED" not in rendered_calls[0]


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


# --- rookie watch -----------------------------------------------------------


def make_rookie(
    player_id: str = "9001",
    name: str = "Rookie One",
    position: str = "WR",
    draft_round: int = 1,
) -> TriagedRookie:
    return TriagedRookie(
        player=Player(
            player_id=player_id,
            name=name,
            position=position,
            team="KC",
            status="Active",
            injury_status=None,
            fantasy_positions=(position,),
            years_exp=0,
        ),
        draft_round=draft_round,
    )


def test_rookie_watch_rows_excludes_already_drafted_triaged_rookies() -> None:
    available = make_rookie(player_id="1")
    drafted = make_rookie(player_id="2")
    picks = [make_pick(1, player_id="2", player_name="Drafted Rookie")]

    rows = rookie_watch_rows([available, drafted], picks)

    assert [row.player.player_id for row in rows] == ["1"]


def test_rookie_watch_rows_attaches_news_excerpt_by_sleeper_id() -> None:
    rookie = make_rookie(player_id="1")

    rows = rookie_watch_rows(
        [rookie], [], news_by_sleeper_id={"1": ["- broke out in camp"]}
    )

    assert rows[0].news_excerpt == ("- broke out in camp",)


def test_rookie_watch_rows_empty_news_when_no_lookup_given() -> None:
    rookie = make_rookie(player_id="1")

    rows = rookie_watch_rows([rookie], [])

    assert rows[0].news_excerpt == ()


def test_render_board_rookie_watch_section_present_only_when_supplied() -> None:
    board = make_vorp_df().head(1)

    without = render_board(board)
    assert "Rookie watch" not in without

    rows = rookie_watch_rows([make_rookie()], [])
    with_watch = render_board(board, rookie_watch=rows)
    assert "Rookie watch" in with_watch
    assert "Rookie One" in with_watch


def test_render_board_rookie_watch_section_omitted_for_empty_list() -> None:
    board = make_vorp_df().head(1)

    rendered = render_board(board, rookie_watch=[])

    assert "Rookie watch" not in rendered


def test_render_board_rookie_watch_rows_have_no_vorp_or_tier_fields() -> None:
    board = make_vorp_df().head(1)
    rows = rookie_watch_rows([make_rookie(draft_round=2)], [])

    rendered = render_board(board, rookie_watch=rows)

    watch_section = rendered.split("Rookie watch")[1]
    assert "vorp=" not in watch_section
    assert "tier=" not in watch_section
    assert "R2" in watch_section


def test_render_board_rookie_watch_includes_news_excerpt_when_present() -> None:
    board = make_vorp_df().head(1)
    rows = rookie_watch_rows(
        [make_rookie()], [], news_by_sleeper_id={"9001": ["- fast start in camp"]}
    )

    rendered = render_board(board, rookie_watch=rows)

    assert "- fast start in camp" in rendered


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
    board = make_vorp_df().head(1)

    rendered = render_board(board)

    assert rendered == (
        "Best available by value:\n 1. Player One                RB  vorp=   50.0"
    )


def test_render_board_tags_only_the_matching_player() -> None:
    board = make_vorp_df()  # sleeper_id 1, 2, 3
    team_changes = {"1": make_team_change(sleeper_id="1")}

    rendered = render_board(board, team_changes=team_changes)

    lines = rendered.splitlines()
    assert "[MOVED: CAR" in lines[1]
    assert "PIT]" in lines[1]
    assert "[MOVED" not in lines[2]
    assert "[MOVED" not in lines[3]


def test_render_board_moved_tag_does_not_change_sort_order_or_vorp_values() -> None:
    board = make_vorp_df()
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
    board = make_vorp_df()
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
    board = make_vorp_df().head(1)

    rendered = render_board(board)

    assert "[MOVED" not in rendered


# --- watch_picks -------------------------------------------------------


def _wp(
    pick_no: int, draft_slot: int, *, name: str = "Player", position: str = "RB"
) -> DraftPick:
    return DraftPick(
        draft_id="did",
        round=1,
        pick_no=pick_no,
        draft_slot=draft_slot,
        roster_id=draft_slot,
        player_id=str(pick_no),
        is_keeper=False,
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
    watch_picks(
        "did",
        num_teams=12,
        draft_type="linear",
        my_draft_slot=8,
        total_picks=180,
        render_full_board=lambda picks: board_calls.append(picks) or "BOARD",
        sleep=lambda seconds: None,
        max_iterations=2,
        render=lambda line: None,
        fetch_picks=fake_fetch,
    )

    assert board_calls == []


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
