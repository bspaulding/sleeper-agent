# Pre-draft Big Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace live VORP-sort + a separate unranked "Rookie watch" section with one materialized, LLM-reviewed ordinal ranking (`data/bigboard/<season>.csv`) that merges VORP-ranked veterans and triaged rookies, required (no fallback) by `draft board`/`watch-picks`.

**Architecture:** A new `draft_tools/bigboard.py` module owns the `BigboardRow` model, CSV load/save, and the mechanical merge logic that builds/refreshes the file. A new `value bigboard build --season <year>` CLI command drives that merge. A new `.claude/skills/bigboard.md` skill drives the LLM review pass that resolves flagged rows and logs reasoning via `decisions new --kind bigboard`. `draft_tools/board.py`'s rendering pipeline and `commands/draft_cmd.py`'s `_resolve_draft_context` are rewired to read the big board instead of raw VORP, dropping Rookie watch entirely.

**Tech Stack:** Python 3.11, polars (VORP/players/draft-picks parquet I/O), stdlib `csv` (bigboard file — deliberately not parquet, see spec §1), argparse (CLI), pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-draft-bigboard-design.md`

## Global Constraints

- No fallback: a missing `data/bigboard/<season>.csv`, or any row still carrying an unresolved `[NEEDS REVIEW...]`/`[VORP CHANGED...]` marker anywhere in the file, is a hard stop for `draft board`/`watch-picks` — never silently degrade to VORP-only behavior (spec §4).
- Never invent a synthetic VORP number for a rookie row — `vorp` stays `None`/null for `source="rookie"` rows everywhere (spec §1, preserves `PROJECT_PLAN.md` §6.3).
- `bigboard build` must never overwrite an existing row's `rank`, `rationale`, or `log_ref` — only add new rows and flag existing ones for review (spec §2).
- Wargame seed/mock-server rookie support is explicitly **out of scope for this plan** (spec §6 — a follow-up plan once this ships).

---

### Task 1: `BigboardRow` model, CSV load/save, review-state validation

**Files:**
- Create: `cli/src/sleeper_agent/draft_tools/bigboard.py`
- Test: `cli/tests/test_bigboard.py`

**Interfaces:**
- Produces: `BigboardRow` (frozen dataclass: `rank: int`, `player_id: str`, `name: str`, `position: str`, `source: Literal["vorp", "rookie"]`, `vorp: float | None`, `draft_round: int | None`, `rationale: str`, `log_ref: str | None`), `BigboardNotBuiltError`, `BigboardUnresolvedRowError`, `load_bigboard(root: Path, season: str) -> list[BigboardRow]`, `load_bigboard_for_build(root: Path, season: str) -> list[BigboardRow]`, `save_bigboard(root: Path, season: str, rows: Sequence[BigboardRow]) -> None`, `filter_off_roster(rows: Sequence[BigboardRow], players_df: pl.DataFrame) -> list[BigboardRow]`.

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_bigboard.py
from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from sleeper_agent.draft_tools.bigboard import (
    BigboardNotBuiltError,
    BigboardRow,
    BigboardUnresolvedRowError,
    filter_off_roster,
    load_bigboard,
    load_bigboard_for_build,
    save_bigboard,
)


def _row(**overrides) -> BigboardRow:
    base = dict(
        rank=1,
        player_id="7547",
        name="Amon-Ra St. Brown",
        position="WR",
        source="vorp",
        vorp=145.0,
        draft_round=None,
        rationale="",
        log_ref=None,
    )
    base.update(overrides)
    return BigboardRow(**base)


def test_load_bigboard_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(BigboardNotBuiltError):
        load_bigboard(tmp_path, "2026")


def test_load_bigboard_for_build_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_bigboard_for_build(tmp_path, "2026") == []


def test_save_then_load_round_trips_all_fields(tmp_path: Path) -> None:
    rows = [
        _row(rank=1, source="vorp", vorp=145.0, draft_round=None),
        _row(
            rank=2,
            player_id="9999",
            name="Rookie Player",
            position="RB",
            source="rookie",
            vorp=None,
            draft_round=2,
            rationale="placed R2",
            log_ref="2026-08-23-bigboard-initial-build",
        ),
    ]
    save_bigboard(tmp_path, "2026", rows)
    loaded = load_bigboard(tmp_path, "2026")
    assert loaded == rows


def test_load_bigboard_raises_on_needs_review_marker(tmp_path: Path) -> None:
    rows = [_row(rationale="[NEEDS REVIEW: new rookie placement]")]
    save_bigboard(tmp_path, "2026", rows)
    with pytest.raises(BigboardUnresolvedRowError) as exc_info:
        load_bigboard(tmp_path, "2026")
    assert exc_info.value.unresolved == rows


def test_load_bigboard_raises_on_vorp_changed_marker(tmp_path: Path) -> None:
    rows = [_row(rationale="[VORP CHANGED: 100.0 -> 120.0]")]
    save_bigboard(tmp_path, "2026", rows)
    with pytest.raises(BigboardUnresolvedRowError):
        load_bigboard(tmp_path, "2026")


def test_load_bigboard_for_build_does_not_raise_on_unresolved_rows(
    tmp_path: Path,
) -> None:
    rows = [_row(rationale="[NEEDS REVIEW: new rookie placement]")]
    save_bigboard(tmp_path, "2026", rows)
    assert load_bigboard_for_build(tmp_path, "2026") == rows


def test_load_bigboard_sorts_by_rank(tmp_path: Path) -> None:
    rows = [_row(rank=2, player_id="a"), _row(rank=1, player_id="b")]
    save_bigboard(tmp_path, "2026", rows)
    loaded = load_bigboard(tmp_path, "2026")
    assert [r.player_id for r in loaded] == ["b", "a"]


def test_filter_off_roster_drops_vorp_rows_with_no_nfl_team() -> None:
    rows = [
        _row(player_id="7547", source="vorp"),
        _row(player_id="9999", source="vorp"),
    ]
    players_df = pl.DataFrame(
        {"player_id": ["7547", "9999"], "team": ["DET", None]}
    )
    filtered = filter_off_roster(rows, players_df)
    assert [r.player_id for r in filtered] == ["7547"]


def test_filter_off_roster_never_drops_rookie_rows() -> None:
    rows = [_row(player_id="9999", source="rookie", vorp=None)]
    players_df = pl.DataFrame({"player_id": ["9999"], "team": [None]})
    filtered = filter_off_roster(rows, players_df)
    assert [r.player_id for r in filtered] == ["9999"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_bigboard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sleeper_agent.draft_tools.bigboard'`

- [ ] **Step 3: Write the implementation**

