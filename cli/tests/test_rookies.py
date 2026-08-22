from __future__ import annotations

import polars as pl

from sleeper_agent.draft_tools.rookies import (
    TRIAGE_CUTOFFS,
    TriagedRookie,
    crosswalk_draft_picks_to_sleeper_ids,
    triage_rookies,
)

# --- crosswalk_draft_picks_to_sleeper_ids ----------------------------------


def test_crosswalk_joins_on_normalized_name_and_position_not_gsis_id() -> None:
    # `draft_picks`'s own `gsis_id` is a PFR-derived scheme for this year's
    # class (e.g. "MEN516487"), not a real nflverse GSIS id — confirmed live
    # against the 2026 draft class. The join must go through (name,
    # position) against `ff_playerids` instead, or it silently matches
    # nothing.
    draft_picks = pl.DataFrame(
        {
            "season": [2026, 2026],
            "round": [1, 1],
            "pick": [1, 3],
            "position": ["QB", "RB"],
            "pfr_player_name": ["Fernando Mendoza", "Jeremiyah Love"],
            "gsis_id": ["MEN516487", "LOV121782"],
        }
    )
    ff_playerids = pl.DataFrame(
        {
            "name": ["Fernando Mendoza", "Jeremiyah Love", "Someone Else"],
            "position": ["QB", "RB", "WR"],
            "gsis_id": ["00-0041562", "00-0041570", None],
            "sleeper_id": [13269, 13287, 99999],
            "draft_year": [2026, 2026, 2025],
        }
    )

    joined = crosswalk_draft_picks_to_sleeper_ids(
        draft_picks, ff_playerids, season=2026
    )

    by_name = {row["pfr_player_name"]: row["sleeper_id"] for row in joined.to_dicts()}
    assert by_name["Fernando Mendoza"] == "13269"
    assert by_name["Jeremiyah Love"] == "13287"


def test_crosswalk_leaves_sleeper_id_null_for_unmatched_pick() -> None:
    draft_picks = pl.DataFrame(
        {
            "season": [2026],
            "round": [7],
            "pick": [250],
            "position": ["LS"],
            "pfr_player_name": ["Deep Snapper"],
            "gsis_id": ["ABC000000"],
        }
    )
    ff_playerids = pl.DataFrame(
        {
            "name": ["Someone Else"],
            "position": ["WR"],
            "gsis_id": ["00-1"],
            "sleeper_id": [1],
            "draft_year": [2026],
        }
    )

    joined = crosswalk_draft_picks_to_sleeper_ids(
        draft_picks, ff_playerids, season=2026
    )

    assert joined["sleeper_id"].to_list() == [None]


def test_crosswalk_filters_ff_playerids_to_the_requested_draft_year() -> None:
    # Same name/position but a different draft class shouldn't match — the
    # (name, position) join is only safe once scoped to one draft year.
    draft_picks = pl.DataFrame(
        {
            "season": [2026],
            "round": [1],
            "pick": [1],
            "position": ["WR"],
            "pfr_player_name": ["Same Name"],
            "gsis_id": ["X"],
        }
    )
    ff_playerids = pl.DataFrame(
        {
            "name": ["Same Name"],
            "position": ["WR"],
            "gsis_id": ["00-9999999"],
            "sleeper_id": [55555],
            "draft_year": [2019],
        }
    )

    joined = crosswalk_draft_picks_to_sleeper_ids(
        draft_picks, ff_playerids, season=2026
    )

    assert joined["sleeper_id"].to_list() == [None]


def test_crosswalk_filters_draft_picks_to_the_requested_season() -> None:
    draft_picks = pl.DataFrame(
        {
            "season": [2025, 2026],
            "round": [1, 1],
            "pick": [1, 1],
            "position": ["QB", "QB"],
            "pfr_player_name": ["Old Class Guy", "New Class Guy"],
            "gsis_id": ["A", "B"],
        }
    )
    ff_playerids = pl.DataFrame(
        {
            "name": ["Old Class Guy", "New Class Guy"],
            "position": ["QB", "QB"],
            "gsis_id": ["00-1", "00-2"],
            "sleeper_id": [1, 2],
            "draft_year": [2025, 2026],
        }
    )

    joined = crosswalk_draft_picks_to_sleeper_ids(
        draft_picks, ff_playerids, season=2026
    )

    assert joined["pfr_player_name"].to_list() == ["New Class Guy"]


# --- triage_rookies ---------------------------------------------------------


def _pick(
    round_: int,
    position: str,
    *,
    pick: int,
    sleeper_id: str | None,
) -> dict[str, object]:
    return {
        "season": 2026,
        "round": round_,
        "pick": pick,
        "position": position,
        "pfr_player_name": f"Player {pick}",
        "gsis_id": f"X{pick}",
        "sleeper_id": sleeper_id,
    }


