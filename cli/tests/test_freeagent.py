from __future__ import annotations

from sleeper_agent.freeagent.recommend import recommend_free_agents
from sleeper_agent.models.sleeper import Roster
from sleeper_agent.waiver.recommend import PlayerValueRow


def make_roster(player_ids: tuple[str, ...]) -> Roster:
    return Roster(
        roster_id=5,
        owner_id="u1",
        league_id="lid",
        player_ids=player_ids,
        starter_ids=(),
        wins=0,
        losses=0,
        ties=0,
        points_for=0.0,
        waiver_budget_used=0,
    )


def test_recommend_free_agents_finds_upgrade_over_weakest_rostered_player() -> None:
    roster = make_roster(("1", "2"))
    value_by_id = {
        "1": PlayerValueRow(name="Weak RB", position="RB", vorp_season=-10.0),
        "2": PlayerValueRow(name="Good WR", position="WR", vorp_season=50.0),
        "3": PlayerValueRow(name="Free RB", position="RB", vorp_season=5.0),
    }

    recs = recommend_free_agents(roster, value_by_id, {"3"})

    assert len(recs) == 1
    assert recs[0].player_id == "3"
    assert recs[0].upgrade_over_player_id == "1"
    assert recs[0].vorp_delta == 15.0


def test_recommend_free_agents_keeps_the_weakest_among_multiple_same_position_players() -> (
    None
):
    roster = make_roster(("1", "2"))
    value_by_id = {
        "1": PlayerValueRow(name="Weakest RB", position="RB", vorp_season=-10.0),
        "2": PlayerValueRow(name="Stronger RB", position="RB", vorp_season=20.0),
        "3": PlayerValueRow(name="Free RB", position="RB", vorp_season=0.0),
    }

    recs = recommend_free_agents(roster, value_by_id, {"3"})

    assert recs[0].upgrade_over_player_id == "1"


def test_recommend_free_agents_excludes_non_upgrades() -> None:
    roster = make_roster(("1",))
    value_by_id = {
        "1": PlayerValueRow(name="Strong RB", position="RB", vorp_season=100.0),
        "2": PlayerValueRow(name="Weaker Free RB", position="RB", vorp_season=10.0),
    }

    recs = recommend_free_agents(roster, value_by_id, {"2"})

    assert recs == []


def test_recommend_free_agents_ignores_positions_not_on_roster() -> None:
    roster = make_roster(("1",))
    value_by_id = {
        "1": PlayerValueRow(name="Only RB", position="RB", vorp_season=10.0),
        "2": PlayerValueRow(name="Free TE", position="TE", vorp_season=50.0),
    }

    recs = recommend_free_agents(roster, value_by_id, {"2"})

    assert recs == []  # no rostered TE to compare against


def test_recommend_free_agents_ignores_rostered_players_missing_from_value_data() -> (
    None
):
    roster = make_roster(("1", "unranked"))
    value_by_id = {
        "1": PlayerValueRow(name="Weak RB", position="RB", vorp_season=-10.0),
        "2": PlayerValueRow(name="Free RB", position="RB", vorp_season=5.0),
    }

    recs = recommend_free_agents(roster, value_by_id, {"2"})

    assert len(recs) == 1


def test_recommend_free_agents_skips_available_players_missing_from_value_data() -> (
    None
):
    roster = make_roster(("1",))
    value_by_id = {
        "1": PlayerValueRow(name="Weak RB", position="RB", vorp_season=-10.0)
    }

    recs = recommend_free_agents(roster, value_by_id, {"unranked-free-agent"})

    assert recs == []


def test_recommend_free_agents_sorts_by_delta_and_respects_top_n() -> None:
    roster = make_roster(("1",))
    value_by_id = {
        "1": PlayerValueRow(name="Weak RB", position="RB", vorp_season=0.0),
        "2": PlayerValueRow(name="Small Upgrade", position="RB", vorp_season=5.0),
        "3": PlayerValueRow(name="Big Upgrade", position="RB", vorp_season=50.0),
    }

    recs = recommend_free_agents(roster, value_by_id, {"2", "3"}, top_n=1)

    assert len(recs) == 1
    assert recs[0].player_id == "3"
