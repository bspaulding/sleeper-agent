"""Wargame draft-state machine — pure logic for the mock Sleeper server.

Deliberately framework-free: plain dataclasses + functions over a mutable
`DraftState`, so the HTTP shell (`scripts/wargame_server.py`) stays thin and
every transition is unit-testable. Selection validation mirrors what the real
Sleeper UI enforces on a click: on-the-clock check, availability check,
draft-not-complete check.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sleeper_agent.draft_tools.board import slot_for_pick


@dataclass(frozen=True)
class WargamePlayer:
    player_id: str
    name: str
    position: str
    vorp: float


@dataclass(frozen=True)
class DraftConfig:
    league_id: str
    draft_id: str
    num_teams: int = 12
    rounds: int = 15
    # slot number -> roster_id, straight from Sleeper's slot_to_roster_id.
    slot_to_roster_id: Mapping[int, int] = field(default_factory=dict)

    @property
    def total_picks(self) -> int:
        return self.num_teams * self.rounds


@dataclass(frozen=True)
class WargamePick:
    round: int
    pick_no: int
    draft_slot: int
    roster_id: int
    player_id: str
    player_name: str
    position: str
    is_keeper: bool


@dataclass(frozen=True)
class BotPersona:
    """Per-turn scoring multipliers by position; higher = bot reaches harder."""

    name: str
    multipliers: Mapping[str, float]


@dataclass
class DraftState:
    config: DraftConfig
    board: Mapping[str, WargamePlayer]
    personas: Mapping[int, BotPersona] = field(default_factory=dict)
    picks: list[WargamePick] = field(default_factory=list)
    # Set by the server shell when a rule is violated hard enough to void the
    # exercise (e.g. pick-clock expiry). Once set, selections are refused.
    void_reason: str | None = None

    def available_players(self) -> dict[str, WargamePlayer]:
        drafted = {pick.player_id for pick in self.picks}
        return {pid: player for pid, player in self.board.items() if pid not in drafted}

    def next_pick_no(self) -> int | None:
        """Lowest overall pick number not yet taken (keeper-safe)."""
        if len(self.picks) >= self.config.total_picks:
            return None
        taken = {pick.pick_no for pick in self.picks}
        for pick_no in range(1, self.config.total_picks + 1):
            if pick_no not in taken:
                return pick_no
        return None  # pragma: no cover - guarded by the length check above

    def on_clock_roster_id(self) -> int | None:
        pick_no = self.next_pick_no()
        if pick_no is None:
            return None
        slot = slot_for_pick(pick_no, self.config.num_teams)
        return self.config.slot_to_roster_id[slot]

    def make_selection(self, roster_id: int, player_id: str) -> SelectionResult:
        """Apply a human selection with real-UI validation semantics."""
        next_pick_no = self.next_pick_no()
        if next_pick_no is None:
            return DraftComplete()
        if self.void_reason is not None:
            return DraftVoided(reason=self.void_reason)
        on_clock = self.on_clock_roster_id()
        if roster_id != on_clock:
            return NotYourTurn(on_clock_roster_id=on_clock)
        player = self.available_players().get(player_id)
        if player is None:
            return PlayerUnavailable(player_id=player_id)
        pick = self._record(player, keeper=False)
        self._run_bots()
        return SelectionMade(pick=pick, subsequent_bot_picks=self.picks[pick.pick_no :])

    def seed_keepers(
        self, keepers: Sequence[tuple[int, int, str]]
    ) -> list[WargamePick]:
        """Pre-fill keeper picks from (slot, cost_round, player_id) triples.

        Each keeper occupies its owner's own pick within the cost round.
        """
        recorded = []
        for slot, cost_round, player_id in keepers:
            # Owner's position within the cost round (odd rounds ascending,
            # even rounds reversed) -- NOT slot_for_pick, which maps a pick
            # number to a slot; this is the inverse direction.
            pos_in_round = (
                slot if cost_round % 2 == 1 else self.config.num_teams - slot + 1
            )
            pick_no = (cost_round - 1) * self.config.num_teams + pos_in_round
            player = self.board[player_id]
            pick = WargamePick(
                round=cost_round,
                pick_no=pick_no,
                draft_slot=slot,
                roster_id=self.config.slot_to_roster_id[slot],
                player_id=player.player_id,
                player_name=player.name,
                position=player.position,
                is_keeper=True,
            )
            self.picks.append(pick)
            recorded.append(pick)
        self.picks.sort(key=lambda p: p.pick_no)
        return recorded

    def _run_bots(self) -> None:
        """Auto-pick for every bot team until it's a non-bot turn or done."""
        while True:
            pick_no = self.next_pick_no()
            if pick_no is None:
                return
            roster_id = self.on_clock_roster_id()
            assert roster_id is not None  # guarded by next_pick_no() above
            persona = self.personas.get(roster_id)
            if persona is None:
                return
            self._bot_autopick(roster_id, persona)

    def _bot_autopick(self, roster_id: int, persona: BotPersona) -> None:
        available = self.available_players()
        if not available:
            return
        best_id = max(
            available,
            key=lambda pid: (
                available[pid].vorp
                * persona.multipliers.get(available[pid].position, 1.0)
            ),
        )
        self._record(available[best_id], keeper=False)

    def _record(self, player: WargamePlayer, *, keeper: bool) -> WargamePick:
        pick_no = self.next_pick_no()
        assert pick_no is not None
        slot = slot_for_pick(pick_no, self.config.num_teams)
        pick = WargamePick(
            round=(pick_no - 1) // self.config.num_teams + 1,
            pick_no=pick_no,
            draft_slot=slot,
            roster_id=self.config.slot_to_roster_id[slot],
            player_id=player.player_id,
            player_name=player.name,
            position=player.position,
            is_keeper=keeper,
        )
        self.picks.append(pick)
        self.picks.sort(key=lambda p: p.pick_no)
        return pick


@dataclass(frozen=True)
class SelectionMade:
    pick: WargamePick
    subsequent_bot_picks: list[WargamePick]


@dataclass(frozen=True)
class NotYourTurn:
    on_clock_roster_id: int | None


@dataclass(frozen=True)
class PlayerUnavailable:
    player_id: str


@dataclass(frozen=True)
class DraftComplete:
    pass


@dataclass(frozen=True)
class DraftVoided:
    reason: str


SelectionResult = (
    SelectionMade | NotYourTurn | PlayerUnavailable | DraftComplete | DraftVoided
)
