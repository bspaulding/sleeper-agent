# `draft watch-picks` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested `sleeper-agent draft watch-picks` CLI command that replaces the ad hoc bash
Monitor-loop script used to track live/mock draft picks, per
`docs/superpowers/specs/2026-08-22-draft-watch-picks-design.md`.

**Architecture:** A pure snake-order function (`slot_for_pick`) plus a dependency-injected
orchestration function (`watch_picks`), both in `draft_tools/board.py` alongside the existing
`watch_board`. `cmd_draft_board`'s setup logic is extracted into a shared `_resolve_draft_context`
helper so the new `cmd_draft_watch_picks` command can reuse it without duplication. A prerequisite
schema change threads a `player_team` field through `DraftPick` end-to-end so per-pick lines can
show a team abbreviation.

**Tech Stack:** Python, polars, pytest, argparse (existing project stack — no new dependencies).

## Global Constraints

- Follow this repo's existing test style exactly: dependency-injected `fetch_picks`/`sleep`/
  `render`/`max_iterations` for orchestration functions (see `watch_board`), `mock_http_server` +
  `argparse.Namespace` + `capsys` for CLI-level command tests (see `test_cmd_draft_board_*` in
  `cli/tests/test_commands.py`).
- `DraftPick` is a frozen dataclass with no defaulted fields (except test-only helper defaults) —
  every production and test construction site must be updated explicitly when adding a field.
- `storage/parquet_store.read_table` fails loudly on a schema-version mismatch by design (no
  silent migration) — bumping `DRAFTS_SCHEMA_VERSION` means existing synced data needs a resync,
  not an in-place migration script.
- Run `cd cli && pytest` (or the equivalent project test command) after every task; all tests must
  pass before moving to the next task.

---

### Task 1: `DraftPick.player_team` + persisted-schema migration

**Files:**
- Modify: `cli/src/sleeper_agent/models/sleeper.py` (`DraftPick` dataclass, `parse_draft_pick`)
- Modify: `cli/src/sleeper_agent/sleeper_client/sync.py` (`draft_picks_to_dataframe`,
  `dataframe_to_draft_picks`, `DRAFTS_SCHEMA_VERSION`)
- Test: `cli/tests/test_sleeper_client.py` (new test)
- Modify (fixture-only, no assertion changes): `cli/tests/test_sleeper_sync.py` (2 `DraftPick(...)`
  sites in `test_draft_picks_dataframe_round_trips`)
- Modify (fixture-only): `cli/tests/test_commands.py` (4 `DraftPick(...)` sites in the keeper-
  eligibility fixture, around line 1321-1370)
- Modify: `cli/tests/test_draft_tools.py` (`make_pick` helper + 1 direct `DraftPick(...)` site in
  `test_my_roster_positions_buckets_missing_position_as_unk`)

**Interfaces:**
- Produces: `DraftPick.player_team: str | None` — every later task that constructs or reads a
  `DraftPick` may pass/rely on this field.

- [ ] **Step 1: Write the failing test**

Add to `cli/tests/test_sleeper_client.py` (near `test_fetch_draft_picks_parses_real_fixture_including_keepers`):

```python
def test_fetch_draft_picks_parses_player_team_from_metadata() -> None:
    payload = json.loads(load_fixture("draft_picks.json"))

    def handler(request: Request) -> Response:
        return json_response(payload)

    with mock_http_server(handler) as base_url:
        picks = draft_client.fetch_draft_picks("did", base_url=base_url)

    # First fixture entry is Ja'Marr Chase, metadata.team == "CIN".
    assert picks[0].player_team == "CIN"
```

- [ ] **Step 2: Run it, verify it fails**

Run: `cd cli && pytest tests/test_sleeper_client.py::test_fetch_draft_picks_parses_player_team_from_metadata -v`
Expected: FAIL — `AttributeError: 'DraftPick' object has no attribute 'player_team'`

- [ ] **Step 3: Add the field to the model and parse it**

In `cli/src/sleeper_agent/models/sleeper.py`, extend the `DraftPick` dataclass (currently ends at
`player_position: str | None`):

```python
@dataclass(frozen=True)
class DraftPick:
    draft_id: str
    round: int
    pick_no: int
    draft_slot: int
    roster_id: int | None
    player_id: str
    is_keeper: bool
    picked_by: str | None
    player_name: str | None
    player_position: str | None
    player_team: str | None
```

And in `parse_draft_pick`, add the extraction:

