"""Post-draft recap: join draft picks against the big board to produce a
per-team value-delta anchor for `.claude/skills/draft-recap.md`'s grading.

See docs/superpowers/specs/2026-08-27-draft-recap-design.md. This module is
pure data — no IO, no grading, no persona. `commands/draft_cmd.py` does the
fetching; the `draft-recap` skill does the judgment.
"""

from __future__ import annotations

from dataclasses import dataclass

from sleeper_agent.draft_tools.bigboard import BigboardRow
from sleeper_agent.models.sleeper import Draft, DraftPick


class DraftNotCompleteError(Exception):
    def __init__(self, draft_id: str, picks_made: int, picks_expected: int) -> None:
        self.draft_id = draft_id
        self.picks_made = picks_made
        self.picks_expected = picks_expected
        super().__init__(
            f"draft {draft_id} is not complete: {picks_made}/{picks_expected} "
            "picks made -- a recap only makes sense after every pick has landed"
        )


@dataclass(frozen=True)
class PickRecap:
    round: int
    pick_no: int
    player_id: str
    name: str | None
    position: str | None
    is_keeper: bool
    board_rank: int | None
    vorp: float | None
    value_delta: int | None


@dataclass(frozen=True)
class TeamRecap:
    draft_slot: int
    roster_id: int | None
    team_name: str
    picks: tuple[PickRecap, ...]
    mean_value_delta: float | None


def check_draft_complete(draft: Draft, picks: list[DraftPick]) -> None:
    expected = draft.rounds * draft.num_teams
    if len(picks) < expected:
        raise DraftNotCompleteError(draft.draft_id, len(picks), expected)


def _pick_recap(pick: DraftPick, bigboard_by_id: dict[str, BigboardRow]) -> PickRecap:
    row = bigboard_by_id.get(pick.player_id)
    board_rank = row.rank if row is not None else None
    vorp = row.vorp if row is not None else None
    value_delta = pick.pick_no - board_rank if board_rank is not None else None
    return PickRecap(
        round=pick.round,
        pick_no=pick.pick_no,
        player_id=pick.player_id,
        name=pick.player_name,
        position=pick.player_position,
        is_keeper=pick.is_keeper,
        board_rank=board_rank,
        vorp=vorp,
        value_delta=value_delta,
    )


def _mean_value_delta(picks: list[PickRecap]) -> float | None:
    deltas = [p.value_delta for p in picks if p.value_delta is not None]
    if not deltas:
        return None
    return sum(deltas) / len(deltas)


def build_team_recaps(
    picks: list[DraftPick],
    bigboard_rows: list[BigboardRow],
    team_names: dict[int, str],
) -> list[TeamRecap]:
    bigboard_by_id = {row.player_id: row for row in bigboard_rows}
    picks_by_slot: dict[int, list[DraftPick]] = {}
    for pick in picks:
        picks_by_slot.setdefault(pick.draft_slot, []).append(pick)

    teams: list[TeamRecap] = []
    for slot in sorted(picks_by_slot):
        slot_picks = sorted(picks_by_slot[slot], key=lambda p: p.pick_no)
        pick_recaps = [_pick_recap(p, bigboard_by_id) for p in slot_picks]
        teams.append(
            TeamRecap(
                draft_slot=slot,
                roster_id=slot_picks[0].roster_id,
                team_name=team_names.get(slot, f"Slot {slot}"),
                picks=tuple(pick_recaps),
                mean_value_delta=_mean_value_delta(pick_recaps),
            )
        )
    return teams


def recap_to_dict(
    draft: Draft, value_season: str, teams: list[TeamRecap]
) -> dict[str, object]:
    return {
        "draft_id": draft.draft_id,
        "draft_season": draft.season,
        "value_season": value_season,
        "num_teams": draft.num_teams,
        "teams": [
            {
                "draft_slot": team.draft_slot,
                "roster_id": team.roster_id,
                "team_name": team.team_name,
                "mean_value_delta": team.mean_value_delta,
                "picks": [
                    {
                        "round": pick.round,
                        "pick_no": pick.pick_no,
                        "player_id": pick.player_id,
                        "name": pick.name,
                        "position": pick.position,
                        "is_keeper": pick.is_keeper,
                        "board_rank": pick.board_rank,
                        "vorp": pick.vorp,
                        "value_delta": pick.value_delta,
                    }
                    for pick in team.picks
                ],
            }
            for team in teams
        ],
    }


def render_recap_text(teams: list[TeamRecap]) -> str:
    lines: list[str] = []
    for team in teams:
        mean = (
            f"{team.mean_value_delta:+.1f}"
            if team.mean_value_delta is not None
            else "n/a"
        )
        lines.append(
            f"Slot {team.draft_slot} -- {team.team_name}  (mean value Δ={mean})"
        )
        for pick in team.picks:
            rank = (
                f"rank={pick.board_rank}"
                if pick.board_rank is not None
                else "rank=-- (no board data)"
            )
            vorp = f"vorp={pick.vorp:.1f}" if pick.vorp is not None else "vorp=--"
            delta = (
                f"Δ={pick.value_delta:+d}" if pick.value_delta is not None else "Δ=--"
            )
            keeper = "  [KEEPER]" if pick.is_keeper else ""
            name = pick.name or pick.player_id
            position = pick.position or "?"
            lines.append(
                f"  {pick.round}.{pick.pick_no:03d}  {name} ({position})  "
                f"{rank} {vorp} {delta}{keeper}"
            )
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
