# Draft Recap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `sleeper-agent draft recap` (picks x big-board join producing a per-team value
anchor) and the `.claude/skills/draft-recap.md` skill that turns it into a tongue-in-cheek,
graded HTML report card, then run it for real against the latest logged mock draft and commit
the result.

**Architecture:** A pure data module (`draft_tools/recap.py`) joins already-fetched `DraftPick`s
against big-board rows and produces per-team `TeamRecap`/`PickRecap` dataclasses plus a
deterministic `mean_value_delta` anchor — no IO, no judgment. A thin command
(`commands/draft_cmd.py::cmd_draft_recap`) does the HTTP/file IO (fetch draft, picks, optionally
rosters/users; load the big board) and renders JSON or plain text. A new skill file
(`.claude/skills/draft-recap.md`) consumes that JSON to write the actual grades, trophies, and
HTML — content no code in this plan touches or tests.

**Tech Stack:** Python 3.11, existing `sleeper_agent` CLI (argparse, polars, `uv`/`ruff`/`ty`),
pytest with the repo's real-local-HTTP-server test harness (`tests/support/mock_http.py`) — no
mocking library, per `PROJECT_PLAN.md` §10.1's no-dynamic-magic CI gate.

**Spec:** `docs/superpowers/specs/2026-08-27-draft-recap-design.md`

## Global Constraints

- **No `unittest.mock`/`monkeypatch`/bare `setattr`/`getattr`** anywhere in `cli/` — CI greps for
  these (`PROJECT_PLAN.md` §10.1). Test HTTP-calling code against a real local server
  (`tests/support/mock_http.py::mock_http_server`), exactly like every existing `cmd_draft_*`
  test in `cli/tests/test_commands.py`.
- **100% branch+function coverage enforced in CI** (`pytest --cov-fail-under=100`) for everything
  under `cli/src/sleeper_agent/` — every new branch needs a test hitting it. The skill's
  LLM-authored prose/HTML is explicitly out of that gate (not code).
- **Full typing, `ty check` clean, `ruff check`/`ruff format --check` clean, default rule sets
  unmodified.**
- **Prefer plain functions and frozen dataclasses over classes** (`PROJECT_PLAN.md` §10.2) —
  matches every existing module in `draft_tools/`.
- **CLI computes the deterministic data; the skill supplies the judgment.** No grading logic,
  persona text, letter grades, or trophy categories belong anywhere in `cli/` — see spec
  Motivation section. Task 1/2 build data only.

---

## Task 1: `draft_tools/recap.py` — the picks x big-board join

**Files:**
- Create: `cli/src/sleeper_agent/draft_tools/recap.py`
- Test: `cli/tests/test_draft_recap.py`

**Interfaces:**
- Consumes: `sleeper_agent.draft_tools.bigboard.BigboardRow` (existing —
  `rank: int`, `player_id: str`, `vorp: float | None`), `sleeper_agent.models.sleeper.Draft`
  (existing — `draft_id: str`, `season: str`, `rounds: int`, `num_teams: int`),
  `sleeper_agent.models.sleeper.DraftPick` (existing — `round: int`, `pick_no: int`,
  `draft_slot: int`, `roster_id: int | None`, `player_id: str`, `is_keeper: bool`,
  `player_name: str | None`, `player_position: str | None`).