```python
def parse_draft_pick(raw: DraftPickRaw) -> DraftPick:
    metadata = raw.get("metadata") or {}
    first_name = metadata.get("first_name")
    last_name = metadata.get("last_name")
    player_name = f"{first_name} {last_name}" if first_name or last_name else None
    return DraftPick(
        draft_id=raw.get("draft_id", ""),
        round=raw["round"],
        pick_no=raw["pick_no"],
        draft_slot=raw.get("draft_slot", 0),
        roster_id=raw["roster_id"],
        player_id=raw["player_id"],
        is_keeper=bool(raw.get("is_keeper")),
        picked_by=raw.get("picked_by"),
        player_name=player_name,
        player_position=metadata.get("position"),
        player_team=metadata.get("team"),
    )
```

(`DraftPickMetadataRaw` already declares `team: str` — no change needed there.)

- [ ] **Step 4: Run the new test, verify it passes**

Run: `cd cli && pytest tests/test_sleeper_client.py::test_fetch_draft_picks_parses_player_team_from_metadata -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite and observe the fallout**

Run: `cd cli && pytest`
Expected: FAIL — every other `DraftPick(...)` construction site now raises
`TypeError: DraftPick.__init__() missing 1 required positional argument: 'player_team'`. This is
expected; the remaining steps fix each site.

- [ ] **Step 6: Thread `player_team` through the persisted-schema helpers**

In `cli/src/sleeper_agent/sleeper_client/sync.py`, bump the schema version:

```python
DRAFTS_SCHEMA_VERSION = 2
```

Update `draft_picks_to_dataframe`:

```python
def draft_picks_to_dataframe(picks: list[DraftPick]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "draft_id": [p.draft_id for p in picks],
            "round": [p.round for p in picks],
            "pick_no": [p.pick_no for p in picks],
            "draft_slot": [p.draft_slot for p in picks],
            "roster_id": [p.roster_id for p in picks],
            "player_id": [p.player_id for p in picks],
            "is_keeper": [p.is_keeper for p in picks],
            "picked_by": [p.picked_by for p in picks],
            "player_name": [p.player_name for p in picks],
            "player_position": [p.player_position for p in picks],
            "player_team": [p.player_team for p in picks],
        }
    )
```

Update `dataframe_to_draft_picks`:

```python
def dataframe_to_draft_picks(df: pl.DataFrame) -> list[DraftPick]:
    return [
        DraftPick(
            draft_id=row["draft_id"],
            round=row["round"],
            pick_no=row["pick_no"],
            draft_slot=row["draft_slot"],
            roster_id=row["roster_id"],
            player_id=row["player_id"],
            is_keeper=row["is_keeper"],
            picked_by=row["picked_by"],
            player_name=row["player_name"],
            player_position=row["player_position"],
            player_team=row["player_team"],
        )
        for row in df.to_dicts()
    ]
```

- [ ] **Step 7: Fix `test_sleeper_sync.py`'s two construction sites**

In `cli/tests/test_sleeper_sync.py`, `test_draft_picks_dataframe_round_trips`, add `player_team=`
to both picks (Ja'Marr Chase and Joe Burrow are both Bengals):

```python
def test_draft_picks_dataframe_round_trips() -> None:
    picks = [
        DraftPick(
            draft_id="did",
            round=1,
            pick_no=1,
            draft_slot=1,
            roster_id=3,
            player_id="7564",
            is_keeper=False,
            picked_by="u1",
            player_name="Ja'Marr Chase",
            player_position="WR",
            player_team="CIN",
        ),
        DraftPick(
            draft_id="did",
            round=4,
            pick_no=47,
            draft_slot=2,
            roster_id=8,
            player_id="6770",
            is_keeper=True,
            picked_by="u2",
            player_name="Joe Burrow",
            player_position="QB",
            player_team="CIN",
        ),
    ]

    df = sleeper_sync.draft_picks_to_dataframe(picks)
    result = sleeper_sync.dataframe_to_draft_picks(df)

    assert result == picks
```

- [ ] **Step 8: Fix `test_commands.py`'s four construction sites**

In `cli/tests/test_commands.py`, the `picks_2025` list (3 picks: Runner A/B/C) and `picks_2024`
list (1 pick: Runner C) in the keeper-eligibility fixture each need `player_team="SF"` added
(arbitrary but concrete — these are synthetic test fixtures, not real players). For example, the
first entry becomes:

```python
        DraftPick(
            draft_id="did",
            round=4,
            pick_no=40,
            draft_slot=1,
            roster_id=5,
            player_id="101",
            is_keeper=False,
            picked_by="u1",
            player_name="Runner A",
            player_position="RB",
            player_team="SF",
        ),
