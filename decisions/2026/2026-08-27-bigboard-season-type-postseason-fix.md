---
date: '2026-08-27'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Christian McCaffrey
  - Kyren Williams
  - Travis Etienne
  - D'Andre Swift
  - Kyle Pitts
  - Josh Allen
  - Drake Maye
  - Caleb Williams
  - Ja'Marr Chase
related_wiki:
  - team/bigboard-external-comparison.md
  - team/roster-philosophy.md
---

## Summary

Follow-up to `decisions/2026/2026-08-27-bigboard-external-consensus-comparison.md`, which
surfaced implausible `games_played` values (18–21, over a 17-game season) while comparing our
bigboard against external consensus rankings. Root-caused, fixed, and the full pipeline
(`stats vorp` → `value bigboard build`) re-run for `--value-season 2025`.

## Reasoning

**Root cause.** `stats/vorp.py::_season_totals` summed every row of the cached weekly-stats file
per player with no filter on `season_type`. `data/stats/weekly/2025.parquet` mixes `REG` (18,540
rows) and `POST` (882 rows) — confirmed via `nflreadpy.load_player_stats`'s default
`summary_level="week"`, which returns both season types in one file, and confirmed `season_type`
was referenced nowhere else in the codebase (`grep -rn "season_type" src/` — zero hits before this
fix). Net effect: any player whose team made a playoff run got 1–4 extra games silently folded
into their "season" total, inflating `season_points` and therefore `vorp_season` (VORP is computed
off season totals, not a per-game rate).

**Fix.** `_season_totals` now filters to `season_type == "REG"` when that column is present
(fixture DataFrames in existing tests lack it and are treated as already-regular-season, so no
test churn). Added `test_compute_vorp_excludes_postseason_rows` exercising a player with a mixed
REG/POST weekly history. Full suite: 370 passed.

**Data regeneration.** Re-ran `stats vorp --season 2025`, then `value bigboard build --season
2025`. The build flagged 599 of 616 rows `[VORP CHANGED: <old> -> <new>]` (mechanical half of the
skill — `merge_bigboard` updates the value but never reorders on its own). Before resolving,
verified whether any veteran (`source="vorp"`) row had ever been manually promoted/demoted away
from pure VORP order (the documented "sharp edge" in `.claude/skills/bigboard.md`, which a blind
resort would silently undo): parsed each row's old value out of its `[VORP CHANGED: old -> new]`
text and checked the pre-fix order was strictly non-increasing. It was, with one tie at the exact
replacement level (rank 393/394, both `-142.3`) — no evidence any veteran row was ever hand-reordered.
On that basis, resolved all 599 flags mechanically: re-sorted every `source="vorp"` row by its
fresh `vorp_season` value, cleared the `[VORP CHANGED...]` marker back to an empty `rationale`
(matching the pre-existing convention — no vorp row carried hand-written rationale before this),
and set `log_ref` to this entry. `source="rookie"` rows (14, all already resolved in the
2026-08-24 initial build) and 3 veteran rows absent from the fresh VORP data entirely (Jarquez
Hunter, Frank Gore Jr., Jordan James — ranks 354/368/393, deep bench, never realistically drafted
in a 15-round league) were left untouched, pinned at their existing rank, same as `merge_bigboard`
itself would do for a player it can't find in `vorp_df` (the "nothing removes a stale row" sharp
edge — not this fix's job to address).

## Data

Per-player impact, the players flagged as "overvalued vs. external consensus" in the prior
comparison entry:

| Player | Games (all→REG) | VORP (all→REG) |
|---|---|---|
| Drake Maye | 21→17 | 139.2→77.0 |
| Kyren Williams | 20→17 | 180.3→129.6 |
| Josh Allen | 18→16 | 137.1→91.7 |
| Christian McCaffrey | 19→17 | 316.1→280.9 |
| Caleb Williams | 19→17 | 73.7→40.8 |
| Travis Etienne | 18→17 | 134.2→118.2 |
| D'Andre Swift | 18→16 | 113.1→94.9 |

Unaffected (their teams didn't make the playoffs, or already had exactly 17 games) — Ja'Marr
Chase, Bijan Robinson, Jahmyr Gibbs among them — actually *gained* a couple of VORP points, since
the replacement-level baseline itself dropped once other positions' postseason inflation was
removed (VORP is relative to a shared per-position baseline).

**Top-12 position mix, unchanged by this fix:** RB 8 / WR 3 / TE 1 / QB 0, both before and after.
Confirms (per the prior comparison entry) that the RB-heavy top-of-board pattern is not an
artifact of this bug — it survives the fix intact, and traces to the real, symmetric
replacement-rank math (RB and WR share the same rank-35 replacement cutoff in this league's
slots; RB's replacement level is simply worse in points-per-game terms, `~8.4 ppg vs. WR's ~10.5
ppg`). Real positional scarcity, not something to fix here.

## Outcome

`data/bigboard/2025.csv`: 616 rows, 0 flagged for review, ranks strictly ordinal 1..616 (`value
bigboard build --season 2025` confirms). `draft board` loads cleanly. Test suite: 370 passed.

Not done here, and still worth doing before Saturday's draft: a normal `bigboard` skill pass
(news/injury/depth-chart judgment) is a separate concern from this mechanical VORP fix — this
entry only resolved the flags this fix itself created, it didn't re-litigate placement on
anything else.
