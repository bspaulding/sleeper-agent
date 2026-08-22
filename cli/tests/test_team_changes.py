from __future__ import annotations

import polars as pl

from sleeper_agent.value.team_changes import (
    MIN_PRIOR_SEASON_TOUCHES,
    TEAM_CODE_ALIASES,
    TeamChange,
    detect_team_changes,
    triage_team_changes,
)

# --- detect_team_changes -----------------------------------------------------


def _weekly_row(
    player_id: str,
    position: str,
    week: int,
    team: str,
    *,
    carries: float = 0.0,
    targets: float = 0.0,
) -> dict[str, object]:
    return {
        "player_id": player_id,
        "position": position,
        "week": week,
        "team": team,
        "carries": carries,
        "targets": targets,
    }


def _ids_df(pairs: list[tuple[str, int | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "gsis_id": [gsis_id for gsis_id, _ in pairs],
            "sleeper_id": [sleeper_id for _, sleeper_id in pairs],
        }
    )


def _players_df(rows: list[tuple[str, str, str | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "player_id": [r[0] for r in rows],
            "name": [f"Name {r[0]}" for r in rows],
            "team": [r[2] for r in rows],
        }
    )


def test_detect_team_changes_flags_a_genuine_cross_team_move() -> None:
    weekly = pl.DataFrame(
        [
            _weekly_row("00-A", "RB", 1, "CAR", carries=10),
            _weekly_row("00-A", "RB", 2, "CAR", carries=10),
        ]
    )
    ids = _ids_df([("00-A", 101)])
    players = _players_df([("101", "RB", "PIT")])

    changes = detect_team_changes(weekly, players, ids)

    assert len(changes) == 1
    assert changes[0] == TeamChange(
        sleeper_id="101",
        name="Name 101",
        position="RB",
        old_team="CAR",
        new_team="PIT",
        total_touches=20,
    )


def test_detect_team_changes_does_not_flag_rams_player_whose_code_only_normalizes() -> (
    None
):
    # nflverse codes the Rams `LA`; Sleeper codes them `LAR` -- a Rams
    # player who never left must not be flagged as a "move".
    weekly = pl.DataFrame([_weekly_row("00-A", "WR", 1, "LA", targets=5)])
    ids = _ids_df([("00-A", 101)])
    players = _players_df([("101", "WR", "LAR")])

    assert detect_team_changes(weekly, players, ids) == []


def test_team_code_aliases_is_exactly_the_la_rams_case() -> None:
    # Confirmed live by diffing every team code on both sides: this is the
    # *only* mismatch across all 32 teams, not a general fuzzy-match problem.
    assert TEAM_CODE_ALIASES == {"LA": "LAR"}


def test_detect_team_changes_does_not_flag_player_who_stayed_on_same_team() -> None:
    weekly = pl.DataFrame([_weekly_row("00-A", "WR", 1, "KC", targets=5)])
    ids = _ids_df([("00-A", 101)])
    players = _players_df([("101", "WR", "KC")])

    assert detect_team_changes(weekly, players, ids) == []


def test_detect_team_changes_uses_the_last_week_as_old_team() -> None:
    # Mid-season trade: the player's most recent team is the relevant "old"
    # team for the diff, not wherever they started the season.
    weekly = pl.DataFrame(
        [
            _weekly_row("00-A", "WR", 1, "MIA", targets=5),
            _weekly_row("00-A", "WR", 2, "MIA", targets=5),
            _weekly_row("00-A", "WR", 3, "NYJ", targets=5),
        ]
    )
    ids = _ids_df([("00-A", 101)])
    players = _players_df([("101", "WR", "DAL")])

    changes = detect_team_changes(weekly, players, ids)

    assert len(changes) == 1
    assert changes[0].old_team == "NYJ"


def test_detect_team_changes_sums_carries_and_targets_across_the_season() -> None:
    weekly = pl.DataFrame(
        [
            _weekly_row("00-A", "RB", 1, "CAR", carries=8, targets=2),
            _weekly_row("00-A", "RB", 2, "CAR", carries=12, targets=3),
        ]
    )
    ids = _ids_df([("00-A", 101)])
    players = _players_df([("101", "RB", "PIT")])

    changes = detect_team_changes(weekly, players, ids)

    assert changes[0].total_touches == 25


def test_detect_team_changes_skips_players_with_no_crosswalk_match() -> None:
    weekly = pl.DataFrame([_weekly_row("00-A", "RB", 1, "CAR", carries=10)])
    ids = _ids_df([("00-OTHER", 999)])
    players = _players_df([("101", "RB", "PIT")])

    assert detect_team_changes(weekly, players, ids) == []


def test_detect_team_changes_skips_crosswalk_rows_with_null_sleeper_id() -> None:
    weekly = pl.DataFrame([_weekly_row("00-A", "RB", 1, "CAR", carries=10)])
    ids = _ids_df([("00-A", None)])
    players = _players_df([("101", "RB", "PIT")])

    assert detect_team_changes(weekly, players, ids) == []


def test_detect_team_changes_skips_sleeper_ids_missing_from_current_players_df() -> (
    None
):
    weekly = pl.DataFrame([_weekly_row("00-A", "RB", 1, "CAR", carries=10)])
    ids = _ids_df([("00-A", 101)])
    players = _players_df([])  # empty players_df -- no current-team record

    assert detect_team_changes(weekly, players, ids) == []


def test_detect_team_changes_skips_players_with_no_current_team_on_record() -> None:
    # Off an NFL roster entirely (team is null/empty) -- can't declare a
    # "move" to nowhere.
    weekly = pl.DataFrame([_weekly_row("00-A", "RB", 1, "CAR", carries=10)])
    ids = _ids_df([("00-A", 101)])
    players = _players_df([("101", "RB", None)])

    assert detect_team_changes(weekly, players, ids) == []


def test_detect_team_changes_ignores_positions_outside_qb_rb_wr_te() -> None:
    weekly = pl.DataFrame([_weekly_row("00-A", "DEF", 1, "CAR")])
    ids = _ids_df([("00-A", 101)])
    players = _players_df([("101", "DEF", "PIT")])

    assert detect_team_changes(weekly, players, ids) == []


# --- triage_team_changes ------------------------------------------------------


def _change(sleeper_id: str, total_touches: int) -> TeamChange:
    return TeamChange(
        sleeper_id=sleeper_id,
        name=f"Name {sleeper_id}",
        position="RB",
        old_team="CAR",
        new_team="PIT",
        total_touches=total_touches,
    )


def test_min_prior_season_touches_is_50() -> None:
    assert MIN_PRIOR_SEASON_TOUCHES == 50


def test_triage_team_changes_excludes_49_touches() -> None:
    changes = [_change("101", 49)]

    assert triage_team_changes(changes) == []


def test_triage_team_changes_includes_50_touches() -> None:
    changes = [_change("101", 50)]

    assert triage_team_changes(changes) == changes


def test_triage_team_changes_respects_custom_threshold() -> None:
    changes = [_change("101", 30)]

    assert triage_team_changes(changes, min_touches=30) == changes
    assert triage_team_changes(changes, min_touches=31) == []