```

Apply the same `player_team="SF"` addition to the other 3 sites in that fixture (Runner B, Runner
C in `picks_2025`, and Runner C in `picks_2024`).

- [ ] **Step 9: Fix `test_draft_tools.py`'s `make_pick` helper and remaining direct site**

In `cli/tests/test_draft_tools.py`, extend `make_pick` with a defaulted `player_team` parameter
(test-helper convenience — the dataclass itself still requires the field, the helper just
supplies a default so existing callers don't need to change):

```python
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
```

Then fix the one remaining direct construction, `test_my_roster_positions_buckets_missing_position_as_unk`:

```python
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
```

(Leave the rest of the test body unchanged.)

- [ ] **Step 10: Run the full test suite, verify everything passes**

Run: `cd cli && pytest`
Expected: PASS (all tests, including the new one from Step 1)

- [ ] **Step 11: Commit**

```bash
git add cli/src/sleeper_agent/models/sleeper.py cli/src/sleeper_agent/sleeper_client/sync.py \
  cli/tests/test_sleeper_client.py cli/tests/test_sleeper_sync.py cli/tests/test_commands.py \
  cli/tests/test_draft_tools.py
git commit -m "Add DraftPick.player_team, bump DRAFTS_SCHEMA_VERSION to 2"
```

---

### Task 2: `slot_for_pick` snake-order function

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/board.py`
- Test: `cli/tests/test_draft_tools.py`

**Interfaces:**
- Produces: `slot_for_pick(pick_no: int, num_teams: int) -> int`, used by Task 3's `watch_picks`.

- [ ] **Step 1: Write the failing tests**

Add to `cli/tests/test_draft_tools.py` (near the other `board.py`-level tests, e.g. after
`compute_tiers`/`_is_tier_break` tests or near `my_roster_positions` tests):

```python
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
```

- [ ] **Step 2: Run them, verify they fail**

Run: `cd cli && pytest tests/test_draft_tools.py -k slot_for_pick -v`
Expected: FAIL — `ImportError` / `NameError: name 'slot_for_pick' is not defined` (add the import
at the top of the test file alongside the other `board` imports first, then re-run to confirm the
`NameError`/`ImportError` comes from the missing function itself, not a missing import).

- [ ] **Step 3: Implement `slot_for_pick`**

Add to `cli/src/sleeper_agent/draft_tools/board.py`, near `watch_board` (top-level function, no
class):

```python
def slot_for_pick(pick_no: int, num_teams: int) -> int:
    """Which draft slot owns a given overall pick number, standard snake order.

    Odd rounds go 1..num_teams ascending; even rounds reverse (num_teams..1).
    No 3rd-round-reversal — this league's drafts (and every mock run so far)
    use plain snake.
    """
    round_number = (pick_no - 1) // num_teams + 1
    pos_in_round = pick_no - (round_number - 1) * num_teams
    if round_number % 2 == 1:
        return pos_in_round
    return num_teams - pos_in_round + 1
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `cd cli && pytest tests/test_draft_tools.py -k slot_for_pick -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/board.py cli/tests/test_draft_tools.py
git commit -m "Add slot_for_pick snake-order helper"
```

---

### Task 3: `watch_picks` orchestration function

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/board.py`
- Test: `cli/tests/test_draft_tools.py`

**Interfaces:**
- Consumes: `slot_for_pick(pick_no: int, num_teams: int) -> int` (Task 2); `DraftPick` with
  `player_team` (Task 1); `_flush_print` (existing, in `board.py`); `fetch_draft_picks` (existing).
- Produces: `watch_picks(...)`, used by Task 5's `cmd_draft_watch_picks`. Signature:

```python
def watch_picks(
    draft_id: str,
    *,
    num_teams: int,
    draft_type: str,
    my_draft_slot: int | None,
    total_picks: int,
    render_full_board: Callable[[list[DraftPick]], str],
    base_url: str = SLEEPER_BASE_URL,
    poll_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
    render: Callable[[str], None] = _flush_print,
    fetch_picks: Callable[..., list[DraftPick]] = fetch_draft_picks,
) -> None:
```

`my_draft_slot` here is always a slot *number* representing "me" — the caller (Task 5) is
responsible for resolving it whether the user identified themselves via `--draft-slot` directly
or via `--me`/`--roster-id` (reverse-lookup through `slot_to_roster_id`). `watch_picks` itself
never deals with `roster_id`.

- [ ] **Step 1: Write the failing tests**

Add to `cli/tests/test_draft_tools.py`:

```python
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
```

- [ ] **Step 2: Run them, verify they fail**

Run: `cd cli && pytest tests/test_draft_tools.py -k watch_picks -v`
Expected: FAIL — `NameError: name 'watch_picks' is not defined` (add the import first, alongside
`watch_board`, then confirm the failure is about the missing function).

- [ ] **Step 3: Implement `watch_picks`**