- Produces (used by Task 2): `PickRecap`, `TeamRecap` dataclasses; `DraftNotCompleteError`;
  `check_draft_complete(draft: Draft, picks: list[DraftPick]) -> None`;
  `build_team_recaps(picks: list[DraftPick], bigboard_rows: list[BigboardRow], team_names:
  dict[int, str]) -> list[TeamRecap]`; `recap_to_dict(draft: Draft, value_season: str, teams:
  list[TeamRecap]) -> dict[str, object]`; `render_recap_text(teams: list[TeamRecap]) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `cli/tests/test_draft_recap.py`:

```python
from __future__ import annotations

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
    source: str = "vorp",
) -> BigboardRow:
    return BigboardRow(
        rank=rank,
        player_id=player_id,
        name=f"Player {player_id}",
        position=position,
        source=source,  # type: ignore[arg-type]
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_draft_recap.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sleeper_agent.draft_tools.recap'`

- [ ] **Step 3: Write the implementation**

Create `cli/src/sleeper_agent/draft_tools/recap.py`:

```python
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
        lines.append(f"Slot {team.draft_slot} -- {team.team_name}  (mean value Δ={mean})")
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_draft_recap.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Verify coverage, lint, and types clean**

Run:
```bash
cd cli
uv run pytest tests/test_draft_recap.py --cov=sleeper_agent.draft_tools.recap --cov-report=term-missing --cov-fail-under=100
uv run ruff check src/sleeper_agent/draft_tools/recap.py tests/test_draft_recap.py
uv run ruff format --check src/sleeper_agent/draft_tools/recap.py tests/test_draft_recap.py
uv run ty check
```
Expected: 100% coverage on `recap.py`, no ruff/ty findings.

- [ ] **Step 6: Commit and push**

```bash
git add cli/src/sleeper_agent/draft_tools/recap.py cli/tests/test_draft_recap.py
git commit -m "Add draft-recap data join (picks x bigboard value-delta anchor)"
git push
```

---

## Task 2: `draft recap` CLI command

**Files:**
- Modify: `cli/src/sleeper_agent/commands/draft_cmd.py`
- Modify (test helper, backward-compatible addition): `cli/tests/test_commands.py`

**Interfaces:**
- Consumes: Task 1's `draft_tools.recap` module (`check_draft_complete`, `DraftNotCompleteError`,
  `build_team_recaps`, `recap_to_dict`, `render_recap_text`); existing
  `sleeper_client.draft.fetch_draft`/`fetch_draft_picks`; existing
  `sleeper_client.league.fetch_rosters`/`fetch_users`; existing
  `draft_tools.bigboard.load_bigboard` + its three error classes.
- Produces: `cmd_draft_recap(args, *, repo_root=None, base_url=SLEEPER_BASE_URL, today=date.today)
  -> int`, wired to `sleeper-agent draft recap`.

- [ ] **Step 1: Add imports**

In `cli/src/sleeper_agent/commands/draft_cmd.py`, add `import json` near the top (after
`import argparse`), and extend two existing import blocks:

```python
import argparse
import json
import sys
```

Change:
```python
from sleeper_agent.sleeper_client.league import fetch_league
```
to:
```python
from sleeper_agent.sleeper_client.league import fetch_league, fetch_rosters, fetch_users
```

Add a new import block (alphabetically near the `draft_tools.keepers` import):
```python
from sleeper_agent.draft_tools.recap import (
    DraftNotCompleteError,
    build_team_recaps,
    check_draft_complete,
    recap_to_dict,
    render_recap_text,
)
```

- [ ] **Step 2: Add the `recap` subparser**

In `add_subcommands`, after the existing `board_parser.set_defaults(func=cmd_draft_board)` line,
add:

```python
    recap_parser = draft_subparsers.add_parser(
        "recap", help="Post-draft recap data: picks joined against the big board"
    )
    recap_parser.add_argument("--draft-id", required=True)
    recap_parser.add_argument("--value-season", default=None)
    recap_parser.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable output for the draft-recap skill. Default is a "
        "human-readable per-team table.",
    )
    recap_parser.set_defaults(func=cmd_draft_recap)