```python
# cli/src/sleeper_agent/draft_tools/bigboard.py
"""The pre-draft big board: one materialized, hand-reviewed ordinal ranking
merging VORP-ranked veterans and triaged rookies.

See docs/superpowers/specs/2026-08-23-draft-bigboard-design.md. Deliberately
CSV, not parquet like the rest of `data/` — this file is meant to be
reviewed and edited by an LLM (with human sign-off) between builds, so it
needs to stay plain-text and git-diffable.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import polars as pl

from sleeper_agent.config import data_dir

BIGBOARD_FIELDS = [
    "rank",
    "player_id",
    "name",
    "position",
    "source",
    "vorp",
    "draft_round",
    "rationale",
    "log_ref",
]

# A row carrying either marker is an unreviewed judgment gap — see the
# hard-stop rule in docs/superpowers/specs/2026-08-23-draft-bigboard-
# design.md §4. Whole-file, not just the top of the board.
REVIEW_MARKERS = ("[NEEDS REVIEW", "[VORP CHANGED")


@dataclass(frozen=True)
class BigboardRow:
    rank: int
    player_id: str
    name: str
    position: str
    source: Literal["vorp", "rookie"]
    vorp: float | None
    draft_round: int | None
    rationale: str
    log_ref: str | None


class BigboardNotBuiltError(Exception):
    def __init__(self, season: str) -> None:
        self.season = season
        super().__init__(
            f"data/bigboard/{season}.csv not found — run the bigboard skill "
            f"(or `sleeper-agent value bigboard build --season {season}`) first"
        )


class BigboardUnresolvedRowError(Exception):
    def __init__(self, season: str, unresolved: list[BigboardRow]) -> None:
        self.season = season
        self.unresolved = unresolved
        names = ", ".join(f"{row.name} (rank {row.rank})" for row in unresolved[:5])
        more = f" and {len(unresolved) - 5} more" if len(unresolved) > 5 else ""
        super().__init__(
            f"data/bigboard/{season}.csv has {len(unresolved)} unresolved row(s) "
            f"still flagged for review: {names}{more} — finish the bigboard "
            "skill's review pass before drafting"
        )


def _bigboard_path(root: Path, season: str) -> Path:
    return data_dir(root) / "bigboard" / f"{season}.csv"


def _is_unresolved(row: BigboardRow) -> bool:
    return any(marker in row.rationale for marker in REVIEW_MARKERS)


def _read_rows(path: Path) -> list[BigboardRow]:
    rows: list[BigboardRow] = []
    with path.open(newline="") as fh:
        for raw in csv.DictReader(fh):
            rows.append(
                BigboardRow(
                    rank=int(raw["rank"]),
                    player_id=raw["player_id"],
                    name=raw["name"],
                    position=raw["position"],
                    source=raw["source"],  # type: ignore[arg-type]
                    vorp=float(raw["vorp"]) if raw["vorp"] else None,
                    draft_round=int(raw["draft_round"])
                    if raw["draft_round"]
                    else None,
                    rationale=raw["rationale"],
                    log_ref=raw["log_ref"] or None,
                )
            )
    rows.sort(key=lambda r: r.rank)
    return rows


def load_bigboard_for_build(root: Path, season: str) -> list[BigboardRow]:
    """Raw load for `bigboard build`: empty (not an error) when no file
    exists yet (first-ever build), and never raises on unresolved rows —
    the whole point of a build run is to work with rows still flagged."""
    path = _bigboard_path(root, season)
    if not path.exists():
        return []
    return _read_rows(path)


def load_bigboard(root: Path, season: str) -> list[BigboardRow]:
    """Load for live consumption (`draft board`/`watch-picks`): hard-stops
    on a missing file or any unresolved row anywhere in it."""
    path = _bigboard_path(root, season)
    if not path.exists():
        raise BigboardNotBuiltError(season)
    rows = _read_rows(path)
    unresolved = [row for row in rows if _is_unresolved(row)]
    if unresolved:
        raise BigboardUnresolvedRowError(season, unresolved)
    return rows


def save_bigboard(root: Path, season: str, rows: Sequence[BigboardRow]) -> None:
    path = _bigboard_path(root, season)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=BIGBOARD_FIELDS)
        writer.writeheader()
        for row in rows:
            d = asdict(row)
            d["vorp"] = "" if row.vorp is None else row.vorp
            d["draft_round"] = "" if row.draft_round is None else row.draft_round
            d["log_ref"] = row.log_ref or ""
            writer.writerow(d)


def filter_off_roster(
    rows: Sequence[BigboardRow], players_df: pl.DataFrame
) -> list[BigboardRow]:
    """Drop `source="vorp"` rows for players with no current NFL team on
    record — same signal as `value.scoring.filter_rostered`, reimplemented
    here against `BigboardRow` instead of a VORP DataFrame. Never applied to
    `source="rookie"` rows: a rookie's `team` field is sourced differently
    (from the draft-picks crosswalk) and this filter was never applied to
    the old Rookie watch population either.
    """
    off_roster_ids = set(
        players_df.filter(pl.col("team").is_null() | (pl.col("team") == ""))[
            "player_id"
        ].to_list()
    )
    return [
        row
        for row in rows
        if row.source == "rookie" or row.player_id not in off_roster_ids
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_bigboard.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/bigboard.py cli/tests/test_bigboard.py
git commit -m "Add BigboardRow model, CSV load/save, and review-state validation"
```

---

### Task 2: Shared rookie-triage loader

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/rookies.py`
- Modify: `cli/src/sleeper_agent/commands/draft_cmd.py:202-215` (remove `_triaged_rookies`, replace its one call site)
- Test: `cli/tests/test_draft_tools.py` (add near existing `triage_rookies` tests)

Both `commands/value_cmd.py` (Task 4, new) and `commands/draft_cmd.py` (already) need the same "load draft-picks + players parquet, triage, best-effort-empty if either is missing" logic that today lives as a private `_triaged_rookies` helper inside `draft_cmd.py`. Promote it to `rookies.py` so both call sites share it; `draft_cmd.py`'s own copy is deleted here (its only caller, `_resolve_draft_context`, stops needing rookie data at all once Task 7 removes Rookie watch wiring — but do this promotion now, independently, so Task 4 has something to import).

**Interfaces:**
- Consumes: `sleeper_agent.storage.parquet_store.read_table`, `sleeper_agent.stats.draft_picks_sync.DRAFT_PICKS_SCHEMA_VERSION`, `sleeper_agent.sleeper_client.players.PLAYERS_SCHEMA_VERSION`, `sleeper_agent.config.data_dir`.
- Produces: `load_triaged_rookies(root: Path, season: str) -> list[TriagedRookie]` in `rookies.py`.

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_draft_tools.py — add near the existing triage_rookies tests
def test_load_triaged_rookies_best_effort_empty_when_draft_picks_missing(
    tmp_path: Path,
) -> None:
    from sleeper_agent.draft_tools.rookies import load_triaged_rookies

    assert load_triaged_rookies(tmp_path, "2026") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd cli && uv run pytest tests/test_draft_tools.py::test_load_triaged_rookies_best_effort_empty_when_draft_picks_missing -v`
Expected: FAIL — `ImportError: cannot import name 'load_triaged_rookies'`

- [ ] **Step 3: Add the loader to `rookies.py`**

Add to `cli/src/sleeper_agent/draft_tools/rookies.py` (below the existing `triage_rookies` function):

```python
from pathlib import Path

from sleeper_agent.config import data_dir
from sleeper_agent.sleeper_client.players import PLAYERS_SCHEMA_VERSION
from sleeper_agent.stats.draft_picks_sync import DRAFT_PICKS_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table


def load_triaged_rookies(root: Path, season: str) -> list[TriagedRookie]:
    """Load + triage rookies for `season`, best-effort empty (not an error)
    when `data/nfl/draft_picks.parquet` or `data/sleeper/players.parquet`
    hasn't been synced yet — shared by `value bigboard build` and (legacy)
    `draft board`'s Rookie watch rendering.
    """
    draft_picks_path = data_dir(root) / "nfl" / "draft_picks.parquet"
    players_path = data_dir(root) / "sleeper" / "players.parquet"
    if not draft_picks_path.exists() or not players_path.exists():
        return []
    draft_picks_df = read_table(
        draft_picks_path, expected_schema_version=DRAFT_PICKS_SCHEMA_VERSION
    ).filter(pl.col("season") == int(season))
    players_df = read_table(
        players_path, expected_schema_version=PLAYERS_SCHEMA_VERSION
    )
    return triage_rookies(draft_picks_df, players_df)
```