Add to `cli/src/sleeper_agent/draft_tools/board.py`, after `watch_board`:

```python
def _render_pick_line(pick: DraftPick, my_draft_slot: int | None) -> str:
    name = pick.player_name or pick.player_id
    position = pick.player_position or "?"
    team = pick.player_team or "?"
    line = f"Pick {pick.pick_no} (slot {pick.draft_slot}): {name} ({position}, {team})"
    if my_draft_slot is not None and pick.draft_slot == my_draft_slot:
        line += " <== MY PICK"
    return line


def watch_picks(
    draft_id: str,
    *,
    num_teams: int,
    draft_type: str,
    my_draft_slot: int | None,
    total_picks: int,
    render_full_board: Callable[[list[DraftPick]], str],
    base_url: str = SLEEPER_BASE_URL,
    poll_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
    render: Callable[[str], None] = _flush_print,
    fetch_picks: Callable[..., list[DraftPick]] = fetch_draft_picks,
) -> None:
    """Stream one line per new pick; auto-render the full board the instant
    the next pick is mine.

    Deliberately lighter-weight than `watch_board`: it never reprints the
    whole board for picks that aren't mine, and only fetches/renders the
    board once per "my turn" (not on every poll while the human is still on
    the clock) — see `.claude/skills/draft.md`'s "Preferred live setup".
    """
    printed_count = 0
    announced_pick_no: int | None = None
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        picks = fetch_picks(draft_id, base_url=base_url)
        for pick in picks[printed_count:]:
            render(_render_pick_line(pick, my_draft_slot))
        printed_count = len(picks)

        if (
            draft_type == "snake"
            and my_draft_slot is not None
            and printed_count < total_picks
        ):
            next_pick_no = printed_count + 1
            if (
                slot_for_pick(next_pick_no, num_teams) == my_draft_slot
                and announced_pick_no != next_pick_no
            ):
                render(render_full_board(picks))
                announced_pick_no = next_pick_no

        if printed_count >= total_picks:
            return

        iteration += 1
        if max_iterations is None or iteration < max_iterations:
            sleep(poll_seconds)
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `cd cli && pytest tests/test_draft_tools.py -k watch_picks -v`
Expected: PASS (all 6 new tests)

- [ ] **Step 5: Run the full test suite**

Run: `cd cli && pytest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/board.py cli/tests/test_draft_tools.py
git commit -m "Add watch_picks: per-pick streaming with turn-triggered board render"
```

---

### Task 4: Extract `_resolve_draft_context` from `cmd_draft_board`

This is a behavior-preserving refactor — no new CLI-visible behavior. The existing
`test_cmd_draft_board_*` tests in `cli/tests/test_commands.py` are the safety net; the task is to
extract without changing what any of them observe.

**Files:**
- Modify: `cli/src/sleeper_agent/commands/draft_cmd.py`

**Interfaces:**
- Produces: `DraftContext` dataclass and `_resolve_draft_context(args, root, *, base_url) ->
  DraftContext | None`, used by Task 5's `cmd_draft_watch_picks`.

- [ ] **Step 1: Run the full test suite to establish the baseline**

Run: `cd cli && pytest tests/test_commands.py -k draft_board -v`
Expected: PASS (this is the baseline — all `cmd_draft_board` tests green before touching anything)

- [ ] **Step 2: Add the `Draft`/`DraftPick` imports**

In `cli/src/sleeper_agent/commands/draft_cmd.py`, add to the imports:

```python
from sleeper_agent.models.sleeper import Draft, DraftPick
```

- [ ] **Step 3: Add the `DraftContext` dataclass and `_resolve_draft_context` function**

Add near the top of `draft_cmd.py`, after the existing `_team_changes_by_sleeper_id` helper (i.e.
right before `cmd_draft_keepers`):

```python
@dataclass(frozen=True)
class DraftContext:
    draft_id: str
    value_season: str
    num_teams: int
    draft: Draft
    vorp_df: pl.DataFrame
    my_roster_id: int | None
    my_draft_slot: int | None
    requirement: RosterRequirement
    triaged_rookies: list[TriagedRookie]
    rookie_news: dict[str, list[str]]
    team_changes: dict[str, TeamChange]


