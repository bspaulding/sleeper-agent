# Draft strategy research + positional-need-aware draft board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `draft board` annotate its output with the drafter's own roster-position counts
(against the league's roster grid) and per-position value-tier numbers, so positional imbalance
(the first 2026 mock draft's 8 RB/2 WR/0 DEF result) is visible live instead of only
reconstructable after the fact — and write the drafting-strategy research behind this change
into the wiki as a standing reference.

**Architecture:** `draft_tools/board.py` gains pure functions for roster-requirement math,
per-drafter position counts, and per-position value-tier numbers; `render_board` and
`watch_board` take optional `my_counts`/`requirement` parameters that, when present, add a
summary line plus per-row tags/tier numbers without touching the existing VORP sort order.
`draft_cmd.py`'s `cmd_draft_board` resolves "my roster_id" from new `--me`/`--roster-id`/
`--draft-slot` args (mirroring the `--me`/`--roster-id` pattern every other command module
already uses) via a newly-fetched `Draft` object, which also supplies the roster-slot counts
needed for the requirement math. A new wiki page captures the drafting-strategy research this
change was based on.

**Tech Stack:** Python 3.11, polars, pytest, argparse — matches the existing `cli/` package.
No new dependencies.

## Global Constraints

- No live network calls in tests — use the existing `mock_http_server`/`Request`/`Response`
  fixtures (`cli/tests/support/mock_http.py`) exactly as today's tests do.
- Follow the existing functional-dataclass style (`PROJECT_PLAN.md` §10.2): frozen dataclasses,
  hand-written boundary parsers, no classes/inheritance for logic.
- Sort order and `vorp_season` values in `draft board`'s output must not change — this is
  annotation only, per the approved spec
  (`docs/superpowers/specs/2026-08-16-draft-strategy-research-and-positional-need.md`).
- Tier-break threshold is a fixed 20% VORP-drop, `prev_vorp <= 0` always counts as a break.
- Every new CLI arg (`--me`, `--roster-id`, `--draft-slot`) is optional; omitting all three must
  reproduce today's `draft board` output byte-for-byte (no annotation).
- CI (`.github/workflows/ci.yml`) enforces `ruff check .`, `ruff format --check .`, `ty check`,
  `python scripts/check_no_magic.py`, and `pytest --cov=sleeper_agent
  --cov-report=term-missing --cov-fail-under=100` — **100% line coverage is a hard gate**, so
  every new branch (e.g. `position_tag`'s three return paths, `_is_tier_break`'s `prev_vorp <=
  0` guard, both arms of each `if my_roster_id is not None` check) needs a test exercising it,
  not just the happy path.

---

## Task 1: `Draft` model gains roster-slot counts and `slot_to_roster_id`

**Files:**
- Modify: `cli/src/sleeper_agent/models/sleeper.py` (`DraftSettingsRaw`, `DraftRaw`, `Draft`,
  `parse_draft`)
- Test: `cli/tests/test_sleeper_client.py` (extend `test_fetch_draft_parses_real_fixture`)

**Interfaces:**
- Produces: `Draft.slots_qb: int`, `Draft.slots_rb: int`, `Draft.slots_wr: int`,
  `Draft.slots_te: int`, `Draft.slots_flex: int`, `Draft.slots_def: int`,
  `Draft.slot_to_roster_id: dict[int, int]` — consumed by Task 2's
  `roster_requirement_from_draft` and Task 7's `cmd_draft_board`.

- [ ] **Step 1: Extend the failing assertions in the existing fixture test**

Open `cli/tests/test_sleeper_client.py` and replace the body of
`test_fetch_draft_parses_real_fixture` (currently just checks `draft_type`, `rounds`,
`num_teams`) with:

```python
def test_fetch_draft_parses_real_fixture() -> None:
    payload = json.loads(load_fixture("draft.json"))

    def handler(request: Request) -> Response:
        return json_response(payload)

    with mock_http_server(handler) as base_url:
        draft = draft_client.fetch_draft("did", base_url=base_url)

    assert draft.draft_type == "snake"
    assert draft.rounds == 15
    assert draft.num_teams == 12
    assert draft.slots_qb == 1
    assert draft.slots_rb == 2
    assert draft.slots_wr == 2
    assert draft.slots_te == 1
    assert draft.slots_flex == 2
    assert draft.slots_def == 1
    assert draft.slot_to_roster_id == {
        1: 3,
        2: 8,
        3: 1,
        4: 4,
        5: 12,
        6: 6,
        7: 10,
        8: 7,
        9: 2,
        10: 9,
        11: 5,
        12: 11,
    }
```

These values come directly from `cli/tests/fixtures/sleeper/draft.json`'s `settings` block
(`slots_qb: 1, slots_rb: 2, slots_wr: 2, slots_te: 1, slots_flex: 2, slots_def: 1`) and its
top-level `slot_to_roster_id` block.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd cli && uv run pytest tests/test_sleeper_client.py::test_fetch_draft_parses_real_fixture -v`
Expected: FAIL — `AttributeError: 'Draft' object has no attribute 'slots_qb'`

- [ ] **Step 3: Extend `DraftSettingsRaw` and `DraftRaw` in the model file**

In `cli/src/sleeper_agent/models/sleeper.py`, change:

```python
class DraftSettingsRaw(TypedDict, total=False):
    rounds: int
    teams: int
```

to:

```python
class DraftSettingsRaw(TypedDict, total=False):
    rounds: int
    teams: int
    slots_qb: int
    slots_rb: int
    slots_wr: int
    slots_te: int
    slots_flex: int
    slots_def: int
```

And change:

```python
class DraftRaw(TypedDict, total=False):
    draft_id: str
    league_id: str
    season: str
    status: str
    type: str
    start_time: int | None
    settings: DraftSettingsRaw
```

to:

```python
class DraftRaw(TypedDict, total=False):
    draft_id: str
    league_id: str
    season: str
    status: str
    type: str
    start_time: int | None
    settings: DraftSettingsRaw
    slot_to_roster_id: dict[str, int]
```

- [ ] **Step 4: Extend the `Draft` dataclass**

Change:

```python
@dataclass(frozen=True)
class Draft:
    draft_id: str
    league_id: str
    season: str
    status: str
    draft_type: str
    rounds: int
    num_teams: int
    start_time_ms: int | None
```

to:

```python
@dataclass(frozen=True)
class Draft:
    draft_id: str
    league_id: str
    season: str
    status: str
    draft_type: str
    rounds: int
    num_teams: int
    start_time_ms: int | None
    slots_qb: int
    slots_rb: int
    slots_wr: int
    slots_te: int
    slots_flex: int
    slots_def: int
    slot_to_roster_id: dict[int, int]
```

- [ ] **Step 5: Extend `parse_draft`**

Change:

```python
def parse_draft(raw: DraftRaw) -> Draft:
    settings_raw = raw.get("settings") or {}
    return Draft(
        draft_id=raw["draft_id"],
        league_id=raw.get("league_id", ""),
        season=raw.get("season", ""),
        status=raw.get("status", ""),
        draft_type=raw.get("type", ""),
        rounds=settings_raw.get("rounds", 0),
        num_teams=settings_raw.get("teams", 0),
        start_time_ms=raw.get("start_time"),
    )
```

to:

```python
def parse_draft(raw: DraftRaw) -> Draft:
    settings_raw = raw.get("settings") or {}
    return Draft(
        draft_id=raw["draft_id"],
        league_id=raw.get("league_id", ""),
        season=raw.get("season", ""),
        status=raw.get("status", ""),
        draft_type=raw.get("type", ""),
        rounds=settings_raw.get("rounds", 0),
        num_teams=settings_raw.get("teams", 0),
        start_time_ms=raw.get("start_time"),
        slots_qb=settings_raw.get("slots_qb", 0),
        slots_rb=settings_raw.get("slots_rb", 0),
        slots_wr=settings_raw.get("slots_wr", 0),
        slots_te=settings_raw.get("slots_te", 0),
        slots_flex=settings_raw.get("slots_flex", 0),
        slots_def=settings_raw.get("slots_def", 0),
        slot_to_roster_id={
            int(slot): roster_id
            for slot, roster_id in (raw.get("slot_to_roster_id") or {}).items()
        },
    )
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd cli && uv run pytest tests/test_sleeper_client.py::test_fetch_draft_parses_real_fixture -v`
Expected: PASS

- [ ] **Step 7: Run the full test suite to check for other `Draft(...)` construction sites**

Run: `cd cli && uv run pytest -q`
Expected: Any other place that constructs `Draft(...)` directly (rather than via `parse_draft`)
will now fail with a missing-argument `TypeError` — search with
`grep -rn "Draft(" cli/src cli/tests` and add the six new fields (use `0`/`{}` for
fixtures/tests that don't care about them) to any other call site found. If none exist besides
`parse_draft`, this step is a no-op check.

- [ ] **Step 8: Commit**

```bash
cd /Volumes/mini-dock-ssd/repos/sleeper-agent
git add cli/src/sleeper_agent/models/sleeper.py cli/tests/test_sleeper_client.py
git commit -m "Add roster-slot counts and slot_to_roster_id to the Draft model

Sleeper's real draft object (cli/tests/fixtures/sleeper/draft.json)
already carries per-position slot counts and a slot->roster_id map,
available before any picks are made and in both league and mock-draft
mode. Needed as the source for draft board's upcoming roster-need
annotation."
```

---

## Task 2: Roster-requirement + position-tag helpers

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/board.py`
- Test: `cli/tests/test_draft_tools.py`

**Interfaces:**
- Consumes: `Draft` (Task 1's new fields)
- Produces: `RosterRequirement` (frozen dataclass with `hard_min: dict[str, int]`,
  `flex_capacity: int`), `roster_requirement_from_draft(draft: Draft) -> RosterRequirement`,
  `FLEX_ELIGIBLE_POSITIONS: frozenset[str]`, `position_tag(position: str, count: int,
  requirement: RosterRequirement) -> str` — all consumed by Task 5 (`render_board`) and Task 7
  (`cmd_draft_board`).

- [ ] **Step 1: Write the failing tests**

Add to `cli/tests/test_draft_tools.py` (near the existing `# --- draft board` section):

```python
from sleeper_agent.draft_tools.board import (
    RosterRequirement,
    position_tag,
    roster_requirement_from_draft,
)
from sleeper_agent.models.sleeper import Draft


def make_draft(**overrides: object) -> Draft:
    defaults: dict[str, object] = dict(
        draft_id="did",
        league_id="lid",
        season="2026",
        status="drafting",
        draft_type="snake",
        rounds=15,
        num_teams=12,
        start_time_ms=None,
        slots_qb=1,
        slots_rb=2,
        slots_wr=2,
        slots_te=1,
        slots_flex=2,
        slots_def=1,
        slot_to_roster_id={1: 5},
    )
    defaults.update(overrides)
    return Draft(**defaults)  # type: ignore[arg-type]


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k position_tag -v`
Expected: FAIL with `ImportError` (names don't exist yet)

- [ ] **Step 3: Add the implementation to `draft_tools/board.py`**

Add these imports at the top of `cli/src/sleeper_agent/draft_tools/board.py` (alongside the
existing `from sleeper_agent.models.sleeper import DraftPick`):

```python
from dataclasses import dataclass

from sleeper_agent.models.sleeper import Draft, DraftPick
```

Then add, after the imports:

```python
FLEX_ELIGIBLE_POSITIONS = frozenset({"RB", "WR", "TE"})


@dataclass(frozen=True)
class RosterRequirement:
    hard_min: dict[str, int]
    flex_capacity: int


def roster_requirement_from_draft(draft: Draft) -> RosterRequirement:
    return RosterRequirement(
        hard_min={
            "QB": draft.slots_qb,
            "RB": draft.slots_rb,
            "WR": draft.slots_wr,
            "TE": draft.slots_te,
            "DEF": draft.slots_def,
        },
        flex_capacity=draft.slots_flex,
    )


def position_tag(position: str, count: int, requirement: RosterRequirement) -> str:
    hard_min = requirement.hard_min.get(position, 0)
    if count < hard_min:
        return "NEED"
    flex_ceiling = hard_min + (
        requirement.flex_capacity if position in FLEX_ELIGIBLE_POSITIONS else 0
    )
    if count < flex_ceiling:
        return "FLEX"
    return "SURPLUS"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k "position_tag or roster_requirement" -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/board.py cli/tests/test_draft_tools.py
git commit -m "Add roster-requirement and position-tag helpers to draft_tools/board.py"
```

---

## Task 3: `my_roster_positions` — count a drafter's picks by position

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/board.py`
- Test: `cli/tests/test_draft_tools.py`

**Interfaces:**
- Consumes: `DraftPick` (existing model, `roster_id`/`player_position` fields)
- Produces: `my_roster_positions(picks: Sequence[DraftPick], my_roster_id: int) -> dict[str,
  int]` — consumed by Task 5's rendering and Task 6/7's wiring.

- [ ] **Step 1: Write the failing tests**

Add to `cli/tests/test_draft_tools.py`:

```python
from sleeper_agent.draft_tools.board import my_roster_positions


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
```

(`DraftPick` is already imported at the top of `test_draft_tools.py`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k my_roster_positions -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `my_roster_positions`**

Add to `cli/src/sleeper_agent/draft_tools/board.py`, near the other new helpers. Needs
`Sequence` — add `from collections.abc import Sequence` to the imports at the top of the file:

```python
def my_roster_positions(
    picks: Sequence[DraftPick], my_roster_id: int
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pick in picks:
        if pick.roster_id != my_roster_id:
            continue
        position = pick.player_position or "UNK"
        counts[position] = counts.get(position, 0) + 1
    return counts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k my_roster_positions -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/board.py cli/tests/test_draft_tools.py
git commit -m "Add my_roster_positions: count a drafter's picks by position"
```

---

## Task 4: Per-position value-tier computation

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/board.py`
- Test: `cli/tests/test_draft_tools.py`

**Interfaces:**
- Consumes: a `pl.DataFrame` with `sleeper_id`, `position`, `vorp_season` columns (same shape as
  `board_view`'s return value)
- Produces: `compute_tiers(board: pl.DataFrame) -> dict[str, int]` (keyed by `sleeper_id`) —
  consumed by Task 5's `render_board`.

- [ ] **Step 1: Write the failing tests**

Add to `cli/tests/test_draft_tools.py`:

```python
from sleeper_agent.draft_tools.board import compute_tiers


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k compute_tiers -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `compute_tiers`**

Add to `cli/src/sleeper_agent/draft_tools/board.py`:

```python
def compute_tiers(board: pl.DataFrame) -> dict[str, int]:
    tiers: dict[str, int] = {}
    for position in sorted(set(board["position"].to_list())):
        rows = (
            board.filter(pl.col("position") == position)
            .sort("vorp_season", descending=True)
            .to_dicts()
        )
        tier = 1
        prev_vorp: float | None = None
        for row in rows:
            if prev_vorp is not None and _is_tier_break(prev_vorp, row["vorp_season"]):
                tier += 1
            tiers[row["sleeper_id"]] = tier
            prev_vorp = row["vorp_season"]
    return tiers


def _is_tier_break(prev_vorp: float, vorp: float) -> bool:
    if prev_vorp <= 0:
        return True
    return (prev_vorp - vorp) / prev_vorp >= 0.20
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k compute_tiers -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/board.py cli/tests/test_draft_tools.py
git commit -m "Add compute_tiers: per-position value-gap tier numbers for draft board"
```

---

## Task 5: `render_board` annotation (summary line, tags, tier numbers)

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/board.py`
- Test: `cli/tests/test_draft_tools.py`

**Interfaces:**
- Consumes: `RosterRequirement`, `position_tag`, `compute_tiers`, `FLEX_ELIGIBLE_POSITIONS`
  (Tasks 2 and 4)
- Produces: `render_board(board, *, my_counts=None, requirement=None) -> str` (extends the
  existing signature — both new params optional, default `None`) — consumed by Task 6
  (`watch_board`) and Task 7 (`cmd_draft_board`).
- `render_roster_summary(counts: dict[str, int], requirement: RosterRequirement) -> str` — new,
  consumed only by `render_board` itself.

- [ ] **Step 1: Write the failing tests**

Add to `cli/tests/test_draft_tools.py`:

```python
def test_render_board_without_annotation_is_unchanged() -> None:
    board = make_vorp_df().head(1)

    rendered = render_board(board)

    assert rendered == (
        "Best available by value:\n"
        " 1. Player One                RB  vorp=   50.0"
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
    assert "(+2 FLEX)" in rendered
    assert "WR 1/2" in rendered
    # RB is drafted well past hard_min + flex_capacity (5 >= 2 + 2) -> SURPLUS
    assert "RB  vorp=  50.0 tier=1 [SURPLUS]" in rendered
    # WR is below hard_min (1 < 2) -> NEED
    assert "WR  vorp=  30.0 tier=1 [NEED]" in rendered


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k render_board -v`
Expected: FAIL — `test_render_board_with_annotation_adds_summary_tags_and_tiers` and the
`_requires_both_` test fail with `TypeError: render_board() got an unexpected keyword argument
'my_counts'`. `test_render_board_without_annotation_is_unchanged` and the pre-existing
`test_render_board_formats_ranked_lines` should already pass (they exercise no new behavior).

- [ ] **Step 3: Implement the new `render_board` and `render_roster_summary`**

Replace the existing `render_board` function in `cli/src/sleeper_agent/draft_tools/board.py`:

```python
ROSTER_SUMMARY_POSITIONS = ("QB", "RB", "WR", "TE", "DEF")


def render_roster_summary(
    counts: dict[str, int], requirement: RosterRequirement
) -> str:
    parts = []
    for position in ROSTER_SUMMARY_POSITIONS:
        hard_min = requirement.hard_min.get(position, 0)
        count = counts.get(position, 0)
        part = f"{position} {count}/{hard_min}"
        if position in FLEX_ELIGIBLE_POSITIONS and requirement.flex_capacity:
            part += f" (+{requirement.flex_capacity} FLEX)"
        parts.append(part)
    return "My roster so far: " + "  ".join(parts)


def render_board(
    board: pl.DataFrame,
    *,
    my_counts: dict[str, int] | None = None,
    requirement: RosterRequirement | None = None,
) -> str:
    annotation = (
        (my_counts, requirement)
        if my_counts is not None and requirement is not None
        else None
    )
    lines = []
    if annotation is not None:
        counts, req = annotation
        lines.append(render_roster_summary(counts, req))
        lines.append("")
    lines.append("Best available by value:")
    tiers = compute_tiers(board) if annotation is not None else {}
    for rank, row in enumerate(board.to_dicts(), start=1):
        line = (
            f"{rank:2d}. {row['name']:<25} {row['position']:<3} "
            f"vorp={row['vorp_season']:7.1f}"
        )
        if annotation is not None:
            counts, req = annotation
            tier = tiers.get(row["sleeper_id"], 1)
            tag = position_tag(row["position"], counts.get(row["position"], 0), req)
            line += f" tier={tier} [{tag}]"
        lines.append(line)
    return "\n".join(lines)
```

This replaces the old body:

```python
def render_board(board: pl.DataFrame) -> str:
    lines = ["Best available by value:"]
    for rank, row in enumerate(board.to_dicts(), start=1):
        lines.append(
            f"{rank:2d}. {row['name']:<25} {row['position']:<3} vorp={row['vorp_season']:7.1f}"
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k render_board -v`
Expected: PASS (5 tests, including the two pre-existing ones)

- [ ] **Step 5: Run the full draft_tools test file to check nothing else regressed**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/board.py cli/tests/test_draft_tools.py
git commit -m "Add opt-in roster-need annotation to render_board

my_counts/requirement are optional kwargs; when both are provided,
render_board adds a roster-position summary line and per-row
tier/NEED-FLEX-SURPLUS tags. Sort order and vorp values are untouched
-- this is annotation, not re-ranking."
```

---

## Task 6: `watch_board` threads annotation through the live-polling loop

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/board.py`
- Test: `cli/tests/test_draft_tools.py`

**Interfaces:**
- Consumes: `my_roster_positions` (Task 3), `render_board` (Task 5)
- Produces: `watch_board(..., my_roster_id: int | None = None, requirement: RosterRequirement |
  None = None)` (extends the existing signature) — consumed by Task 7 (`cmd_draft_board`).

- [ ] **Step 1: Write the failing test**

Add to `cli/tests/test_draft_tools.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k watch_board_annotate -v`
Expected: FAIL — `test_watch_board_annotates_when_my_roster_id_given` fails with `TypeError:
watch_board() got an unexpected keyword argument 'my_roster_id'`.
`test_watch_board_without_my_roster_id_is_unannotated` should already pass (no new args used) —
confirms the no-args path is unaffected before the change, and must still pass after.

- [ ] **Step 3: Update `watch_board`**

Replace the existing `watch_board` function body in
`cli/src/sleeper_agent/draft_tools/board.py`:

```python
def watch_board(
    draft_id: str,
    vorp_df: pl.DataFrame,
    *,
    base_url: str = SLEEPER_BASE_URL,
    # Sleeper's documented limit is ~1000 req/min before risking an IP block; one GET per
    # poll at 5s is ~12 req/min (~1% of budget), so there's no rate-limit reason to poll
    # slower — see .claude/skills/draft.md's "During the draft" section.
    poll_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
    render: Callable[[str], None] = print,
    fetch_picks: Callable[..., list[DraftPick]] = fetch_draft_picks,
    log_path: Path | None = None,
    my_roster_id: int | None = None,
    requirement: RosterRequirement | None = None,
) -> None:
    previous_drafted_ids: frozenset[str] | None = None
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        picks = fetch_picks(draft_id, base_url=base_url)
        drafted_ids = frozenset(pick.player_id for pick in picks)
        if drafted_ids != previous_drafted_ids:
            board = board_view(vorp_df, picks)
            my_counts = (
                my_roster_positions(picks, my_roster_id)
                if my_roster_id is not None
                else None
            )
            rendered = render_board(
                board,
                my_counts=my_counts,
                requirement=requirement if my_roster_id is not None else None,
            )
            render(rendered)
            if log_path is not None:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(f"# Draft board — live\n\n{rendered}\n")
            previous_drafted_ids = drafted_ids
        iteration += 1
        if max_iterations is None or iteration < max_iterations:
            sleep(poll_seconds)
```

(Only the signature and the four lines building `my_counts`/`rendered` changed from the
original — the polling/logging control flow is untouched.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -k watch_board -v`
Expected: PASS (all `watch_board` tests, old and new)

- [ ] **Step 5: Run the full draft_tools test file**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/board.py cli/tests/test_draft_tools.py
git commit -m "Thread roster-need annotation through watch_board's polling loop"
```

---

## Task 7: `cmd_draft_board` CLI wiring (`--me`/`--roster-id`/`--draft-slot`)

**Files:**
- Modify: `cli/src/sleeper_agent/commands/draft_cmd.py`
- Test: `cli/tests/test_commands.py`

**Interfaces:**
- Consumes: `fetch_draft` (`sleeper_client/draft.py`, already imported elsewhere in the
  codebase), `roster_requirement_from_draft`, `my_roster_positions`, `RosterRequirement`,
  updated `render_board`/`watch_board` (Tasks 1-6)

- [ ] **Step 1: Write the failing tests**

`test_commands.py` already defines a `_draft_payload`-shaped need — add a new helper next to the
existing `_league_payload` (around line 1030) and update the four affected existing tests plus
add two new ones. First, add the helper:

```python
def _draft_object_payload(
    draft_id: str = "did1", slot_to_roster_id: dict[str, int] | None = None
) -> dict[str, object]:
    return {
        "draft_id": draft_id,
        "type": "snake",
        "settings": {
            "rounds": 15,
            "teams": 12,
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

Now update `test_cmd_draft_board_prints_available_players`'s handler to also serve the draft
object, and add `me=False, roster_id=None, draft_slot=None` to its `args`:

```python
def test_cmd_draft_board_prints_available_players(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1", "2"],
            "name": ["A", "B"],
            "position": ["RB", "WR"],
            "vorp_season": [50.0, 30.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Best available by value:" in out
    assert "A" in out
    assert "My roster so far" not in out  # no --me/--roster-id/--draft-slot given
```

Apply the identical two changes (handler gains a `/draft/did1` case; `args` gains `me=False,
roster_id=None, draft_slot=None`) to:
- `test_cmd_draft_board_excludes_players_with_no_nfl_team`
- `test_cmd_draft_board_watch_writes_decision_log`

For `test_cmd_draft_board_with_draft_id_skips_league_lookup`, the draft object is served at
`/draft/mockdid1` (not `/draft/did1`, since this test uses `--draft-id mockdid1` directly):

```python
def test_cmd_draft_board_with_draft_id_skips_league_lookup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Sleeper mock draft has no league to resolve — --draft-id points at it directly."""
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1", "2"],
            "name": ["A", "B"],
            "position": ["RB", "WR"],
            "vorp_season": [50.0, 30.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2026.parquet", schema_version=1)

    def handler(request: Request) -> Response:
        if request.path == "/draft/mockdid1":
            return json_response(_draft_object_payload(draft_id="mockdid1"))
        if request.path == "/draft/mockdid1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id=None,
        draft_id="mockdid1",
        rounds=15,
        watch=False,
        value_season="2026",
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Best available by value:" in out
    assert "A" in out
```

Now add two new tests exercising the annotation end to end — one for `--me` (league mode), one
for `--draft-slot` (mock mode):

```python
def test_cmd_draft_board_annotates_with_me_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1", "2"],
            "name": ["A", "B"],
            "position": ["RB", "WR"],
            "vorp_season": [50.0, 30.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2025.parquet", schema_version=1)

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload())
        if request.path == "/draft/did1/picks":
            # roster_id 5 matches draft_cmd.ME_ROSTER_ID
            return json_response(
                [
                    {
                        "draft_id": "did1",
                        "round": 1,
                        "pick_no": 1,
                        "draft_slot": 1,
                        "roster_id": 5,
                        "player_id": "3",
                        "is_keeper": False,
                        "picked_by": "u1",
                        "metadata": {
                            "first_name": "Already",
                            "last_name": "Drafted",
                            "position": "RB",
                        },
                    }
                ]
            )
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        watch=False,
        value_season=None,
        num_teams=12,
        me=True,
        roster_id=None,
        draft_slot=None,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "My roster so far:" in out
    assert "RB 1/2" in out


def test_cmd_draft_board_annotates_with_draft_slot_in_mock_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    vorp_df = pl.DataFrame(
        {
            "sleeper_id": ["1"],
            "name": ["A"],
            "position": ["RB"],
            "vorp_season": [50.0],
        }
    )
    from sleeper_agent.storage.parquet_store import write_table

    write_table(vorp_df, repo_root / "data" / "vorp" / "2026.parquet", schema_version=1)

    def handler(request: Request) -> Response:
        if request.path == "/draft/mockdid1":
            # slot 8 -> roster_id 42 for this mock
            return json_response(
                _draft_object_payload(draft_id="mockdid1", slot_to_roster_id={"8": 42})
            )
        if request.path == "/draft/mockdid1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id=None,
        draft_id="mockdid1",
        rounds=15,
        watch=False,
        value_season="2026",
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=8,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_board(
            args, repo_root=repo_root, base_url=base_url
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "My roster so far:" in out
    assert "RB 0/2" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_commands.py -k cmd_draft_board -v`
Expected: FAIL — the four updated tests fail with `AttributeError: 'Namespace' object has no
attribute 'me'` (since `cmd_draft_board` doesn't read it yet, this specific failure won't appear
until Step 3, but the two new tests fail the same way now); before Step 3, actually all six will
currently fail because `handler` raises `AssertionError: unexpected path /draft/did1` (or
`/draft/mockdid1`) since the *old* `cmd_draft_board` never requests that path. Confirm the
failure mode matches "unexpected path" for the four updated tests, and either `AssertionError`
or `AttributeError` for the two new ones — the exact message isn't important, only that they
fail before the implementation step.

- [ ] **Step 3: Update `add_subcommands` to register the new args**

In `cli/src/sleeper_agent/commands/draft_cmd.py`, find the `board_parser` block inside
`add_subcommands` and add three lines after the existing `--num-teams` argument:

```python
    board_parser.add_argument(
        "--num-teams",
        type=int,
        default=12,
        help="Only used with --draft-id, where there's no league.settings to read it from.",
    )
    board_parser.add_argument("--me", action="store_true")
    board_parser.add_argument("--roster-id", type=int, default=None)
    board_parser.add_argument(
        "--draft-slot",
        type=int,
        default=None,
        help=(
            "Resolve my roster_id from this draft's slot_to_roster_id map — needed for "
            "a mock draft (no stable roster_id across seasons), or as an alternative to "
            "--me/--roster-id in league mode."
        ),
    )
    board_parser.set_defaults(func=cmd_draft_board)
```

- [ ] **Step 4: Update the imports at the top of `draft_cmd.py`**

Change:

```python
from sleeper_agent.draft_tools.board import board_view, render_board, watch_board
```

to:

```python
from sleeper_agent.draft_tools.board import (
    board_view,
    my_roster_positions,
    render_board,
    roster_requirement_from_draft,
    watch_board,
)
```

And change:

```python
from sleeper_agent.sleeper_client.draft import (
    KeeperEligible,
    KeeperEligibleUndraftedDefault,
    KeeperIneligibleCostBelowRoundOne,
    KeeperIneligibleMaxYearsReached,
    fetch_draft_picks,
    keeper_history,
)
```

to:

```python
from sleeper_agent.sleeper_client.draft import (
    KeeperEligible,
    KeeperEligibleUndraftedDefault,
    KeeperIneligibleCostBelowRoundOne,
    KeeperIneligibleMaxYearsReached,
    fetch_draft,
    fetch_draft_picks,
    keeper_history,
)
```

- [ ] **Step 5: Update `cmd_draft_board`'s body**

Find this block in `cmd_draft_board` (right after the `vorp_df is None` check):

```python
    vorp_df = _read_vorp(root, value_season)
    if vorp_df is None:
        print(
            f"no VORP data for season {value_season} — run `stats vorp --season {value_season}` first"
        )
        return 1

    players_df = _read_players(root)
```

Insert the new draft-fetch and my-roster-id resolution between the `return 1` and
`players_df = ...`:

```python
    vorp_df = _read_vorp(root, value_season)
    if vorp_df is None:
        print(
            f"no VORP data for season {value_season} — run `stats vorp --season {value_season}` first"
        )
        return 1

    draft = fetch_draft(draft_id, base_url=base_url)
    requirement = roster_requirement_from_draft(draft)
    my_roster_id: int | None = None
    if args.draft_slot is not None:
        my_roster_id = draft.slot_to_roster_id.get(args.draft_slot)
    elif args.me:
        my_roster_id = ME_ROSTER_ID
    elif args.roster_id is not None:
        my_roster_id = args.roster_id

    players_df = _read_players(root)
```

Then find the watch branch:

```python
    if args.watch:
        log_path = (
            decisions_dir(root) / value_season / f"{today().isoformat()}-draft-live.md"
        )
        watch_board(
            draft_id,
            vorp_df,
            base_url=base_url,
            log_path=log_path,
            max_iterations=max_watch_iterations,
        )
        return 0

    picks = fetch_draft_picks(draft_id, base_url=base_url)
    board = board_view(vorp_df, picks, top_n=top_n)
    print(render_board(board))
    return 0
```

Replace it with:

```python
    if args.watch:
        log_path = (
            decisions_dir(root) / value_season / f"{today().isoformat()}-draft-live.md"
        )
        watch_board(
            draft_id,
            vorp_df,
            base_url=base_url,
            log_path=log_path,
            max_iterations=max_watch_iterations,
            my_roster_id=my_roster_id,
            requirement=requirement if my_roster_id is not None else None,
        )
        return 0

    picks = fetch_draft_picks(draft_id, base_url=base_url)
    board = board_view(vorp_df, picks, top_n=top_n)
    my_counts = (
        my_roster_positions(picks, my_roster_id) if my_roster_id is not None else None
    )
    print(
        render_board(
            board,
            my_counts=my_counts,
            requirement=requirement if my_roster_id is not None else None,
        )
    )
    return 0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_commands.py -k cmd_draft_board -v`
Expected: PASS (9 tests: 7 pre-existing + 2 new)

- [ ] **Step 7: Run the full test suite**

Run: `cd cli && uv run pytest -q`
Expected: All PASS

- [ ] **Step 8: Manually verify the CLI end to end against a real mock draft**

Run (using a real or currently-open mock draft ID, matching how `draft.md` documents mock-mode
usage):
```bash
cd cli && uv run sleeper-agent draft board --draft-id <mock-draft-id> --value-season 2025 --draft-slot <your-slot>
```
Expected: Output includes a `My roster so far:` line and `tier=`/`[NEED|FLEX|SURPLUS]` tags on
each row, with the VORP-sorted order identical to a run without `--draft-slot`.

- [ ] **Step 9: Commit**

```bash
git add cli/src/sleeper_agent/commands/draft_cmd.py cli/tests/test_commands.py
git commit -m "Wire --me/--roster-id/--draft-slot into draft board's CLI

Resolves 'my roster_id' the same way every other command module
already does (--me/--roster-id), plus a new --draft-slot for mock
drafts (resolved via the draft object's slot_to_roster_id). When none
of the three are passed, output is byte-for-byte identical to before
this change."
```

---

## Task 8: Wiki — drafting strategy research + standing-rule updates

**Files:**
- Create: `wiki/team/draft-strategy.md`
- Modify: `wiki/team/roster-philosophy.md`
- Modify: `.claude/skills/draft.md`

- [ ] **Step 1: Write `wiki/team/draft-strategy.md`**

Create the file with this content:

```markdown
---
last_updated: '2026-08-16'
source: docs/superpowers/specs/2026-08-16-draft-strategy-research-and-positional-need.md
---

# Drafting strategy — general reference

Standing reference on fantasy-football drafting theory, distinct from
`wiki/team/roster-philosophy.md` (which holds this team's own retrospectives and standing
rules). Written up from research done while fixing the first 2026 mock draft's 8 RB/2 WR/0 DEF
result — see `roster-philosophy.md` for that specific incident.

## Value-based drafting (VBD) baselines

VBD assigns every player a value by comparing their projected points to a baseline
"replacement" player at the same position. The baseline you pick changes what the number means:

- **VORP** (value over replacement player) — baseline is a readily available waiver-wire
  player. This is what `stats vorp`/`draft board` compute today.
- **VOLS** (value over last starter) — baseline is the worst player who'll actually start
  *somewhere* in the league, given every team's roster requirements. Bakes roster-slot scarcity
  into the number itself, unlike VORP.
- **VONA** (value over next available) — baseline is the best player likely still available at
  your *next* pick. Accounts for draft position and pick-to-pick gaps, but can't be computed
  before the draft since it depends on what actually happens.

**Why this matters here:** a pure-VORP board (what `draft board` produces) doesn't know about
roster slots at all — it will keep recommending the highest-VORP player regardless of position,
which is exactly what produced the 8 RB result. VOLS-style thinking is "does this position still
have a player at all left to fill a starting slot" — a different question than "what's the
single highest-value player." `draft board`'s new roster-need annotation (added alongside this
page) is a lightweight way to get VOLS-style information without recomputing VBD baselines from
scratch: it shows starter-slot counts directly, next to the existing VORP ranking.

## RB strategy spectrum: Zero-RB, Hero-RB, Robust-RB

These are named points on a spectrum of how early/heavily to draft running backs, driven by two
facts about the position: RB has the steepest value drop-off of any position (confirmed in this
league's own VORP data — see `roster-philosophy.md`), and RB carries the highest in-season
injury/role-loss risk of the skill positions.

- **Robust-RB** — draft RB heavily in the first 3-4 rounds (e.g. 3 RBs in the first 4 picks),
  betting on locking in the scarcest, highest-value position before it's gone. Historically
  strong when true 3-down "bell-cow" backs were common; weaker as more offenses split RB touches
  by committee.
- **Zero-RB** — deliberately punt RB in the first several rounds, load up on WR/QB/TE value
  instead, and address RB later once the position's depth (and price) has normalized. Bets on RB
  being volatile enough that early RB draft capital is a bad risk-adjusted price, and that
  useful RB production can still be found later or via the waiver wire in-season.
- **Hero-RB** — a middle path: take exactly one true RB1 early (accepting the position's
  scarcity premium for a top player), then pivot to WR/QB/TE depth, treating the rest of the RB
  room as bench lottery tickets rather than a second early investment.

**Which fits this league:** this is a **best-ball** league (`league.settings.best_ball`) with no
in-season waiver-wire management modeled by this codebase (`PROJECT_PLAN.md`'s best-ball note).
That cuts against a pure Zero-RB bet, which leans on being able to actively stream RB
replacements off waivers all season — a lever this team doesn't really pull. A Hero-RB-leaning
approach (one strong early RB, then broaden) is a more natural fit than either extreme, but this
is a starting hypothesis to test against the next mock draft, not a hard rule yet.

## Tiered drafting and positional runs

The mainstream answer to "should I reach for a position" isn't raw position count, it's
**tiers** — clusters of players separated by real value gaps. If the last player in a tier is
still on the board and the next tier down is a real drop-off, that's a legitimate reason to
deviate from strict best-player-available; if a "run" on a position starts but there's no real
tier cliff yet, chasing it is usually a mistake (jumping in reactively rather than reading the
board).

`draft board`'s new per-row `tier=N` tag (computed independently per position, a ≥20% VORP drop
counts as a new tier — see the CLI implementation) is a direct, mechanical version of this idea:
a jump in a position's tier number between two rows is the signal to weigh a reach against,
regardless of how many players of that position are already gone.

## Best-ball positional allocation

Large-pool best-ball guidance (e.g. from sites covering DraftKings-scale multi-entry contests)
suggests rough ranges like 2-3 QB, 5-7 RB, 6-9 WR, 2-4 TE per roster. **This doesn't translate
directly to this league** — that guidance is tuned for huge best-ball player pools with
different roster sizes and lineup-scoring rules. This league's actual grid is
`QB,RB,RB,WR,WR,TE,FLEX,FLEX,DEF,BN×6` (15 total, `roster-philosophy.md`'s roster grid section),
which implies a much tighter allocation: `QB≥1, RB≥2, WR≥2, TE≥1, DEF≥1` as an absolute floor,
with the 2 FLEX + 6 bench spots as the only real room for leaning into whichever position is
paying off that draft. The 8 RB mock-draft-1 result used up nearly all of that flexible room on
one position, at the direct cost of a completely unfillable DEF slot and zero WR bench cushion.

## Sources

- [FantasyPros: VORP, VONA, VOLS explained](https://www.fantasypros.com/2025/06/fantasy-football-draft-strategy-vorp-vols-vona/)
- [Athlon: How to Handle Positional Runs](https://athlonsports.com/fantasy/fantasy-football-draft-strategy-navigating-positional-runs)
- [FantasyLife: What is Zero RB?](https://www.fantasylife.com/articles/best-ball/what-is-zero-rb-drafting-tips-from-a-pro)
- [Athlon: Stud RB vs. Zero RB Theories](https://athlonsports.com/fantasy/fantasy-football-strategy-stud-rb-theory-vs-zero-rb-theory)
- [Establish The Run: Optimal Position Allocation for Best Ball](https://establishtherun.com/optimal-position-allocation-for-draftkings-best-ball/)
```

- [ ] **Step 2: Update `wiki/team/roster-philosophy.md`'s standing rules**

Open `wiki/team/roster-philosophy.md`. Find standing rule 1:

```markdown
1. **Never take pure best-player-available (highest VORP) blind.** RB carries roughly 2x WR's
   value-over-replacement at every depth down to about rank 24 (see below) — a pure-VORP policy
   will over-draft RB by construction, not by chance. Check positional need against the roster
   grid (below) before taking the board's #1 suggestion.
```

Replace it with:

```markdown
1. **Never take pure best-player-available (highest VORP) blind.** RB carries roughly 2x WR's
   value-over-replacement at every depth down to about rank 24 (see below) — a pure-VORP policy
   will over-draft RB by construction, not by chance. Check positional need against the roster
   grid (below) before taking the board's #1 suggestion — `draft board --me` (or `--draft-slot`
   for a mock) now shows this live: a "My roster so far" summary plus a NEED/FLEX/SURPLUS tag on
   every row, so this check no longer has to be done by hand. See also
   `wiki/team/draft-strategy.md` for the general theory behind this (VBD baselines, tiered
   drafting, RB strategy spectrum).
```

Then find the final standing rule (rule 6, ending "...before the real draft on Aug 29.") and add
a new rule 7 immediately after it:

```markdown
7. **Read `wiki/team/draft-strategy.md` before a draft, not just this file.** It holds the
   general drafting-strategy research (VBD baselines, RB strategy spectrum, tiered drafting,
   best-ball positional-allocation reasoning) that motivated rule 1 and the `draft board`
   annotation above — this file stays scoped to this team's own retrospectives and specific
   rules.
```

- [ ] **Step 3: Update `.claude/skills/draft.md`**

Open `.claude/skills/draft.md`. Find step 1 of the "Live snake draft" section:

```markdown
1. Before the draft: review `value rank --top 50` (and by position) to build a mental tier list.
   Check `wiki/team/roster-philosophy.md` and `wiki/team/keeper-strategy.md` if they exist for
   standing strategy notes from prior seasons.
```

Replace it with:

```markdown
1. Before the draft: review `value rank --top 50` (and by position) to build a mental tier list.
   Check `wiki/team/roster-philosophy.md`, `wiki/team/draft-strategy.md`, and
   `wiki/team/keeper-strategy.md` if they exist for standing strategy notes from prior seasons
   and general drafting theory.
```

Find step 2's `draft board` invocation description:

```markdown
2. During the draft: `draft board --league-id <id> --rounds 15 [--watch]` shows best-available by
   value, already excluding every drafted and kept player. Use `--watch` for an unattended or
   semi-attended session — it polls and re-renders on every change, and mirrors the board to a
   decision-log entry (`decisions/<season>/<date>-draft-live.md`) so there's a record even if
   nobody's watching every pick.
   - For a **mock draft** (practice run before the real draft — no league object exists for it),
     use `draft board --draft-id <mock-draft-id> --value-season <year> [--num-teams <n>] [--watch]`
     instead: it points straight at the draft's public picks endpoint, skipping the league lookup
     `--league-id` needs. `--value-season` is required in this mode (there's no league to infer it
     from); `--num-teams` defaults to 12 (this league's size) and only matters for `--rounds`
     sizing. Do a mock draft or two in the run-up to the real one — it's cheap rehearsal for tier
     breaks and pacing, and a chance to sanity-check the value rankings against how a real room
     actually drafts.
```

Replace it with:

```markdown
2. During the draft: `draft board --league-id <id> --rounds 15 --me [--watch]` shows
   best-available by value, already excluding every drafted and kept player. **Always pass
   `--me`** (or `--roster-id <id>` if not drafting from this team's usual roster_id) — without
   it, the board has no roster-need annotation at all (no "My roster so far" summary, no
   NEED/FLEX/SURPLUS tags, no per-position `tier=N` numbers), which is exactly the gap that let
   the first 2026 mock draft go 8 RB/2 WR/0 DEF unnoticed. Use `--watch` for an unattended or
   semi-attended session — it polls and re-renders on every change, and mirrors the board to a
   decision-log entry (`decisions/<season>/<date>-draft-live.md`) so there's a record even if
   nobody's watching every pick.
   - For a **mock draft** (practice run before the real draft — no league object exists for it),
     use `draft board --draft-id <mock-draft-id> --value-season <year> --draft-slot <n>
     [--num-teams <n>] [--watch]` instead: it points straight at the draft's public picks
     endpoint, skipping the league lookup `--league-id` needs. `--value-season` is required in
     this mode (there's no league to infer it from); `--draft-slot` is the slot number chosen
     when starting the mock (needed for annotation, since a mock draft has no stable roster_id —
     `--me` won't resolve to anything meaningful there); `--num-teams` defaults to 12 (this
     league's size) and only matters for `--rounds` sizing. Do a mock draft or two in the run-up
     to the real one — it's cheap rehearsal for tier breaks and pacing, and a chance to
     sanity-check the value rankings against how a real room actually drafts.
```

Find step 3's bullet on positional runs:

```markdown
   - Positional runs: if a position is being drafted heavily by other teams, weigh reaching for
     the position against best-player-available — `draft board`'s ranking is value-only, it
     doesn't model positional scarcity dynamics mid-draft.
```

Replace it with:

```markdown
   - Positional runs: if a position is being drafted heavily by other teams, weigh reaching for
     the position against best-player-available. `draft board --me` now shows the facts this
     judgment call needs — my-roster position counts vs. the roster grid, and a per-row `tier=N`
     number that jumps when a real value cliff hits a position — but weighing reach-vs-wait
     against those facts is still a judgment call the tool doesn't make for you. See
     `wiki/team/draft-strategy.md` for the general reasoning (tiered drafting, RB strategy
     spectrum).
```

- [ ] **Step 4: Verify the wiki changes render sensibly**

Run: `cd cli && uv run sleeper-agent wiki stale --unscoped 2>&1 | head -20` (or open the
three edited/created files directly) to confirm no obviously broken frontmatter or markdown —
this repo's wiki tooling reads frontmatter (`last_updated`, `source`) so a malformed YAML block
would surface as a tool error.

- [ ] **Step 5: Commit**

```bash
git add wiki/team/draft-strategy.md wiki/team/roster-philosophy.md .claude/skills/draft.md
git commit -m "Add drafting-strategy research wiki page, wire it and draft board's new --me/--draft-slot annotation into standing rules

New wiki/team/draft-strategy.md covers VBD baselines (VORP/VOLS/VONA),
the Zero-RB/Hero-RB/Robust-RB spectrum, tiered drafting, and best-ball
positional allocation, adapted to this league's actual roster grid.
roster-philosophy.md and draft.md now point at draft board's new
--me/--draft-slot annotation as the live mechanism for standing rule
1's positional-need check."
```

---

## Final check: run the whole suite once more

- [ ] **Step 1: Run the exact CI commands locally**

Run, from the `cli/` directory, each of the five commands `.github/workflows/ci.yml` runs:

```bash
cd cli
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python scripts/check_no_magic.py
uv run pytest --cov=sleeper_agent --cov-report=term-missing --cov-fail-under=100
```

Expected: All five exit 0. If the coverage gate fails, the `term-missing` report names the
uncovered lines directly — add a test for that branch (per the Global Constraints note on 100%
coverage) rather than weakening the gate.

- [ ] **Step 2: Confirm no leftover references to the abandoned `--roster-positions` design**

Run: `grep -rn "roster_positions.*parse_roster_requirement\|--roster-positions" cli/ docs/` —
expected: no matches (an earlier spec draft proposed parsing `League.roster_positions` strings
with a `--roster-positions` CLI override for mock mode; that was replaced by the
`Draft.slot_to_roster_id`-based design in Task 1/2 before this plan was written — this just
confirms nothing from that earlier direction leaked into the final code).
