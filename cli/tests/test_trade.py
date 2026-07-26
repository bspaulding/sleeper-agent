from __future__ import annotations

import pytest

from sleeper_agent.models.sleeper import Roster
from sleeper_agent.trade.evaluate import (
    MalformedAssetError,
    PickAsset,
    PlayerAsset,
    default_pick_value,
    evaluate_trade,
    parse_asset,
    parse_offer,
)
from sleeper_agent.trade.propose import position_average_vorp, propose_trades
from sleeper_agent.waiver.recommend import PlayerValueRow


def make_roster(player_ids: tuple[str, ...], roster_id: int = 5) -> Roster:
    return Roster(
        roster_id=roster_id,
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


# --- offer parsing ---------------------------------------------------------


def test_parse_asset_parses_player_id() -> None:
    assert parse_asset("1234") == PlayerAsset(player_id="1234")


def test_parse_asset_parses_pick_reference() -> None:
    assert parse_asset("2026-R2") == PickAsset(season="2026", round=2)


def test_parse_asset_strips_whitespace() -> None:
    assert parse_asset("  1234  ") == PlayerAsset(player_id="1234")


def test_parse_asset_rejects_malformed_token() -> None:
    with pytest.raises(MalformedAssetError):
        parse_asset("not-a-real-asset")


def test_parse_offer_splits_on_commas() -> None:
    assets = parse_offer("1234, 2026-R2, 5678")

    assert assets == [
        PlayerAsset(player_id="1234"),
        PickAsset(season="2026", round=2),
        PlayerAsset(player_id="5678"),
    ]


def test_parse_offer_returns_empty_list_for_blank_string() -> None:
    assert parse_offer("") == []
    assert parse_offer("   ") == []


# --- pick value + trade evaluation -----------------------------------------


def test_default_pick_value_decreases_by_round() -> None:
    assert default_pick_value(1) > default_pick_value(2) > default_pick_value(8)
    assert default_pick_value(1) == 100.0


def test_evaluate_trade_computes_value_delta_and_position_totals() -> None:
    value_by_id = {
        "1": PlayerValueRow(name="Give Guy", position="RB", vorp_season=20.0),
        "2": PlayerValueRow(name="Get Guy", position="WR", vorp_season=35.0),
    }

    evaluation = evaluate_trade(
        [PlayerAsset(player_id="1")],
        [PlayerAsset(player_id="2")],
        value_by_id,
    )

    assert evaluation.give_value == 20.0
    assert evaluation.get_value == 35.0
    assert evaluation.value_delta == 15.0
    assert evaluation.give_position_totals == {"RB": 20.0}
    assert evaluation.get_position_totals == {"WR": 35.0}


def test_evaluate_trade_includes_picks_via_pick_value_fn() -> None:
    evaluation = evaluate_trade(
        [PickAsset(season="2026", round=1)],
        [PickAsset(season="2026", round=8)],
        {},
    )

    assert evaluation.give_position_totals == {"PICK": default_pick_value(1)}
    assert evaluation.get_position_totals == {"PICK": default_pick_value(8)}
    assert evaluation.value_delta < 0  # a round-1 pick is worth more than round-8


def test_evaluate_trade_treats_unranked_player_as_zero_value() -> None:
    evaluation = evaluate_trade([PlayerAsset(player_id="unranked")], [], {})

    assert evaluation.give_value == 0.0
    assert evaluation.give_position_totals == {"?": 0.0}


def test_evaluate_trade_sums_multiple_assets_at_same_position() -> None:
    value_by_id = {
        "1": PlayerValueRow(name="RB One", position="RB", vorp_season=10.0),
        "2": PlayerValueRow(name="RB Two", position="RB", vorp_season=15.0),
    }

    evaluation = evaluate_trade(
        [PlayerAsset(player_id="1"), PlayerAsset(player_id="2")], [], value_by_id
    )

    assert evaluation.give_position_totals == {"RB": 25.0}


# --- trade proposals ---------------------------------------------------


def test_position_average_vorp_averages_by_position() -> None:
    roster = make_roster(("1", "2", "3"))
    value_by_id = {
        "1": PlayerValueRow(name="A", position="RB", vorp_season=10.0),
        "2": PlayerValueRow(name="B", position="RB", vorp_season=20.0),
        "3": PlayerValueRow(name="C", position="WR", vorp_season=5.0),
    }

    averages = position_average_vorp(roster, value_by_id)

    assert averages == {"RB": 15.0, "WR": 5.0}


def test_position_average_vorp_skips_unranked_players() -> None:
    roster = make_roster(("1", "unranked"))
    value_by_id = {"1": PlayerValueRow(name="A", position="RB", vorp_season=10.0)}

    assert position_average_vorp(roster, value_by_id) == {"RB": 10.0}


def test_propose_trades_finds_value_balanced_swaps_within_tolerance() -> None:
    our_roster = make_roster(("1",), roster_id=5)
    their_roster = make_roster(("2",), roster_id=6)
    value_by_id = {
        "1": PlayerValueRow(name="Our RB", position="RB", vorp_season=50.0),
        "2": PlayerValueRow(name="Their WR", position="WR", vorp_season=51.0),
    }

    proposals = propose_trades(our_roster, their_roster, value_by_id)

    assert len(proposals) == 1
    assert proposals[0].give_player_id == "1"
    assert proposals[0].get_player_id == "2"


def test_propose_trades_excludes_swaps_outside_tolerance() -> None:
    our_roster = make_roster(("1",), roster_id=5)
    their_roster = make_roster(("2",), roster_id=6)
    value_by_id = {
        "1": PlayerValueRow(name="Our RB", position="RB", vorp_season=10.0),
        "2": PlayerValueRow(name="Their WR", position="WR", vorp_season=100.0),
    }

    proposals = propose_trades(our_roster, their_roster, value_by_id)

    assert proposals == []


def test_propose_trades_prefers_need_filling_packages() -> None:
    our_roster = make_roster(("1", "2"), roster_id=5)
    their_roster = make_roster(("3", "4"), roster_id=6)
    value_by_id = {
        # We're stacked at RB (both our players are RB), weak at WR (none rostered).
        "1": PlayerValueRow(name="Our RB One", position="RB", vorp_season=50.0),
        "2": PlayerValueRow(name="Our RB Two", position="RB", vorp_season=48.0),
        "3": PlayerValueRow(name="Their WR", position="WR", vorp_season=50.0),
        "4": PlayerValueRow(name="Their RB", position="RB", vorp_season=49.0),
    }

    proposals = propose_trades(our_roster, their_roster, value_by_id, top_n=10)

    # Getting the WR (a position we have zero rostered depth at) should rank
    # above a same-position RB-for-RB swap of similar value.
    wr_proposal = next(p for p in proposals if p.get_position == "WR")
    rb_proposal = next(p for p in proposals if p.get_position == "RB")
    assert proposals[0] == wr_proposal
    assert wr_proposal.plausibility_score > rb_proposal.plausibility_score


def test_propose_trades_respects_top_n() -> None:
    our_roster = make_roster(tuple(str(i) for i in range(5)), roster_id=5)
    their_roster = make_roster(tuple(str(i) for i in range(5, 10)), roster_id=6)
    value_by_id = {
        str(i): PlayerValueRow(name=f"P{i}", position="RB", vorp_season=50.0)
        for i in range(10)
    }

    proposals = propose_trades(our_roster, their_roster, value_by_id, top_n=3)

    assert len(proposals) == 3