def _resolve_draft_context(
    args: argparse.Namespace, root: Path, *, base_url: str
) -> DraftContext | None:
    """Shared setup for `draft board` and `draft watch-picks`: resolve the
    draft/value-season/num-teams (from --league-id or --draft-id), resolve
    "me" (--me/--roster-id/--draft-slot), and load VORP + rookie-watch +
    team-changes data. Prints its own error message and returns None on
    failure, same convention as the code it was extracted from.
    """
    if args.draft_id is not None:
        if args.value_season is None:
            print(
                "--value-season is required with --draft-id (e.g. for a Sleeper mock "
                "draft, there's no league to infer a season from)"
            )
            return None
        draft_id = args.draft_id
        value_season = args.value_season
        num_teams = args.num_teams
    else:
        league = fetch_league(args.league_id, base_url=base_url)
        if league.draft_id is None:
            print(f"league {args.league_id} has no draft_id")
            return None
        draft_id = league.draft_id
        value_season = args.value_season or league.season
        num_teams = max(league.settings.num_teams, 1)

    vorp_df = _read_vorp(root, value_season)
    if vorp_df is None:
        print(
            f"no VORP data for season {value_season} — run `stats vorp --season {value_season}` first"
        )
        return None

    draft = fetch_draft(draft_id, base_url=base_url)
    requirement = roster_requirement_from_draft(draft)
    my_roster_id: int | None = None
    my_draft_slot: int | None = None
    if args.draft_slot is not None:
        my_roster_id = draft.slot_to_roster_id.get(args.draft_slot)
        if my_roster_id is None:
            print(
                f"--draft-slot {args.draft_slot} is not in this draft's "
                f"slot_to_roster_id (valid slots: {sorted(draft.slot_to_roster_id)})"
            )
            return None
        my_draft_slot = args.draft_slot
    elif args.me:
        my_roster_id = ME_ROSTER_ID
    elif args.roster_id is not None:
        my_roster_id = args.roster_id

    players_df = _read_players(root)
    triaged_rookies = _triaged_rookies(root, players_df)
    rookie_news = _rookie_news_by_sleeper_id(root, triaged_rookies)
    team_changes = _team_changes_by_sleeper_id(root, value_season, players_df)
    if players_df is not None:
        vorp_df = filter_rostered(vorp_df, players_df)

    return DraftContext(
        draft_id=draft_id,
        value_season=value_season,
        num_teams=num_teams,
        draft=draft,
        vorp_df=vorp_df,
        my_roster_id=my_roster_id,
        my_draft_slot=my_draft_slot,
        requirement=requirement,
        triaged_rookies=triaged_rookies,
        rookie_news=rookie_news,
        team_changes=team_changes,
    )