def _players_df(sleeper_ids: list[str], positions: list[str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "player_id": sleeper_ids,
            "name": [f"Name {sid}" for sid in sleeper_ids],
            "position": positions,
            "team": ["KC"] * len(sleeper_ids),
            "status": ["Active"] * len(sleeper_ids),
            "injury_status": [""] * len(sleeper_ids),
            "fantasy_positions": [[p] for p in positions],
            "years_exp": [0] * len(sleeper_ids),
        }
    )


def test_triage_cutoffs_match_rookie_evaluation_wiki_table() -> None:
    assert TRIAGE_CUTOFFS == {"TE": 1, "QB": 1, "WR": 2, "RB": 3}


def test_triage_rookies_keeps_te_round_1_excludes_round_2() -> None:
    draft_picks = pl.DataFrame(
        [
            _pick(1, "TE", pick=1, sleeper_id="1"),
            _pick(2, "TE", pick=2, sleeper_id="2"),
        ]
    )
    players_df = _players_df(["1", "2"], ["TE", "TE"])

    rookies = triage_rookies(draft_picks, players_df)

    assert [r.player.player_id for r in rookies] == ["1"]


def test_triage_rookies_keeps_qb_round_1_excludes_round_2() -> None:
    draft_picks = pl.DataFrame(
        [
            _pick(1, "QB", pick=1, sleeper_id="1"),
            _pick(2, "QB", pick=2, sleeper_id="2"),
        ]
    )
    players_df = _players_df(["1", "2"], ["QB", "QB"])

    rookies = triage_rookies(draft_picks, players_df)

    assert [r.player.player_id for r in rookies] == ["1"]


def test_triage_rookies_keeps_wr_round_2_excludes_round_3() -> None:
    draft_picks = pl.DataFrame(
        [
            _pick(2, "WR", pick=1, sleeper_id="1"),
            _pick(3, "WR", pick=2, sleeper_id="2"),
        ]
    )
    players_df = _players_df(["1", "2"], ["WR", "WR"])

    rookies = triage_rookies(draft_picks, players_df)

    assert [r.player.player_id for r in rookies] == ["1"]


def test_triage_rookies_keeps_rb_round_3_excludes_round_4() -> None:
    draft_picks = pl.DataFrame(
        [
            _pick(3, "RB", pick=1, sleeper_id="1"),
            _pick(4, "RB", pick=2, sleeper_id="2"),
        ]
    )
    players_df = _players_df(["1", "2"], ["RB", "RB"])

    rookies = triage_rookies(draft_picks, players_df)

    assert [r.player.player_id for r in rookies] == ["1"]


def test_triage_rookies_skips_positions_with_no_cutoff() -> None:
    draft_picks = pl.DataFrame([_pick(1, "LS", pick=1, sleeper_id="1")])
    players_df = _players_df(["1"], ["LS"])

    assert triage_rookies(draft_picks, players_df) == []


def test_triage_rookies_skips_picks_with_no_sleeper_id_match() -> None:
    # A crosswalk miss (null sleeper_id) is skipped, not errored on.
    draft_picks = pl.DataFrame([_pick(1, "TE", pick=1, sleeper_id=None)])
    players_df = _players_df([], [])

    assert triage_rookies(draft_picks, players_df) == []


def test_triage_rookies_skips_sleeper_id_with_no_matching_player_row() -> None:
    # sleeper_id resolved by the crosswalk, but not present in
    # data/sleeper/players.parquet (e.g. a stale player dictionary) —
    # skipped rather than raising.
    draft_picks = pl.DataFrame([_pick(1, "TE", pick=1, sleeper_id="1")])
    players_df = _players_df([], [])

    assert triage_rookies(draft_picks, players_df) == []


def test_triage_rookies_returns_full_player_and_draft_round() -> None:
    draft_picks = pl.DataFrame([_pick(1, "TE", pick=5, sleeper_id="1")])
    players_df = _players_df(["1"], ["TE"])

    rookies = triage_rookies(draft_picks, players_df)

    assert rookies == [
        TriagedRookie(
            player=rookies[0].player,
            draft_round=1,
        )
    ]
    assert rookies[0].player.name == "Name 1"
    assert rookies[0].player.position == "TE"
    assert rookies[0].player.team == "KC"


def test_triage_rookies_sorted_by_overall_pick() -> None:
    draft_picks = pl.DataFrame(
        [
            _pick(1, "TE", pick=20, sleeper_id="2"),
            _pick(1, "QB", pick=1, sleeper_id="1"),
        ]
    )
    players_df = _players_df(["1", "2"], ["QB", "TE"])

    rookies = triage_rookies(draft_picks, players_df)

    assert [r.player.player_id for r in rookies] == ["1", "2"]