```

- [ ] **Step 3: Write `cmd_draft_recap`**

Add this function after `cmd_draft_keepers` and before `cmd_draft_board` (near the other
`cmd_draft_*` functions):

```python
def _team_names_by_slot(draft: Draft, *, base_url: str) -> dict[int, str]:
    """Real team names for a league draft (`draft.league_id` non-empty);
    empty dict for a mock draft, where `build_team_recaps` falls back to
    `"Slot N"` labels on its own.
    """
    if not draft.league_id:
        return {}
    rosters = fetch_rosters(draft.league_id, base_url=base_url)
    users = fetch_users(draft.league_id, base_url=base_url)
    user_by_id = {user.user_id: user for user in users}
    owner_by_roster_id = {roster.roster_id: roster.owner_id for roster in rosters}
    names: dict[int, str] = {}
    for slot, roster_id in draft.slot_to_roster_id.items():
        owner_id = owner_by_roster_id.get(roster_id)
        user = user_by_id.get(owner_id) if owner_id is not None else None
        if user is not None:
            names[slot] = user.team_name or user.display_name
    return names


def cmd_draft_recap(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
    today: Callable[[], date] = date.today,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    if args.value_season is None:
        value_season = str(today().year - 1)
        print(
            f"--value-season not given; defaulting to {value_season} "
            "(current year minus 1, the most recently completed season pre-season)"
        )
    else:
        value_season = args.value_season

    draft = fetch_draft(args.draft_id, base_url=base_url)
    picks = fetch_draft_picks(args.draft_id, base_url=base_url)
    try:
        check_draft_complete(draft, picks)
    except DraftNotCompleteError as exc:
        print(str(exc))
        return 1

    try:
        bigboard_rows = load_bigboard(root, value_season)
    except (
        BigboardNotBuiltError,
        BigboardUnresolvedRowError,
        BigboardMalformedError,
    ) as exc:
        print(str(exc))
        return 1

    team_names = _team_names_by_slot(draft, base_url=base_url)
    teams = build_team_recaps(picks, bigboard_rows, team_names)

    if args.json:
        print(json.dumps(recap_to_dict(draft, value_season, teams)))
    else:
        print(render_recap_text(teams))
    return 0
```

- [ ] **Step 4: Extend the shared `_draft_object_payload` test helper (backward-compatible)**

In `cli/tests/test_commands.py`, find `_draft_object_payload` (used by the existing
`cmd_draft_board` tests) and add an optional `league_id` parameter, defaulting to `""` so every
existing call site is unaffected:

```python
def _draft_object_payload(
    draft_id: str = "did1",
    slot_to_roster_id: dict[str, int] | None = None,
    *,
    rounds: int = 15,
    teams: int = 12,
    league_id: str = "",
) -> dict[str, object]:
    return {
        "draft_id": draft_id,
        "type": "snake",
        "league_id": league_id,
        "settings": {
            "rounds": rounds,
            "teams": teams,
            "slots_qb": 1,
            "slots_rb": 2,
            "slots_wr": 2,
            "slots_te": 1,
            "slots_flex": 2,
            "slots_def": 1,
        },
        "slot_to_roster_id": slot_to_roster_id or {"1": 5},
    }
```

- [ ] **Step 5: Write the failing command-level tests**

Append to `cli/tests/test_commands.py` (near the other `cmd_draft_board` tests):

```python
def _rosters_payload() -> list[dict[str, object]]:
    return [
        {
            "roster_id": 5,
            "owner_id": "u5",
            "league_id": "lid1",
            "players": [],
            "starters": [],
            "settings": {},
        },
        {
            "roster_id": 6,
            "owner_id": "u6",
            "league_id": "lid1",
            "players": [],
            "starters": [],
            "settings": {},
        },
    ]


def _users_payload() -> list[dict[str, object]]:
    return [
        {
            "user_id": "u5",
            "display_name": "brad",
            "metadata": {"team_name": "Only Gold's Finest"},
        },
        {"user_id": "u6", "display_name": "aaron", "metadata": {}},
    ]


def _recap_pick_payload(
    *,
    round_: int,
    pick_no: int,
    draft_slot: int,
    roster_id: int | None,
    player_id: str,
    is_keeper: bool = False,
    first_name: str = "",
    last_name: str = "",
    position: str = "",
) -> dict[str, object]:
    return {
        "draft_id": "did1",
        "round": round_,
        "pick_no": pick_no,
        "draft_slot": draft_slot,
        "roster_id": roster_id,
        "player_id": player_id,
        "is_keeper": is_keeper,
        "picked_by": None,
        "metadata": {
            "first_name": first_name,
            "last_name": last_name,
            "position": position,
            "team": "",
        },
    }


def test_cmd_draft_recap_json_resolves_real_team_names_for_a_league_draft(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1", "2"],
            "name": ["A One", "B Two"],
            "position": ["RB", "WR"],
            "vorp_season": [50.0, 30.0],
        }
    )
    _write_bigboard(repo_root, "2025", vorp_df)

    def handler(request: Request) -> Response:
        if request.path == "/draft/did1":
            return json_response(
                _draft_object_payload(
                    draft_id="did1",
                    slot_to_roster_id={"1": 5, "2": 6},
                    rounds=1,
                    teams=2,
                    league_id="lid1",
                )
            )
        if request.path == "/draft/did1/picks":
            return json_response(
                [
                    _recap_pick_payload(
                        round_=1,
                        pick_no=1,
                        draft_slot=1,
                        roster_id=5,
                        player_id="1",
                        first_name="A",
                        last_name="One",
                        position="RB",
                    ),
                    _recap_pick_payload(
                        round_=1,
                        pick_no=2,
                        draft_slot=2,
                        roster_id=6,
                        player_id="2",
                        first_name="B",
                        last_name="Two",
                        position="WR",
                    ),
                ]
            )
        if request.path == "/league/lid1/rosters":
            return json_response(_rosters_payload())
        if request.path == "/league/lid1/users":
            return json_response(_users_payload())
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(draft_id="did1", value_season="2025", json=True)
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_recap(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    payload = json.loads(out)
    assert payload["draft_id"] == "did1"
    assert payload["value_season"] == "2025"
    team_names = {t["draft_slot"]: t["team_name"] for t in payload["teams"]}
    assert team_names == {1: "Only Gold's Finest", 2: "aaron"}
    slot1 = next(t for t in payload["teams"] if t["draft_slot"] == 1)
    assert slot1["picks"][0]["value_delta"] == 0


def test_cmd_draft_recap_falls_back_to_slot_names_for_a_mock_draft(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A One"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    _write_bigboard(repo_root, "2025", vorp_df)

    def handler(request: Request) -> Response:
        if request.path == "/draft/did1":
            return json_response(
                _draft_object_payload(draft_id="did1", rounds=1, teams=1)
            )
        if request.path == "/draft/did1/picks":
            return json_response(
                [
                    _recap_pick_payload(
                        round_=1,
                        pick_no=1,
                        draft_slot=1,
                        roster_id=None,
                        player_id="1",
                        first_name="A",
                        last_name="One",
                        position="RB",
                    )
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(draft_id="did1", value_season="2025", json=True)
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_recap(
            args, repo_root=repo_root, base_url=base_url
        )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["teams"][0]["team_name"] == "Slot 1"
    assert payload["teams"][0]["roster_id"] is None


def test_cmd_draft_recap_json_nulls_are_explicit_for_unranked_players(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A One"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    _write_bigboard(repo_root, "2025", vorp_df)

    def handler(request: Request) -> Response:
        if request.path == "/draft/did1":
            return json_response(
                _draft_object_payload(draft_id="did1", rounds=1, teams=1)
            )
        if request.path == "/draft/did1/picks":
            return json_response(
                [
                    _recap_pick_payload(
                        round_=1,
                        pick_no=1,
                        draft_slot=1,
                        roster_id=5,
                        player_id="def1",
                        first_name="Pittsburgh",
                        last_name="Steelers",
                        position="DEF",
                    )
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(draft_id="did1", value_season="2025", json=True)
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_recap(
            args, repo_root=repo_root, base_url=base_url
        )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    pick = payload["teams"][0]["picks"][0]
    assert pick["board_rank"] is None
    assert pick["value_delta"] is None


def test_cmd_draft_recap_default_output_is_human_readable_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A One"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    _write_bigboard(repo_root, "2025", vorp_df)

    def handler(request: Request) -> Response:
        if request.path == "/draft/did1":
            return json_response(
                _draft_object_payload(draft_id="did1", rounds=1, teams=1)
            )
        if request.path == "/draft/did1/picks":
            return json_response(
                [
                    _recap_pick_payload(
                        round_=1,
                        pick_no=1,
                        draft_slot=1,
                        roster_id=5,
                        player_id="1",
                        first_name="A",
                        last_name="One",
                        position="RB",
                    )
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(draft_id="did1", value_season="2025", json=False)
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_recap(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "A One" in out
    assert "Δ=+0" in out


def test_cmd_draft_recap_reports_incomplete_draft(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)

    def handler(request: Request) -> Response:
        if request.path == "/draft/did1":
            return json_response(
                _draft_object_payload(draft_id="did1", rounds=2, teams=2)
            )
        if request.path == "/draft/did1/picks":
            return json_response(
                [
                    _recap_pick_payload(
                        round_=1, pick_no=1, draft_slot=1, roster_id=5, player_id="1"
                    )
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(draft_id="did1", value_season="2025", json=False)
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_recap(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "did1" in out
    assert "1/4" in out


def test_cmd_draft_recap_reports_missing_bigboard(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)

    def handler(request: Request) -> Response:
        if request.path == "/draft/did1":
            return json_response(
                _draft_object_payload(draft_id="did1", rounds=1, teams=1)
            )
        if request.path == "/draft/did1/picks":
            return json_response(
                [
                    _recap_pick_payload(
                        round_=1, pick_no=1, draft_slot=1, roster_id=5, player_id="1"
                    )
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(draft_id="did1", value_season="2025", json=False)
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_recap(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "not found" in out


def test_cmd_draft_recap_defaults_value_season_when_omitted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A One"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    _write_bigboard(repo_root, "2025", vorp_df)

    def handler(request: Request) -> Response:
        if request.path == "/draft/did1":
            return json_response(
                _draft_object_payload(draft_id="did1", rounds=1, teams=1)
            )
        if request.path == "/draft/did1/picks":
            return json_response(
                [
                    _recap_pick_payload(
                        round_=1,
                        pick_no=1,
                        draft_slot=1,
                        roster_id=5,
                        player_id="1",
                        first_name="A",
                        last_name="One",
                        position="RB",
                    )
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(draft_id="did1", value_season=None, json=True)
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_recap(
            args,
            repo_root=repo_root,
            base_url=base_url,
            today=lambda: date(2026, 1, 1),
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "defaulting to 2025" in out
    payload = json.loads(out.splitlines()[-1])
    assert payload["value_season"] == "2025"


def test_draft_recap_subcommand_is_registered() -> None:
    from sleeper_agent.main import build_parser

    parser = build_parser()
    args = parser.parse_args(["draft", "recap", "--draft-id", "did1"])

    assert args.func is draft_cmd.cmd_draft_recap
    assert args.draft_id == "did1"
    assert args.value_season is None
    assert args.json is False
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_commands.py -k draft_recap -v`
Expected: FAIL — `AttributeError: module 'sleeper_agent.commands.draft_cmd' has no attribute
'cmd_draft_recap'`

- [ ] **Step 7: Apply the Step 1-3 changes to `draft_cmd.py`, then re-run**

Run: `cd cli && uv run pytest tests/test_commands.py -k draft_recap -v`
Expected: PASS (all 7 new tests)

- [ ] **Step 8: Run the full suite with coverage, lint, and types**

```bash
cd cli
uv run pytest --cov=sleeper_agent --cov-report=term-missing --cov-fail-under=100
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python scripts/check_no_magic.py
```
Expected: all clean — this is the same gate CI runs.

- [ ] **Step 9: Commit and push**

```bash
git add cli/src/sleeper_agent/commands/draft_cmd.py cli/tests/test_commands.py
git commit -m "Add \`draft recap\` CLI command"
git push
```

---

## Task 3: `draft-recap` skill + README + `reports/` directory

**Files:**
- Create: `.claude/skills/draft-recap.md`
- Modify: `.claude/skills/README.md`

No tests — this is markdown content consumed by the LLM at skill-invocation time, same as every
other file in `.claude/skills/` (none of them are pytest-covered).

- [ ] **Step 1: Create the skill file**

Create `.claude/skills/draft-recap.md`:

```markdown
---
name: draft-recap
description: Generate a tongue-in-cheek, graded (A-F) draft report card for the whole league as a shareable HTML report, after any draft (mock or real) completes. Use when asked for a draft recap, draft grades, or a report card -- not for live-draft assistance (`draft`) or pre-draft ranking (`bigboard`).
---

# draft-recap

Yahoo Fantasy's old emailed draft-grade reports, sleeper-agent style: one A-F grade and a few
freeform superlative trophies for the whole league, in an over-the-top sports-radio voice,
grounded in our own big board rather than vibes.

## Prerequisites

- The draft is complete (every pick made).
- That value-season's big board is built (`bigboard` skill) -- `draft recap` hard-stops
  otherwise, same as `draft board`.

## Get the data

```
sleeper-agent draft recap --draft-id <id> [--value-season <year>] --json
```

`--value-season` defaults to current-year-minus-1 (prints a notice when defaulted), same
convention as `draft board`. This prints one JSON object: per team (`draft_slot`, `roster_id`,
`team_name`, `mean_value_delta`), and per pick (`round`, `pick_no`, `name`, `position`,
`is_keeper`, `board_rank`, `vorp`, `value_delta`). `value_delta = pick_no - board_rank`: positive
means the player was still on the board later than their rank deserved (good value), negative
means they were reached for ahead of their rank. A `null` `board_rank`/`vorp`/`value_delta` means
the big board has no row for that player (mainly DEF) -- leave it as "no data," don't invent a
number.

## Write the recap

**Persona**: an over-the-top sports-radio hot-take host -- bombastic, confident, quotable. Roast
and praise equally hard, but good-natured: this is a real league of people you know, not
strangers, so the target is ribbing, not mean-spirited. Stay in character for every team's
write-up, not just the extremes.

**Grades**: one A-F letter grade per team. Anchor loosely to that team's `mean_value_delta` -- a
real signal, not decoration -- but don't linearly map it straight to a grade. Weigh it against
your own read of roster construction (positional balance, starter coverage, upside,
bye-week/stacking risk) the way a human draft analyst would. Call out `is_keeper` picks in the
commentary as a keeper decision made seasons ago, not as this draft's judgment call. 2-4
sentences of in-character commentary per team, citing specific picks by name.

**Trophies**: 3-6 freeform superlative awards across the whole league -- invent them fresh each
run, there's no fixed list. Every trophy must cite a specific pick or team from the data, never
an unsupported vibe.

## Build and ship the report card

1. Load the `artifact-design` skill for the visual pass -- this is a fun, shareable page, worth
   real design effort, not a plain table dump.
2. Write the finished HTML directly to a new file at
   `reports/draft-recap-<draft_season>-<draft_id>.html` (create the top-level `reports/`
   directory if it doesn't exist yet) -- `draft_season`/`draft_id` come straight off the JSON
   output above. This is the exact file the `Artifact` tool publishes from.
3. Publish it with the `Artifact` tool from that path.
4. Commit the file to git with a short message (draft id, season, one-line summary of the
   headline grades/trophies). Committing the recap is this skill's normal job every run, not a
   one-off -- push per whatever the invoking session's git workflow already does.
5. Report the Artifact URL and the committed file path back in chat.

## Not this skill's job

- Deciding *when* to run -- nothing here watches for a draft finishing. Triggered by request.
- Emailing or otherwise notifying the league -- publishing produces a link; sending it anywhere
  is a human call.
```

- [ ] **Step 2: Add `draft-recap.md` to the skills README roster**

In `.claude/skills/README.md`, change:

```markdown
The files in this directory (`keepers.md`, `trades.md`, `waivers.md`, `free-agents.md`,
`news-research.md`, `code-review.md`, `bigboard.md`, `draft.md`) are playbooks for the judgment
```

to:

```markdown
The files in this directory (`keepers.md`, `trades.md`, `waivers.md`, `free-agents.md`,
`news-research.md`, `code-review.md`, `bigboard.md`, `draft.md`, `draft-recap.md`) are playbooks
for the judgment
```

And in the same file's existing note paragraph, change:

```markdown
Note: `draft.md` covers agent-driven live-draft watching (turn detection, background polling) —
not pick judgment, which the big board (`bigboard.md`) resolves pre-draft. For a human at the
keyboard, live drafting is just running `draft board` (the Textual TUI) directly, no skill
needed. Keeper selection is its own file, `keepers.md`. `wargame.md` (a live-draft rehearsal
runbook) is removed.
```

to:

```markdown
Note: `draft.md` covers agent-driven live-draft watching (turn detection, background polling) —
not pick judgment, which the big board (`bigboard.md`) resolves pre-draft. For a human at the
keyboard, live drafting is just running `draft board` (the Textual TUI) directly, no skill
needed. Keeper selection is its own file, `keepers.md`. `draft-recap.md` is a separate, later
step still -- a post-draft report, not part of live drafting or pre-draft ranking. `wargame.md`
(a live-draft rehearsal runbook) is removed.
```

- [ ] **Step 3: Commit and push**

```bash
git add .claude/skills/draft-recap.md .claude/skills/README.md
git commit -m "Add draft-recap skill (graded post-draft HTML report card)"
git push
```

(`reports/` itself is created by the skill on first real use in Task 4 below -- git doesn't
track empty directories, so there's nothing to commit for it yet.)

---

## Task 4: Run it for real against the latest mock draft

Not a coding task -- this is executing the finished feature exactly as `.claude/skills/draft-
recap.md` describes, end to end, against real data already in this repo.

- [ ] **Step 1: Confirm prerequisites**

`data/bigboard/2025.csv` already exists (this repo's real 2025-value-season big board, already
used by every mock-draft `draft board` run logged in `decisions/2026/`). The target draft --
mock draft #4, `draft_id 1398935084572143616`, slot 8, 12 teams, season 2026 -- is already fully
logged as complete in `decisions/2026/2026-08-27-draft-mock-draft-4-slot8.md`. No sync/build
step needed before running recap.

- [ ] **Step 2: Run the CLI command for real**

```bash
cd cli
uv run sleeper-agent draft recap --draft-id 1398935084572143616 --json > /tmp/draft-recap-mock4.json
```
(`--value-season` omitted -- defaults to 2025, printed as a notice on stderr/stdout ahead of the
JSON line; grab the JSON from the last line if redirecting the whole stream.)

- [ ] **Step 3: Follow `.claude/skills/draft-recap.md` to write the report**

Read the JSON, write the grades/trophies in the sports-radio persona, build the HTML page
(loading `artifact-design` first), and write it to
`reports/draft-recap-2026-1398935084572143616.html`.

- [ ] **Step 4: Publish via the `Artifact` tool**

Publish from that exact file path.

- [ ] **Step 5: Commit and push**

```bash
git add reports/draft-recap-2026-1398935084572143616.html
git commit -m "Draft recap: mock draft #4 (slot 8)"
git push
```

- [ ] **Step 6: Report back**

State the Artifact URL and the committed file path in chat.