```

Note: `dataclass` must already be imported in this file (`from dataclasses import dataclass`) — if
it isn't, add that import too.

- [ ] **Step 4: Rewrite `cmd_draft_board` to use the shared helper**

Replace the body of `cmd_draft_board` (currently lines ~266-369) with:

```python
def cmd_draft_board(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
    today: Callable[[], date] = date.today,
    max_watch_iterations: int | None = None,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    context = _resolve_draft_context(args, root, base_url=base_url)
    if context is None:
        return 1

    top_n = args.rounds * context.num_teams

    if args.watch:
        log_path = (
            decisions_dir(root)
            / context.value_season
            / f"{today().isoformat()}-draft-live.md"
        )
        watch_board(
            context.draft_id,
            context.vorp_df,
            base_url=base_url,
            log_path=log_path,
            max_iterations=max_watch_iterations,
            my_roster_id=context.my_roster_id,
            my_draft_slot=context.my_draft_slot,
            requirement=context.requirement if context.my_roster_id is not None else None,
            triaged_rookies=context.triaged_rookies,
            rookie_news_by_sleeper_id=context.rookie_news,
            team_changes=context.team_changes,
        )
        return 0

    picks = fetch_draft_picks(context.draft_id, base_url=base_url)
    board = board_view(context.vorp_df, picks, top_n=top_n)
    my_counts = (
        my_roster_positions(picks, context.my_roster_id, my_draft_slot=context.my_draft_slot)
        if context.my_roster_id is not None
        else None
    )
    rookie_watch: list[RookieWatchRow] | None = (
        rookie_watch_rows(context.triaged_rookies, picks, news_by_sleeper_id=context.rookie_news)
        if context.triaged_rookies
        else None
    )
    print(
        render_board(
            board,
            my_counts=my_counts,
            requirement=context.requirement if context.my_roster_id is not None else None,
            rookie_watch=rookie_watch,
            team_changes=context.team_changes,
        )
    )
    return 0
```

- [ ] **Step 5: Run the full test suite, verify no regressions**

Run: `cd cli && pytest`
Expected: PASS — every existing `test_cmd_draft_board_*` test still passes unchanged, proving the
extraction is behavior-preserving.

- [ ] **Step 6: Commit**

```bash
git add cli/src/sleeper_agent/commands/draft_cmd.py
git commit -m "Extract _resolve_draft_context from cmd_draft_board for reuse"
```

---

### Task 5: `cmd_draft_watch_picks` CLI command

**Files:**
- Modify: `cli/src/sleeper_agent/commands/draft_cmd.py`
- Test: `cli/tests/test_commands.py`

**Interfaces:**
- Consumes: `_resolve_draft_context`/`DraftContext` (Task 4), `watch_picks` (Task 3),
  `slot_for_pick` is used internally by `watch_picks`, not called directly here.
- Produces: `cmd_draft_watch_picks(args, *, repo_root=None, base_url=SLEEPER_BASE_URL,
  max_iterations=None) -> int`, wired to the `draft watch-picks` subcommand.

- [ ] **Step 1: Write the failing tests**

Add to `cli/tests/test_commands.py`, near the other `cmd_draft_board` tests (these use the same
`_league_payload`/`_draft_object_payload` helpers already defined in that file):

```python
def test_cmd_draft_watch_picks_streams_lines_and_renders_board_on_my_turn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        pl.DataFrame(
            {
                "sleeper_id": ["9"],
                "name": ["Available Player"],
                "position": ["RB"],
                "vorp_season": [10.0],
            }
        ),
        repo_root / "data" / "vorp" / "2025.parquet",
        schema_version=1,
    )

    seven_picks = [
        {
            "draft_id": "did1",
            "round": 1,
            "pick_no": n,
            "draft_slot": n,
            "roster_id": n,
            "player_id": str(n),
            "is_keeper": False,
            "picked_by": f"u{n}",
            "metadata": {
                "first_name": f"Player{n}",
                "last_name": "Test",
                "position": "RB",
                "team": "SF",
            },
        }
        for n in range(1, 8)
    ]
    eighth_pick = {
        "draft_id": "did1",
        "round": 1,
        "pick_no": 8,
        "draft_slot": 8,
        "roster_id": 5,
        "player_id": "8",
        "is_keeper": False,
        "picked_by": "u5",
        "metadata": {
            "first_name": "Mine",
            "last_name": "Guy",
            "position": "RB",
            "team": "SF",
        },
    }
    call_log = [seven_picks, seven_picks, seven_picks + [eighth_pick]]

    def handler(request: Request) -> Response:
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload(slot_to_roster_id={"8": 5}))
        if request.path == "/draft/did1/picks":
            return json_response(call_log.pop(0))
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id=None,
        draft_id="did1",
        rounds=15,
        value_season="2025",
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=8,
        poll_seconds=0.0,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_watch_picks(
            args, repo_root=repo_root, base_url=base_url, max_iterations=3
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Pick 1 (slot 1): Player1 Test (RB, SF)" in out
    assert "Pick 8 (slot 8): Mine Guy (RB, SF) <== MY PICK" in out
    assert out.count("Best available by value:") == 1


def test_cmd_draft_watch_picks_resolves_turn_slot_from_me_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        pl.DataFrame(
            {
                "sleeper_id": ["9"],
                "name": ["Available Player"],
                "position": ["RB"],
                "vorp_season": [10.0],
            }
        ),
        repo_root / "data" / "vorp" / "2025.parquet",
        schema_version=1,
    )
    my_pick = {
        "draft_id": "did1",
        "round": 1,
        "pick_no": 1,
        "draft_slot": 1,
        "roster_id": 5,  # ME_ROSTER_ID
        "player_id": "1",
        "is_keeper": False,
        "picked_by": "u5",
        "metadata": {"first_name": "Mine", "last_name": "Guy", "position": "RB", "team": "SF"},
    }
    call_log = [[], [my_pick]]

    def handler(request: Request) -> Response:
        if request.path == "/league/lid1":
            return json_response(_league_payload())
        if request.path == "/draft/did1":
            return json_response(_draft_object_payload(slot_to_roster_id={"1": 5}))
        if request.path == "/draft/did1/picks":
            return json_response(call_log.pop(0))
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id="lid1",
        draft_id=None,
        rounds=15,
        value_season=None,
        num_teams=12,
        me=True,
        roster_id=None,
        draft_slot=None,
        poll_seconds=0.0,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_watch_picks(
            args, repo_root=repo_root, base_url=base_url, max_iterations=2
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.count("Best available by value:") == 1  # rendered before any picks existed
    assert "Pick 1 (slot 1): Mine Guy (RB, SF) <== MY PICK" in out


def test_cmd_draft_watch_picks_skips_board_for_non_snake_draft(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = make_repo_root(tmp_path)
    from sleeper_agent.storage.parquet_store import write_table

    write_table(
        pl.DataFrame(
            {
                "sleeper_id": ["9"],
                "name": ["Available Player"],
                "position": ["RB"],
                "vorp_season": [10.0],
            }
        ),
        repo_root / "data" / "vorp" / "2025.parquet",
        schema_version=1,
    )

    def handler(request: Request) -> Response:
        if request.path == "/draft/did1":
            payload = _draft_object_payload(slot_to_roster_id={"8": 5})
            payload["type"] = "linear"
            return json_response(payload)
        if request.path == "/draft/did1/picks":
            return json_response([])
        raise AssertionError(f"unexpected path {request.path}")

    args = argparse.Namespace(
        league_id=None,
        draft_id="did1",
        rounds=15,
        value_season="2025",
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=8,
        poll_seconds=0.0,
    )
    with mock_http_server(handler) as base_url:
        exit_code = draft_cmd.cmd_draft_watch_picks(
            args, repo_root=repo_root, base_url=base_url, max_iterations=1
        )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Best available by value:" not in out


def test_cmd_draft_watch_picks_reports_missing_vorp(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)
    args = argparse.Namespace(
        league_id=None,
        draft_id="did1",
        rounds=15,
        value_season="2025",
        num_teams=12,
        me=False,
        roster_id=None,
        draft_slot=None,
        poll_seconds=0.0,
    )

    exit_code = draft_cmd.cmd_draft_watch_picks(args, repo_root=repo_root)

    assert exit_code == 1
```

- [ ] **Step 2: Run them, verify they fail**

Run: `cd cli && pytest tests/test_commands.py -k watch_picks -v`
Expected: FAIL — `AttributeError: module 'draft_cmd' has no attribute 'cmd_draft_watch_picks'`

- [ ] **Step 3: Implement `cmd_draft_watch_picks` and wire the subparser**

Add the `watch_picks` import to `draft_cmd.py`'s existing `from sleeper_agent.draft_tools.board
import (...)` block:

```python
from sleeper_agent.draft_tools.board import (
    RookieWatchRow,
    board_view,
    my_roster_positions,
    render_board,
    rookie_watch_rows,
    roster_requirement_from_draft,
    watch_board,
    watch_picks,
)
```

In `add_subcommands`, after the existing `board_parser.set_defaults(func=cmd_draft_board)` line,
add the new subparser:

```python
    watch_picks_parser = draft_subparsers.add_parser(
        "watch-picks",
        help="Live pick-by-pick tracker; auto-fetches the board the instant it's your turn",
    )
    watch_picks_source = watch_picks_parser.add_mutually_exclusive_group(required=True)
    watch_picks_source.add_argument("--league-id")
    watch_picks_source.add_argument(
        "--draft-id",
        help=(
            "Draft ID directly, bypassing league lookup — needed for a Sleeper mock "
            "draft, which has no league of its own. Requires --value-season."
        ),
    )
    watch_picks_parser.add_argument("--rounds", type=int, default=15)
    watch_picks_parser.add_argument("--value-season", default=None)
    watch_picks_parser.add_argument(
        "--num-teams",
        type=int,
        default=12,
        help="Only used with --draft-id, where there's no league.settings to read it from.",
    )
    watch_picks_parser.add_argument("--me", action="store_true")
    watch_picks_parser.add_argument("--roster-id", type=int, default=None)
    watch_picks_parser.add_argument(
        "--draft-slot",
        type=int,
        default=None,
        help=(
            "Resolve my roster_id from this draft's slot_to_roster_id map — needed for "
            "a mock draft (no stable roster_id across seasons), or as an alternative to "
            "--me/--roster-id in league mode."
        ),
    )
    watch_picks_parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="Picks-endpoint poll interval — cheap enough to poll faster than draft board --watch's 5s default.",
    )
    watch_picks_parser.set_defaults(func=cmd_draft_watch_picks)
```

Add `cmd_draft_watch_picks` after `cmd_draft_board`:

```python
def cmd_draft_watch_picks(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    base_url: str = SLEEPER_BASE_URL,
    max_iterations: int | None = None,
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    context = _resolve_draft_context(args, root, base_url=base_url)
    if context is None:
        return 1

    turn_detection_slot = context.my_draft_slot
    if turn_detection_slot is None and context.my_roster_id is not None:
        turn_detection_slot = next(
            (
                slot
                for slot, roster_id in context.draft.slot_to_roster_id.items()
                if roster_id == context.my_roster_id
            ),
            None,
        )

    top_n = args.rounds * context.num_teams

    def render_full_board(picks: list[DraftPick]) -> str:
        board = board_view(context.vorp_df, picks, top_n=top_n)
        my_counts = (
            my_roster_positions(
                picks, context.my_roster_id, my_draft_slot=context.my_draft_slot
            )
            if context.my_roster_id is not None
            else None
        )
        rookie_watch: list[RookieWatchRow] | None = (
            rookie_watch_rows(
                context.triaged_rookies, picks, news_by_sleeper_id=context.rookie_news
            )
            if context.triaged_rookies
            else None
        )
        return render_board(
            board,
            my_counts=my_counts,
            requirement=context.requirement if context.my_roster_id is not None else None,
            rookie_watch=rookie_watch,
            team_changes=context.team_changes,
        )

    watch_picks(
        context.draft_id,
        num_teams=context.num_teams,
        draft_type=context.draft.draft_type,
        my_draft_slot=turn_detection_slot,
        total_picks=args.rounds * context.num_teams,
        render_full_board=render_full_board,
        base_url=base_url,
        poll_seconds=args.poll_seconds,
        max_iterations=max_iterations,
    )
    return 0
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `cd cli && pytest tests/test_commands.py -k watch_picks -v`
Expected: PASS (all 4 new tests)

- [ ] **Step 5: Run the full test suite**

Run: `cd cli && pytest`
Expected: PASS

- [ ] **Step 6: Manually smoke-test against a real (or recent) draft ID**

Run (using a real past mock/league draft ID if one is handy, e.g. from a recent
`decisions/2026/*.md` entry):

```bash
cd cli && sleeper-agent draft watch-picks --draft-id <some-completed-draft-id> \
  --value-season 2025 --draft-slot 8 --poll-seconds 0.1
```

Expected: streams every historical pick as a line, then exits once it reaches the end (a
completed draft's pick count equals `rounds * num_teams`). Confirms the command runs against the
real Sleeper API, not just mocked tests.

- [ ] **Step 7: Commit**

```bash
git add cli/src/sleeper_agent/commands/draft_cmd.py cli/tests/test_commands.py
git commit -m "Add draft watch-picks CLI command"
```

---

### Task 6: Point the draft skill at the new command

**Files:**
- Modify: `.claude/skills/draft.md`
- Modify: `todo.md`

**Interfaces:** None (documentation only).

- [ ] **Step 1: Update `.claude/skills/draft.md`'s "Preferred live setup" bullet**

Find the bullet starting "**Preferred live setup: a `Monitor`-tool loop, not `--watch`
directly.**" (in the "During the draft" section) and replace its content to point at the new
command instead of a from-scratch bash script, while keeping the same core guidance (fold the
board-fetch into the same event, no separate round-trip; a `Monitor`-tool wrapper is still how
this surfaces as chat notifications). Rewrite it to something like:

```markdown
   - **Preferred live setup: `draft watch-picks` under a `Monitor`-tool wrapper.** Run
     `sleeper-agent draft watch-picks --draft-id <id> --value-season <year> --draft-slot <n>
     [--num-teams <n>]` (or `--league-id`/`--me` for the real league draft) under `Monitor` — it
     streams one line per pick (not the whole board, unlike `--watch`) and, the moment the next
     pick is mine, fetches and prints the full board inline in that same event — no separate
     round-trip. This replaced an ad hoc bash Monitor-loop script that used to be rewritten from
     scratch each draft (see `docs/superpowers/plans/2026-08-22-draft-watch-picks.md` and
     `decisions/2026/2026-08-22-draft-mock-draft-3-slot8.md`) — the snake-order math and turn
     detection are now tested project code (`draft_tools/board.py::slot_for_pick`/`watch_picks`),
     not something re-derived live. There is still no way to auto-submit the actual pick — this
     project's Sleeper client is read-only and Sleeper has no public pick-submission endpoint —
     so the human still clicks the pick in Sleeper; the goal is only to get the recommendation
     into their hands the instant it's computable.
```

- [ ] **Step 2: Remove the now-completed `todo.md` entry**

Delete the "## Live-draft pick tracker should be a tested CLI command, not an ad hoc script"
section from `todo.md` (it's done).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/draft.md todo.md
git commit -m "Point draft skill's live setup at the new draft watch-picks command"
```

## Self-review notes (for whoever executes this plan)

- Task 1's Step 8/9 fixture edits (`test_commands.py`, `test_draft_tools.py`) are described by
  pattern (add `player_team="SF"` / thread a new parameter) rather than reproducing every full
  existing test body verbatim, since those bodies are long and already exist unchanged in the
  repo — the instruction is precise about *what* to add and *where*, which is what a fresh
  implementer needs; don't re-derive the surrounding code, just add the one field to each existing
  construction call.
- Task 5's tests reuse `_draft_object_payload`/`_league_payload`/`mock_http_server`/`json_response`
  already defined at the top of `test_commands.py` — no new fixture helpers needed except the
  inline pick-payload dicts shown in each test.