Add `import polars as pl` to the top of `rookies.py` if not already present (it isn't — check the current import block and add it alongside the existing `from dataclasses import dataclass` / `from sleeper_agent.models.sleeper import ...` lines).

Note the added `.filter(pl.col("season") == int(season))` — `_triaged_rookies` in `draft_cmd.py` never filtered by season before calling `triage_rookies` (a latent gap: `draft_picks.parquet` can hold multiple seasons via `stats draft-picks sync`, and `triage_rookies` itself doesn't filter by season either, per `rookies.py`'s current body — it triages every row it's handed regardless of `season` column). Filtering here is a real behavior improvement bundled into the promotion, not a no-op refactor; call this out explicitly in the commit message.

In `cli/src/sleeper_agent/commands/draft_cmd.py`, delete the `_triaged_rookies` function (lines 202-215) and its now-unused `_read_draft_picks` helper (lines 195-199) if nothing else in the file calls `_read_draft_picks` — grep first: `grep -n "_read_draft_picks" cli/src/sleeper_agent/commands/draft_cmd.py`. Replace the one call site in `_resolve_draft_context` (`triaged_rookies = _triaged_rookies(root, players_df)`) with `triaged_rookies = load_triaged_rookies(root, value_season)`, and update the import at the top from `from sleeper_agent.draft_tools.rookies import TriagedRookie, triage_rookies` to `from sleeper_agent.draft_tools.rookies import TriagedRookie, load_triaged_rookies`. (Task 7 removes this call site entirely along with the rest of Rookie watch wiring — this intermediate step just keeps the file working standalone between tasks.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -v -k triaged_rookies`
Expected: PASS. Also run the full existing suite to confirm the `draft_cmd.py` edit didn't break anything: `cd cli && uv run pytest tests/ -v -k rookie`

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/rookies.py cli/src/sleeper_agent/commands/draft_cmd.py cli/tests/test_draft_tools.py
git commit -m "Promote rookie-triage loading to a shared rookies.load_triaged_rookies"
```

---

### Task 3: Mechanical merge logic (`merge_bigboard`)

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/bigboard.py`
- Test: `cli/tests/test_bigboard.py`

**Interfaces:**
- Consumes: `BigboardRow` (Task 1), `TriagedRookie` (`draft_tools/rookies.py`, existing — fields `player: Player`, `draft_round: int`; `Player` has `.player_id`, `.name`, `.position`).
- Produces: `merge_bigboard(existing_rows: list[BigboardRow], vorp_df: pl.DataFrame, triaged_rookies: Sequence[TriagedRookie]) -> list[BigboardRow]`. `vorp_df` has columns `sleeper_id: str`, `name: str`, `position: str`, `vorp_season: float` (same shape `board.py`'s existing `board_view` already consumes).

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_bigboard.py — add below the Task 1 tests
from sleeper_agent.draft_tools.bigboard import merge_bigboard
from sleeper_agent.draft_tools.rookies import TriagedRookie
from sleeper_agent.models.sleeper import parse_player


def _vorp_df(*rows: tuple[str, str, str, float]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "sleeper_id": [r[0] for r in rows],
            "name": [r[1] for r in rows],
            "position": [r[2] for r in rows],
            "vorp_season": [r[3] for r in rows],
        }
    )


def _rookie(player_id: str, name: str, position: str, draft_round: int) -> TriagedRookie:
    player = parse_player(
        player_id,
        {
            "player_id": player_id,
            "full_name": name,
            "position": position,
            "team": "DET",
        },
    )
    return TriagedRookie(player=player, draft_round=draft_round)


def test_merge_bigboard_inserts_new_vorp_players_by_value_order() -> None:
    vorp_df = _vorp_df(
        ("1", "Player One", "RB", 100.0),
        ("2", "Player Two", "RB", 80.0),
        ("3", "Player Three", "RB", 60.0),
    )
    merged = merge_bigboard([], vorp_df, [])
    assert [r.player_id for r in merged] == ["1", "2", "3"]
    assert [r.rank for r in merged] == [1, 2, 3]
    assert all(r.source == "vorp" for r in merged)


def test_merge_bigboard_never_touches_existing_row_rank_or_rationale() -> None:
    existing = [
        BigboardRow(
            rank=1,
            player_id="2",
            name="Player Two",
            position="RB",
            source="vorp",
            vorp=80.0,
            draft_round=None,
            rationale="manually reordered above Player One, see log",
            log_ref="2026-08-01-bigboard-initial",
        )
    ]
    vorp_df = _vorp_df(("1", "Player One", "RB", 100.0), ("2", "Player Two", "RB", 80.0))
    merged = merge_bigboard(existing, vorp_df, [])
    kept = next(r for r in merged if r.player_id == "2")
    assert kept.rank == 1
    assert kept.rationale == "manually reordered above Player One, see log"
    assert kept.log_ref == "2026-08-01-bigboard-initial"
    new = next(r for r in merged if r.player_id == "1")
    assert new.rank == 2


def test_merge_bigboard_flags_material_vorp_change_without_reordering() -> None:
    existing = [
        BigboardRow(
            rank=1,
            player_id="1",
            name="Player One",
            position="RB",
            source="vorp",
            vorp=100.0,
            draft_round=None,
            rationale="",
            log_ref=None,
        )
    ]
    vorp_df = _vorp_df(("1", "Player One", "RB", 60.0))
    merged = merge_bigboard(existing, vorp_df, [])
    assert merged[0].rank == 1
    assert "[VORP CHANGED: 100.0 -> 60.0]" in merged[0].rationale


def test_merge_bigboard_does_not_flag_unchanged_vorp() -> None:
    existing = [
        BigboardRow(
            rank=1,
            player_id="1",
            name="Player One",
            position="RB",
            source="vorp",
            vorp=100.0,
            draft_round=None,
            rationale="",
            log_ref=None,
        )
    ]
    vorp_df = _vorp_df(("1", "Player One", "RB", 100.0))
    merged = merge_bigboard(existing, vorp_df, [])
    assert merged[0].rationale == ""


def test_merge_bigboard_inserts_new_rookie_flagged_for_review() -> None:
    vorp_df = _vorp_df(
        ("1", "Vet One", "RB", 100.0),
        ("2", "Vet Two", "RB", 80.0),
        ("3", "Vet Three", "RB", 60.0),
        ("4", "Vet Four", "RB", 40.0),
        ("5", "Vet Five", "RB", 20.0),
    )
    merged = merge_bigboard([], vorp_df, [_rookie("99", "Rookie RB", "RB", 1)])
    rookie_row = next(r for r in merged if r.player_id == "99")
    assert rookie_row.source == "rookie"
    assert rookie_row.vorp is None
    assert rookie_row.draft_round == 1
    assert rookie_row.rationale == "[NEEDS REVIEW: new rookie placement]"
    # Round-1 heuristic places it near the top of its position group, not at the end.
    assert rookie_row.rank < len(merged)


def test_merge_bigboard_is_idempotent_on_rookie_already_present() -> None:
    vorp_df = _vorp_df(("1", "Vet One", "RB", 100.0))
    first = merge_bigboard([], vorp_df, [_rookie("99", "Rookie RB", "RB", 1)])
    reviewed = [
        r if r.player_id != "99" else BigboardRow(**{**r.__dict__, "rationale": "reviewed: kept at rank 2"})
        for r in first
    ]
    second = merge_bigboard(reviewed, vorp_df, [_rookie("99", "Rookie RB", "RB", 1)])
    kept = next(r for r in second if r.player_id == "99")
    assert kept.rationale == "reviewed: kept at rank 2"


def test_merge_bigboard_renumbers_ranks_contiguously_from_one() -> None:
    vorp_df = _vorp_df(("1", "A", "RB", 100.0), ("2", "B", "RB", 80.0))
    merged = merge_bigboard([], vorp_df, [])
    assert [r.rank for r in merged] == [1, 2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_bigboard.py -v -k merge_bigboard`
Expected: FAIL — `ImportError: cannot import name 'merge_bigboard'`

- [ ] **Step 3: Implement `merge_bigboard`**

Add to `cli/src/sleeper_agent/draft_tools/bigboard.py`:

```python
from dataclasses import replace

from sleeper_agent.draft_tools.rookies import TriagedRookie

# Rough starting point only — flagged [NEEDS REVIEW] every time, so
# precision doesn't matter much. Maps a rookie's real NFL draft round to
# how far into their position's VORP-ranked group to insert them, per
# wiki/team/rookie-evaluation.md's round/position hit-rate table (round 1
# rookies are the strongest bets, so they land higher).
_ROOKIE_ROUND_PERCENTILE: dict[int, float] = {1: 0.2, 2: 0.45, 3: 0.7}
_DEFAULT_ROOKIE_PERCENTILE = 0.7


def _insert_index_by_vorp(rows: list[BigboardRow], vorp: float) -> int:
    for i, row in enumerate(rows):
        if row.source == "vorp" and row.vorp is not None and row.vorp < vorp:
            return i
    return len(rows)


def _rookie_insert_index(rows: list[BigboardRow], rookie: TriagedRookie) -> int:
    position_indices = [
        i
        for i, row in enumerate(rows)
        if row.source == "vorp" and row.position == rookie.player.position
    ]
    if not position_indices:
        return len(rows)
    percentile = _ROOKIE_ROUND_PERCENTILE.get(
        rookie.draft_round, _DEFAULT_ROOKIE_PERCENTILE
    )
    offset = min(int(len(position_indices) * percentile), len(position_indices) - 1)
    return position_indices[offset]


def _renumber(rows: list[BigboardRow]) -> list[BigboardRow]:
    return [replace(row, rank=i) for i, row in enumerate(rows, start=1)]


def merge_bigboard(
    existing_rows: list[BigboardRow],
    vorp_df: pl.DataFrame,
    triaged_rookies: Sequence[TriagedRookie],
) -> list[BigboardRow]:
    """Mechanical half of `bigboard build` (spec §2). Never reorders or
    edits an existing row's `rank`/`rationale`/`log_ref` beyond appending a
    `[VORP CHANGED...]` flag — placement judgment (resolving that flag,
    positioning a `[NEEDS REVIEW...]` rookie) is the LLM's job, done via the
    `bigboard` skill, not this function.
    """
    existing_ids = {row.player_id for row in existing_rows}
    rows = list(existing_rows)

    vorp_by_id = {r["sleeper_id"]: r["vorp_season"] for r in vorp_df.to_dicts()}
    for i, row in enumerate(rows):
        if row.source != "vorp":
            continue
        new_vorp = vorp_by_id.get(row.player_id)
        if new_vorp is not None and row.vorp is not None and new_vorp != row.vorp:
            flag = f"[VORP CHANGED: {row.vorp:.1f} -> {new_vorp:.1f}]"
            rationale = f"{row.rationale} {flag}".strip()
            rows[i] = replace(row, vorp=new_vorp, rationale=rationale)

    new_vorp_rows = [
        r
        for r in vorp_df.sort("vorp_season", descending=True).to_dicts()
        if r["sleeper_id"] not in existing_ids
    ]
    for r in new_vorp_rows:
        insert_at = _insert_index_by_vorp(rows, r["vorp_season"])
        rows.insert(
            insert_at,
            BigboardRow(
                rank=0,
                player_id=r["sleeper_id"],
                name=r["name"],
                position=r["position"],
                source="vorp",
                vorp=r["vorp_season"],
                draft_round=None,
                rationale="",
                log_ref=None,
            ),
        )
        existing_ids.add(r["sleeper_id"])

    for rookie in triaged_rookies:
        if rookie.player.player_id in existing_ids:
            continue
        insert_at = _rookie_insert_index(rows, rookie)
        rows.insert(
            insert_at,
            BigboardRow(
                rank=0,
                player_id=rookie.player.player_id,
                name=rookie.player.name,
                position=rookie.player.position,
                source="rookie",
                vorp=None,
                draft_round=rookie.draft_round,
                rationale="[NEEDS REVIEW: new rookie placement]",
                log_ref=None,
            ),
        )
        existing_ids.add(rookie.player.player_id)

    return _renumber(rows)
```

Add `Sequence` to the existing `from collections.abc import Sequence` import (already present from Task 1) and `TriagedRookie` to a new import line.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_bigboard.py -v`
Expected: PASS (16 tests total: 9 from Task 1 + 7 from this task)

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/bigboard.py cli/tests/test_bigboard.py
git commit -m "Add merge_bigboard: mechanical new-player insertion and change flagging"
```

---

### Task 4: `value bigboard build` CLI command

**Files:**
- Modify: `cli/src/sleeper_agent/commands/value_cmd.py`
- Test: `cli/tests/test_commands.py`

**Interfaces:**
- Consumes: `bigboard.load_bigboard_for_build`, `bigboard.merge_bigboard`, `bigboard.save_bigboard` (Tasks 1/3), `rookies.load_triaged_rookies` (Task 2), existing `_read_vorp`-equivalent pattern (this file's own `VorpNotComputedError` + `_read_vorp`, already present at `value_cmd.py:38-46,73-78`).

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_commands.py — add near the other `value` command tests.
# Follow this file's existing fixture-writing helpers (search for how
# other tests in this file write a vorp parquet fixture via `stats vorp`'s
# schema/`_write_vorp_fixture`-style helper, or `read_table`/`write_table`
# directly against `VORP_SCHEMA_VERSION`) for the vorp_df setup below —
# reuse whatever helper the nearby `value rank`/`value roster` tests use
# rather than duplicating one.

def test_cmd_value_bigboard_build_creates_file_from_scratch(tmp_path: Path) -> None:
    from sleeper_agent.commands.value_cmd import cmd_value_bigboard_build
    from sleeper_agent.draft_tools.bigboard import load_bigboard_for_build

    _write_vorp_fixture(  # reuse existing helper; write two vorp rows
        tmp_path,
        "2026",
        [
            {"sleeper_id": "1", "name": "Player One", "position": "RB", "vorp_season": 100.0},
            {"sleeper_id": "2", "name": "Player Two", "position": "WR", "vorp_season": 80.0},
        ],
    )

    args = argparse.Namespace(season="2026")
    exit_code = cmd_value_bigboard_build(args, repo_root=tmp_path)

    assert exit_code == 0
    rows = load_bigboard_for_build(tmp_path, "2026")
    assert [r.player_id for r in rows] == ["1", "2"]


def test_cmd_value_bigboard_build_reports_missing_vorp(tmp_path: Path) -> None:
    from sleeper_agent.commands.value_cmd import cmd_value_bigboard_build

    args = argparse.Namespace(season="2026")
    exit_code = cmd_value_bigboard_build(args, repo_root=tmp_path)
    assert exit_code == 1


def test_bigboard_build_subcommand_is_registered() -> None:
    parser = build_parser()  # reuse this file's existing top-level parser builder
    args = parser.parse_args(["value", "bigboard", "build", "--season", "2026"])
    assert args.func.__name__ == "cmd_value_bigboard_build"
    assert args.season == "2026"
```

Adjust the fixture-writing helper name/signature to match whatever this file's existing `value rank`/`value roster` tests actually use (read `test_commands.py`'s existing `value` tests before writing this step — do not invent a new fixture-writing pattern if one already exists).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_commands.py -v -k bigboard_build`
Expected: FAIL — `ImportError: cannot import name 'cmd_value_bigboard_build'`

- [ ] **Step 3: Implement the command**

Add to `cli/src/sleeper_agent/commands/value_cmd.py`:

```python
from sleeper_agent.draft_tools.bigboard import (
    load_bigboard_for_build,
    merge_bigboard,
    save_bigboard,
)
from sleeper_agent.draft_tools.rookies import load_triaged_rookies
```

In `add_subcommands`, after the existing `roster_parser` block:

```python
    bigboard_parser = value_subparsers.add_parser(
        "bigboard", help="Pre-draft big board (merged VORP + rookie ranking)"
    )
    bigboard_subparsers = bigboard_parser.add_subparsers(dest="bigboard_command")
    bigboard_build_parser = bigboard_subparsers.add_parser(
        "build", help="Mechanically merge new VORP/rookie data into the big board"
    )
    bigboard_build_parser.add_argument("--season", required=True)
    bigboard_build_parser.set_defaults(func=cmd_value_bigboard_build)
```

New command function (place near `cmd_value_rank`):

```python
def cmd_value_bigboard_build(
    args: argparse.Namespace, *, repo_root: Path | None = None
) -> int:
    root = repo_root if repo_root is not None else find_repo_root(Path.cwd())
    try:
        vorp_df = _read_vorp(root, args.season)
    except VorpNotComputedError as exc:
        print(str(exc))
        return 1

    existing = load_bigboard_for_build(root, args.season)
    triaged_rookies = load_triaged_rookies(root, args.season)
    merged = merge_bigboard(existing, vorp_df, triaged_rookies)
    save_bigboard(root, args.season, merged)

    added = len(merged) - len(existing)
    flagged = [
        row
        for row in merged
        if "[NEEDS REVIEW" in row.rationale or "[VORP CHANGED" in row.rationale
    ]
    print(
        f"data/bigboard/{args.season}.csv: {len(merged)} rows "
        f"({added} added this run, {len(flagged)} flagged for review)"
    )
    for row in flagged[:20]:
        print(f"  rank {row.rank}: {row.name} — {row.rationale}")
    if len(flagged) > 20:
        print(f"  ...and {len(flagged) - 20} more")
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_commands.py -v -k bigboard_build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/commands/value_cmd.py cli/tests/test_commands.py
git commit -m "Add value bigboard build command"
```

---

### Task 5: `decisions new --kind bigboard`

**Files:**
- Modify: `cli/src/sleeper_agent/commands/decisions_cmd.py`
- Modify: wherever `DecisionKind` is defined (grep first: `grep -rn "class DecisionKind" cli/src/`)
- Test: `cli/tests/test_commands.py` (or wherever existing `decisions new --kind` tests live — grep `test.*decisions_new` first)

- [ ] **Step 1: Write the failing test**

```python
# add near existing `decisions new` tests, following their exact pattern
def test_decisions_new_accepts_bigboard_kind() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["decisions", "new", "--kind", "bigboard", "--slug", "test", "--season", "2026"]
    )
    assert args.kind == "bigboard"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd cli && uv run pytest tests/test_commands.py -v -k decisions_new_accepts_bigboard`
Expected: FAIL — argparse rejects `bigboard` as an invalid `--kind` choice

- [ ] **Step 3: Add `bigboard` to `DecisionKind`**

Find the enum (`grep -rn "class DecisionKind" cli/src/sleeper_agent/`) and add a `BIGBOARD = "bigboard"` member alongside the existing `DRAFT`/`KEEPER`/`TRADE`/`WAIVER`/`FREEAGENT` members, matching whatever naming convention (e.g. `DRAFT = "draft"`) the existing members use exactly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_commands.py -v -k decisions`
Expected: PASS, no regressions on existing decision-kind tests

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Add bigboard as a decisions new --kind choice"
```

---

### Task 6: Rewire `draft_tools/board.py` to consume `BigboardRow`, remove Rookie watch

**Files:**
- Modify: `cli/src/sleeper_agent/draft_tools/board.py` (whole-file rewrite of the functions listed below)
- Modify: `cli/tests/test_draft_tools.py` (update/remove tests listed below)

This is the highest-blast-radius task in the plan — read it in full before starting.

**Interfaces:**
- Consumes: `BigboardRow` (Task 1).
- Produces (signature changes from current `board.py`):
  - `bigboard_view(bigboard_rows: Sequence[BigboardRow], drafted_picks: list[DraftPick], *, top_n: int = DEFAULT_TOP_N) -> list[BigboardRow]` — replaces `board_view(vorp_df, ...)`.
  - `compute_tiers(board: Sequence[BigboardRow]) -> dict[str, int]` — same name, new param type; skips `source="rookie"` rows.
  - `render_board(board: Sequence[BigboardRow], *, my_counts=None, requirement=None, team_changes=None, injury_statuses=None) -> str` — drops the `rookie_watch` parameter entirely; rookie rows render inline with a `[ROOKIE R<n>]` tag instead of `vorp=`/`tier=`.
  - `render_board_for_picks(bigboard_rows: Sequence[BigboardRow], picks, *, top_n=..., my_roster_id=None, my_draft_slot=None, requirement=None, team_changes=None, injury_statuses=None) -> str` — drops `triaged_rookies`/`rookie_news_by_sleeper_id` params.
  - `watch_board(draft_id, bigboard_rows: Sequence[BigboardRow], *, ...)` — same as today minus `triaged_rookies`/`rookie_news_by_sleeper_id` params, `vorp_df` renamed to `bigboard_rows`.
  - `watch_picks` — **unchanged signature** (it never took `vorp_df` directly; only its caller's `render_full_board` closure changes, in Task 7).
- Removed entirely: `RookieWatchRow`, `rookie_watch_rows`.

- [ ] **Step 1: Update `test_draft_tools.py` for the new signatures (write failing tests first)**

Replace every `vorp_df`-based board fixture in this file with a `list[BigboardRow]` fixture. Two fully-worked examples — apply the same transformation to the rest of the named tests below:

```python
# Before (current test_board_view_excludes_drafted_and_kept_players, ~line 336):
def test_board_view_excludes_drafted_and_kept_players() -> None:
    vorp_df = pl.DataFrame(
        {"sleeper_id": ["1", "2", "3"], "name": ["A", "B", "C"],
         "position": ["RB", "RB", "RB"], "vorp_season": [30.0, 20.0, 10.0]}
    )
    picks = [_pick(pick_no=1, player_id="2")]
    result = board_view(vorp_df, picks)
    assert result["sleeper_id"].to_list() == ["1", "3"]

# After:
def test_bigboard_view_excludes_drafted_and_kept_players() -> None:
    rows = [
        _bigboard_row(rank=1, player_id="1", vorp=30.0),
        _bigboard_row(rank=2, player_id="2", vorp=20.0),
        _bigboard_row(rank=3, player_id="3", vorp=10.0),
    ]
    picks = [_pick(pick_no=1, player_id="2")]
    result = bigboard_view(rows, picks)
    assert [r.player_id for r in result] == ["1", "3"]
```

Add this helper near the top of the test file's existing fixture helpers (alongside wherever `_pick` is already defined):

```python
def _bigboard_row(
    *,
    rank: int,
    player_id: str,
    name: str | None = None,
    position: str = "RB",
    source: str = "vorp",
    vorp: float | None = 0.0,
    draft_round: int | None = None,
    rationale: str = "",
    log_ref: str | None = None,
) -> BigboardRow:
    return BigboardRow(
        rank=rank,
        player_id=player_id,
        name=name or f"Player {player_id}",
        position=position,
        source=source,
        vorp=vorp,
        draft_round=draft_round,
        rationale=rationale,
        log_ref=log_ref,
    )
```

Add `from sleeper_agent.draft_tools.bigboard import BigboardRow` to this test file's imports.

Apply the same `vorp_df` → `list[_bigboard_row(...)]` and `board_view` → `bigboard_view` transformation to: `test_board_view_respects_top_n`, `test_render_board_formats_ranked_lines`, `test_render_board_without_annotation_is_unchanged`, `test_render_board_with_annotation_adds_summary_tags_and_tiers`, `test_render_board_annotation_requires_both_counts_and_requirement`, `test_watch_board_only_rerenders_when_drafted_ids_change`, `test_watch_board_works_without_a_log_path`, `test_watch_board_annotates_when_my_roster_id_given`, `test_watch_board_without_my_roster_id_is_unannotated`, `test_watch_board_threads_team_changes_through_to_render_board`, `test_watch_board_without_team_changes_omits_moved_tag`, `test_render_board_injury_status_tags_only_flagged_players`, `test_render_board_injury_tag_combines_with_moved_tag`, `test_render_board_without_injury_statuses_is_unchanged`, `test_watch_board_threads_injury_statuses_through_to_render_board`, `test_compute_tiers_increments_only_past_a_big_gap`, `test_compute_tiers_is_independent_per_position`, `test_compute_tiers_treats_non_positive_vorp_as_always_a_break` (these three: change `board.filter(...)`-style polars fixtures to `[_bigboard_row(...), ...]` lists, `compute_tiers` now takes the list directly).

**Delete** these tests entirely (the feature they cover is removed): `test_watch_board_threads_rookie_watch_through_and_excludes_drafted_ones`, `test_watch_board_without_triaged_rookies_omits_rookie_watch`, `test_rookie_watch_rows_excludes_already_drafted_triaged_rookies`, `test_rookie_watch_rows_attaches_news_excerpt_by_sleeper_id`, `test_rookie_watch_rows_empty_news_when_no_lookup_given`, `test_render_board_rookie_watch_section_present_only_when_supplied`, `test_render_board_rookie_watch_section_omitted_for_empty_list`, `test_render_board_rookie_watch_rows_have_no_vorp_or_tier_fields`.

Add these new tests for the rookie-row-inline behavior that replaces Rookie watch:

```python
def test_render_board_renders_rookie_row_with_rookie_tag_not_vorp() -> None:
    board = [
        _bigboard_row(rank=1, player_id="1", source="rookie", vorp=None, draft_round=2),
    ]
    rendered = render_board(board)
    assert "[ROOKIE R2]" in rendered
    assert "vorp=" not in rendered


def test_render_board_rookie_row_gets_need_tag_but_no_tier() -> None:
    board = [
        _bigboard_row(rank=1, player_id="1", position="RB", source="rookie", vorp=None, draft_round=1),
    ]
    rendered = render_board(
        board,
        my_counts={},
        requirement=RosterRequirement(hard_min={"RB": 2}, flex_capacity=0),
    )
    assert "[NEED]" in rendered
    assert "tier=" not in rendered


def test_compute_tiers_skips_rookie_rows() -> None:
    board = [
        _bigboard_row(rank=1, player_id="1", position="RB", source="vorp", vorp=100.0),
        _bigboard_row(rank=2, player_id="2", position="RB", source="rookie", vorp=None),
    ]
    tiers = compute_tiers(board)
    assert "2" not in tiers
    assert tiers["1"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -v`
Expected: FAIL across most board-related tests (old signatures still in place)

- [ ] **Step 3: Rewrite `board.py`**

Replace the file's content from `RookieWatchRow` (line 40) through `render_board_for_picks` (line 288) with:

```python
def board_view_placeholder_removed() -> None:  # DELETE this marker, see below
    pass
```

(That marker line is not real code — it exists only to mark the deletion boundary for this plan's reviewer; delete `RookieWatchRow`, `rookie_watch_rows`, `board_view`, `compute_tiers`, `_is_tier_break` stays, `render_board`, `render_board_for_picks` and replace with the following, keeping `_is_tier_break` unchanged where it already is:)

```python
def bigboard_view(
    bigboard_rows: Sequence[BigboardRow],
    drafted_picks: list[DraftPick],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> list[BigboardRow]:
    drafted_ids = {pick.player_id for pick in drafted_picks}
    available = [row for row in bigboard_rows if row.player_id not in drafted_ids]
    return available[:top_n]


def compute_tiers(board: Sequence[BigboardRow]) -> dict[str, int]:
    tiers: dict[str, int] = {}
    by_position: dict[str, list[BigboardRow]] = {}
    for row in board:
        if row.source != "vorp":
            continue
        by_position.setdefault(row.position, []).append(row)
    for rows in by_position.values():
        rows.sort(key=lambda r: r.vorp or 0.0, reverse=True)
        tier = 1
        prev_vorp: float | None = None
        for row in rows:
            if prev_vorp is not None and _is_tier_break(prev_vorp, row.vorp or 0.0):
                tier += 1
            tiers[row.player_id] = tier
            prev_vorp = row.vorp
    return tiers


def render_board(
    board: Sequence[BigboardRow],
    *,
    my_counts: dict[str, int] | None = None,
    requirement: RosterRequirement | None = None,
    team_changes: dict[str, TeamChange] | None = None,
    injury_statuses: dict[str, str] | None = None,
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
    team_changes = team_changes or {}
    injury_statuses = injury_statuses or {}
    for rank, row in enumerate(board, start=1):
        if row.source == "rookie":
            line = f"{rank:2d}. {row.name:<25} {row.position:<3} [ROOKIE R{row.draft_round}]"
        else:
            line = f"{rank:2d}. {row.name:<25} {row.position:<3} vorp={row.vorp:7.1f}"
        if annotation is not None:
            counts, req = annotation
            tag = position_tag(row.position, counts.get(row.position, 0), req)
            if row.source == "vorp":
                tier = tiers.get(row.player_id, 1)
                line += f" tier={tier} [{tag}]"
            else:
                line += f" [{tag}]"
        change = team_changes.get(row.player_id)
        if change is not None:
            line += f" [MOVED: {change.old_team}→{change.new_team}]"
        status = injury_statuses.get(row.player_id)
        if status is not None:
            line += f" [INJ: {status}]"
        lines.append(line)
    return "\n".join(lines)


def render_board_for_picks(
    bigboard_rows: Sequence[BigboardRow],
    picks: Sequence[DraftPick],
    *,
    top_n: int = DEFAULT_TOP_N,
    my_roster_id: int | None = None,
    my_draft_slot: int | None = None,
    requirement: RosterRequirement | None = None,
    team_changes: dict[str, TeamChange] | None = None,
    injury_statuses: dict[str, str] | None = None,
) -> str:
    picks_list = list(picks)
    board = bigboard_view(bigboard_rows, picks_list, top_n=top_n)
    my_counts = (
        my_roster_positions(picks_list, my_roster_id, my_draft_slot=my_draft_slot)
        if my_roster_id is not None
        else None
    )
    return render_board(
        board,
        my_counts=my_counts,
        requirement=requirement if my_roster_id is not None else None,
        team_changes=team_changes,
        injury_statuses=injury_statuses,
    )
```

Update `watch_board`'s signature: rename its `vorp_df: pl.DataFrame` parameter to `bigboard_rows: Sequence[BigboardRow]`, remove the `triaged_rookies`/`rookie_news_by_sleeper_id` parameters, and update its one internal call to `render_board_for_picks` to pass `bigboard_rows` positionally instead of `vorp_df` and drop the two removed kwargs. `watch_picks` itself needs no changes.

Add `from sleeper_agent.draft_tools.bigboard import BigboardRow` to `board.py`'s imports; remove `from sleeper_agent.draft_tools.rookies import TriagedRookie` (no longer used in this file) and `import polars as pl` if nothing else in the file still uses `pl` after this rewrite (check — `board_view`/`compute_tiers` were the only polars users; confirm with `grep -n "pl\." cli/src/sleeper_agent/draft_tools/board.py` after the edit).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_draft_tools.py -v`
Expected: PASS, zero failures, zero `rookie_watch`-named tests remaining

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/draft_tools/board.py cli/tests/test_draft_tools.py
git commit -m "Rewire board.py rendering pipeline to consume BigboardRow, remove Rookie watch"
```

---

### Task 7: Rewire `commands/draft_cmd.py` to require the big board

**Files:**
- Modify: `cli/src/sleeper_agent/commands/draft_cmd.py`
- Modify: `cli/tests/test_commands.py`

**Interfaces:**
- Consumes: `bigboard.load_bigboard`, `bigboard.BigboardNotBuiltError`, `bigboard.BigboardUnresolvedRowError`, `bigboard.filter_off_roster` (Task 1); `board.bigboard_view`/`render_board_for_picks`/`watch_board` (Task 6).
- Produces: `DraftContext.bigboard_rows: list[BigboardRow]` replacing `DraftContext.vorp_df`; `DraftContext` drops `triaged_rookies`/`rookie_news` fields entirely.

- [ ] **Step 1: Update tests for the new hard-stop behavior (write failing tests first)**

Rename `test_cmd_draft_board_reports_missing_vorp` (line ~2193) to `test_cmd_draft_board_reports_missing_bigboard` and change its assertion from checking for the VORP-missing message to the bigboard one:

```python
def test_cmd_draft_board_reports_missing_bigboard(tmp_path: Path) -> None:
    # same setup this test already has (a fetch_draft/fetch_league stub, no
    # data/bigboard/<season>.csv written) — keep everything except the
    # assertion below
    ...
    exit_code = cmd_draft_board(args, repo_root=tmp_path, base_url=..., today=...)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "data/bigboard/2026.csv not found" in captured.out
```

Apply the same rename+assertion-swap pattern to `test_cmd_draft_watch_picks_reports_missing_vorp` (line ~2860) → `test_cmd_draft_watch_picks_reports_missing_bigboard`.

Add a new test for the unresolved-row hard-stop:

```python
def test_cmd_draft_board_reports_unresolved_bigboard_rows(tmp_path: Path) -> None:
    # write a data/bigboard/2026.csv (via bigboard.save_bigboard) containing
    # one row with rationale="[NEEDS REVIEW: new rookie placement]", plus
    # whatever league/draft fetch stubs the neighboring tests already use
    ...
    exit_code = cmd_draft_board(args, repo_root=tmp_path, base_url=..., today=...)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "unresolved row" in captured.out
```

**Delete** these tests (Rookie watch is gone): `test_cmd_draft_board_prints_rookie_watch_section_when_draft_picks_data_present`, `test_cmd_draft_board_rookie_watch_excludes_already_drafted_rookie`, `test_cmd_draft_board_omits_rookie_watch_when_no_draft_picks_data`, `test_cmd_draft_board_watch_threads_rookie_watch_into_decision_log`.

For every remaining test that currently writes a `data/vorp/<season>.parquet` fixture as its board's data source (`test_cmd_draft_board_prints_available_players`, `test_cmd_draft_board_exclude_players_drops_projected_keepers`, `test_cmd_draft_board_tags_live_sleeper_injury_designations`, `test_cmd_draft_board_excludes_players_with_no_nfl_team`, `test_cmd_draft_board_tags_triaged_role_changer`, `test_cmd_draft_board_omits_moved_tag_when_no_stats_data`, `test_cmd_draft_board_watch_threads_moved_tag_into_decision_log`, `test_cmd_draft_board_watch_writes_decision_log`, `test_cmd_draft_board_with_draft_id_skips_league_lookup`, `test_cmd_draft_board_annotates_with_me_flag`, `test_cmd_draft_board_annotates_with_roster_id_flag`, `test_cmd_draft_board_annotates_with_draft_slot_in_mock_mode`, `test_cmd_draft_board_reports_unresolvable_draft_slot`, `test_cmd_draft_board_with_draft_id_requires_value_season`, `test_cmd_draft_watch_picks_streams_lines_and_renders_board_on_my_turn`, `test_cmd_draft_watch_picks_resolves_turn_slot_from_me_flag`, `test_cmd_draft_watch_picks_skips_board_for_non_snake_draft`, `test_cmd_draft_watch_picks_uses_draft_object_num_teams_not_flag`, `test_cmd_draft_watch_picks_uses_draft_object_rounds_for_total_picks`, `test_cmd_draft_watch_picks_reports_unusable_draft_geometry`, `test_cmd_draft_watch_picks_warns_when_roster_id_has_no_draft_slot`, `test_cmd_draft_watch_picks_rejects_negative_poll_seconds`): **also write** a corresponding `data/bigboard/<season>.csv` fixture (via `bigboard.save_bigboard`, built from the same player rows the test's VORP fixture already uses, `source="vorp"`, sequential `rank`, empty `rationale`) alongside the existing VORP fixture — the VORP fixture stays (some of these tests, like the injury/moved-tag ones, may still need `data/sleeper/players.parquet`/stats fixtures for annotation, which are unaffected by this change) but the board's ranking now comes from the new bigboard fixture, not the VORP one directly. Read each test's current body before editing to confirm exactly what it asserts and keep those assertions intact — this task only changes *how the ranked list is sourced*, not what each test is verifying.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_commands.py -v -k "draft_board or draft_watch_picks"`
Expected: FAIL — `_resolve_draft_context` still reads `data/vorp/`, ignores any bigboard fixture

- [ ] **Step 3: Rewrite `draft_cmd.py`**

In `_resolve_draft_context`, replace:

```python
    vorp_df = _read_vorp(root, value_season)
    if vorp_df is None:
        print(
            f"no VORP data for season {value_season} — run `stats vorp --season {value_season}` first"
        )
        return None
```

with:

```python
    try:
        bigboard_rows = load_bigboard(root, value_season)
    except (BigboardNotBuiltError, BigboardUnresolvedRowError) as exc:
        print(str(exc))
        return None
```

Delete the `_triaged_rookies`/`_rookie_news_by_sleeper_id` calls and the block that assigns `triaged_rookies`/`rookie_news`:

```python
    players_df = _read_players(root)
    triaged_rookies = _triaged_rookies(root, players_df)
    rookie_news = _rookie_news_by_sleeper_id(root, triaged_rookies)
    team_changes = _team_changes_by_sleeper_id(root, value_season, players_df)
    if players_df is not None:
        vorp_df = filter_rostered(vorp_df, players_df)
```

replace with:

```python
    players_df = _read_players(root)
    team_changes = _team_changes_by_sleeper_id(root, value_season, players_df)
    if players_df is not None:
        bigboard_rows = filter_off_roster(bigboard_rows, players_df)
```

Update the `--exclude-players` block right below it — it currently filters `vorp_df` with a polars `.filter(~pl.col("sleeper_id").is_in(excluded))`; change to a list comprehension against `bigboard_rows`:

```python
    excluded = parse_excluded_players(getattr(args, "exclude_players", None))
    if excluded:
        bigboard_rows = [row for row in bigboard_rows if row.player_id not in excluded]
```

Update `DraftContext` (remove `vorp_df`, `triaged_rookies`, `rookie_news` fields; add `bigboard_rows: list[BigboardRow]`) and its construction at the end of `_resolve_draft_context` accordingly.

Update `cmd_draft_board`'s `watch_board(...)` call: replace `context.vorp_df` with `context.bigboard_rows`, delete the `triaged_rookies=`/`rookie_news_by_sleeper_id=` kwargs.

Update `_render_context_board`: replace `context.vorp_df` with `context.bigboard_rows`, delete the same two kwargs from its `render_board_for_picks(...)` call.

Update imports at the top: replace `from sleeper_agent.value.scoring import (filter_rostered, injury_statuses, recent_news_excerpt)` with `from sleeper_agent.value.scoring import (injury_statuses, recent_news_excerpt)` (keep `recent_news_excerpt` — still used by nothing now that `_rookie_news_by_sleeper_id` is deleted; grep to confirm and drop it too if genuinely unused: `grep -n "recent_news_excerpt" cli/src/sleeper_agent/commands/draft_cmd.py`). Delete the `from sleeper_agent.draft_tools.rookies import TriagedRookie, load_triaged_rookies` import (no longer used in this file after this task — `load_triaged_rookies` moved its only remaining caller to `value_cmd.py` in Task 4). Add `from sleeper_agent.draft_tools.bigboard import (BigboardNotBuiltError, BigboardRow, BigboardUnresolvedRowError, filter_off_roster, load_bigboard)`. Add `from sleeper_agent.draft_tools.board import bigboard_view` only if this file calls it directly anywhere (it doesn't currently — `render_board_for_picks`/`watch_board` call it internally — skip this import unless a later step needs it).

Also delete `_read_vorp` and `VORP_SCHEMA_VERSION` from this file if nothing else in it still uses them (`grep -n "_read_vorp\|VORP_SCHEMA_VERSION" cli/src/sleeper_agent/commands/draft_cmd.py` — `cmd_draft_keepers` uses `_read_vorp` too, at line 408, so **keep both** — this task only removes the `_resolve_draft_context` call site, not the helper itself).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_commands.py -v -k "draft_board or draft_watch_picks or draft_keepers"`
Expected: PASS across all board/watch-picks/keepers tests, zero rookie-watch tests remaining

Then run the full suite once to catch anything missed: `cd cli && uv run pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add cli/src/sleeper_agent/commands/draft_cmd.py cli/tests/test_commands.py
git commit -m "Rewire draft_cmd.py to require the big board, drop VORP-direct + Rookie watch"
```

---

### Task 8: `bigboard` skill

**Files:**
- Create: `.claude/skills/bigboard.md`

- [ ] **Step 1: Write the skill file**

```markdown
---
name: bigboard
description: Build or refresh the pre-draft big board (data/bigboard/<season>.csv) — merges VORP-ranked veterans with triaged rookies into one ordinal ranking, resolving ties and rookie placement via LLM judgment informed by recent bigboard decision-log entries and fresh news. Use before a draft, or any time news/injury/depth-chart signal changes enough to warrant a re-sweep.
---

# bigboard

Builds/refreshes `data/bigboard/<season>.csv`, the single ordinal ranking `draft board`/
`watch-picks` require at draft time (see
`docs/superpowers/specs/2026-08-23-draft-bigboard-design.md`). Splits mechanical work (adding
new players, flagging changes) from judgment work (placement, tie-breaking) — this skill drives
the judgment half.

## When to run this

- Before any draft (real or mock/wargame) — a required prerequisite, same footing as `stats vorp`.
- Any time news/injury/depth-chart signal changes enough that the current ranking might be
  stale (a manual trigger — there's no automated re-sweep schedule).

## Process

1. Run `sleeper-agent value bigboard build --season <year>` (from `cli/`). This mechanically
   merges in anything new — a VORP-ranked veteran not yet on the board gets inserted by value
   order (no judgment needed), a newly-triaged rookie gets inserted at a rough starting slot and
   flagged `[NEEDS REVIEW: new rookie placement]`, and any existing row whose VORP changed since
   last build gets `[VORP CHANGED: <old> -> <new>]` appended to its rationale — without moving
   it. The command prints every flagged row.
2. Read the most recent `--kind bigboard` decision-log entries for this season
   (`decisions/<season>/`) — continuity matters: don't re-litigate a call that was already
   deliberately reconsidered and kept. Check current news/injury/wiki context (especially
   `wiki/team/rookie-evaluation.md` for rookie judgment, `wiki/team/roster-philosophy.md` for
   roster-construction framing) for anything flagged.
3. For every row still carrying `[NEEDS REVIEW...]` or `[VORP CHANGED...]`: make the call.
   - New rookie: place it using the same reasoning `draft.md` used to describe live (tier
     cliffs at the position, the round's historical hit rate, `wiki/team/rookie-evaluation.md`'s
     framework) — just done here, calmly, pre-draft, instead of live under a clock. Edit the
     row's `rank` directly (renumber neighbors if you're inserting between two adjacent ranks —
     open the CSV, it's a small hand-editable file) and replace the `[NEEDS REVIEW...]` marker
     in `rationale` with a one-line reason.
   - VORP-changed veteran: decide whether the new VORP value actually changes where they belong
     relative to neighbors. If yes, move the row and update `rationale`. If no, still clear the
     `[VORP CHANGED...]` marker and say so explicitly (e.g. `"reconsidered 2026-09-01, no
     change: still ahead of the next tier"`) — the distinction between "never revisited" and
     "revisited and kept" has to survive, not just the changes.
   - Any near-tied cluster you notice while reviewing (even if nothing flagged it): resolve it
     into a strict order now. This is the whole point — a tie resolved here never costs a live
     pick's clock again.
4. Run `sleeper-agent decisions new --kind bigboard --slug <slug> --season <year>` and fill in
   Summary/Reasoning/Data: what changed, why, and what was explicitly reconsidered-and-kept.
5. Update every row you touched this pass to set `log_ref` to this entry's date/slug.
6. Re-run `sleeper-agent value bigboard build --season <year>` once more as a final check — it
   should report 0 flagged rows. If it doesn't, you missed one; go back to step 3.

## Known sharp edges

(none yet — fill in as real usage surfaces issues, same convention as `wargame.md`)
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/bigboard.md
git commit -m "Add /bigboard skill: runbook for building/refreshing the pre-draft big board"
```

---

### Task 9: Update `draft.md` to build and use the big board

**Files:**
- Modify: `.claude/skills/draft.md`

- [ ] **Step 1: Update step 1 (pre-draft prep)**

In the "Live snake draft" section's numbered step 1, replace:

```
1. Before the draft: review `value rank --top 50` (and by position) to build a mental tier list.
   Check `wiki/team/roster-philosophy.md`, `wiki/team/draft-strategy.md`, `wiki/team/defense-strategy.md`,
   `wiki/team/rookie-evaluation.md`, `wiki/team/role-changers.md`, and
   `wiki/team/keeper-strategy.md` if they exist for standing strategy notes from prior seasons
   and general drafting theory. Also run, if not already done for this season: `stats
   draft-picks sync --season <year>` (feeds Rookie watch), `wiki scaffold rookies --season
   <year>` and `wiki scaffold role-changers --season <prior-year>` (stub any missing pages for
   the triaged lists), and `wiki sync-frontmatter` after any `sleeper players sync` (keeps
   `nfl_team` current on already-scaffolded pages — it's only set once at scaffold time
   otherwise). Rookie watch and the `MOVED` tag are silently absent from `draft board` if this
   data hasn't been synced, not an error — check for them explicitly rather than assuming.
```

with:

```
1. Before the draft: check `wiki/team/roster-philosophy.md`, `wiki/team/draft-strategy.md`,
   `wiki/team/defense-strategy.md`, `wiki/team/rookie-evaluation.md`, `wiki/team/role-changers.md`,
   and `wiki/team/keeper-strategy.md` if they exist for standing strategy notes from prior
   seasons and general drafting theory. Run, if not already done for this season: `stats
   draft-picks sync --season <year>` (feeds the big board's rookie half), `wiki scaffold
   rookies --season <year>` and `wiki scaffold role-changers --season <prior-year>` (stub any
   missing pages for the triaged lists), and `wiki sync-frontmatter` after any `sleeper players
   sync` (keeps `nfl_team` current on already-scaffolded pages — it's only set once at scaffold
   time otherwise). Then run the **`bigboard` skill** to build/refresh
   `data/bigboard/<year>.csv` — this is what replaced "review `value rank --top 50` to build a
   mental tier list": the tier list is now a materialized, reviewed artifact, not something
   reconstructed in your head every draft. `draft board`/`watch-picks` require this file to
   exist and have zero rows flagged for review — see
   `docs/superpowers/specs/2026-08-23-draft-bigboard-design.md`.
```

- [ ] **Step 2: Update step 2's board description**

Find the bullet describing `draft board --league-id <id> --rounds 15 --me [--watch]`'s output
("shows best-available by value, already excluding every drafted and kept player"). After that
sentence, add: "The ranked order comes from the pre-draft big board (§1), not a live VORP
sort — ties and rookie placement were already resolved during the `bigboard` skill's review, so
there's nothing left to deliberate on the order itself at pick time; only the NEED/FLEX/SURPLUS
tags and tier numbers (for VORP-sourced rows) are computed live, against your current roster."

Find and delete the sub-bullet describing the "Rookie watch" section (the one starting "Given
the pre-draft sync in step 1, the same output also carries a **Rookie watch** section...") —
rookies now render inline in the main list with a `[ROOKIE R<n>]` tag instead of `tier=N`, so
there's no separate section to describe.

- [ ] **Step 3: Update step 3's rookie-weighing bullet**

Find the bullet starting "**Weighing a Rookie watch entry against the main board.**" Replace its
entire body with:

```
   - **Rookies are already placed in the main board** — the reasoning chain that used to run
     live here (round-hit-rate weighting, tier-cliff comparison, best-ball-forgives-a-slow-start
     shading, news-line tie-breaking) now runs during the `bigboard` skill's pre-draft review
     instead, calmly and without a clock. If a rookie's board position ever looks wrong mid-draft,
     that's a `bigboard` skill problem to fix after the draft (or before the next one), not
     something to re-litigate live.
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/draft.md
git commit -m "Update draft.md: build/use the big board instead of live VORP-sort + Rookie watch"
```

---

## Self-Review Notes

- **Spec coverage:** §1 (schema) → Task 1. §2 (build command mechanics) → Tasks 1, 3, 4. §3
  (skill) → Task 8. §4 (live consumption, hard-stop, Rookie watch removal) → Tasks 6, 7. §5
  (draft.md) → Task 9. §6 (wargame tie-in) → explicitly out of scope, called out in Global
  Constraints. §7 (tests) → covered per-task. §8 (rollout) → not a task; it's validated by the
  next wargame run, per the spec's own DoD pattern (no separate sign-off task needed).
- **Placeholder scan:** the one literal placeholder-looking line (`board_view_placeholder_removed`
  in Task 6 Step 3) is intentional — it's a reviewer-facing deletion marker, not code left in the
  final file; the step's prose says explicitly to delete it.
- **Type consistency:** `BigboardRow` fields are identical across Tasks 1, 3, 6, 7 (`rank`,
  `player_id`, `name`, `position`, `source`, `vorp`, `draft_round`, `rationale`, `log_ref`).
  `bigboard_view`/`load_bigboard`/`merge_bigboard`/`filter_off_roster` signatures are used
  consistently in Tasks 6 and 7 exactly as defined in Tasks 1 and 3.
