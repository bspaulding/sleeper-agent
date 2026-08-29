---
date: '2026-08-29'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved: []
related_wiki:
  - wiki/team/draft-strategy.md
---

## Summary

Direct mechanical follow-up to
[[2026-08-28-bigboard-qb-vorp-reliability-research]]: that entry found QB's year-over-year
`vorp_season` reliability (r≈0.40 among established starters) is much weaker than RB/WR/TE's
(r≈0.67-0.71), and treated that as judgment-calibration guidance for hand review. User's follow-up
question: shouldn't this be applied *mechanically* to the board's actual cross-position ordering,
not just used as permission to look harder at individual rows? Yes — this implements that:
`compute_vorp`/`compute_def_vorp` now emit a new `vorp_season_shrunk` field
(`= position's own r × raw vorp_season`), and `merge_bigboard` sorts/inserts/flags using that
shrunk value instead of raw `vorp_season`. This is a standard "regression to the mean" treatment:
a position whose raw season total predicts next year's less reliably gets less credit for an
extreme raw value on the board's shared cross-position scale. Verified against real 2025 data:
Josh Allen's raw vorp (91.7, QB's best) shrinks to 36.7 — now below WR5-tier talent (George
Pickens, 85.0) — while top RB/WR values only lose ~30% instead of QB's ~60%, exactly the
demotion-of-top-QBs effect expected going in.

## Reasoning

- **Why shrinkage, mechanically.** A low year-over-year r doesn't mean a position's performance is
  random — it means last year's raw total is a noisier estimate of next year's true value than a
  more reliable position's raw total is. The standard statistical correction is to regress each
  value toward the mean (here, replacement level, since `vorp_season` is already
  replacement-relative) by a factor of `1 - r`. Concretely: `vorp_season_shrunk = r * vorp_season`.
  This is the same operation for every position — QB just gets hit harder because its r is lower.
- **Which r to use.** The ≥8-games-both-years figures from the QB research (QB 0.40, RB 0.67, WR
  0.71, TE 0.68), not the inflated full-population numbers (QB 0.70, RB 0.68, WR 0.74, TE 0.73) —
  the filtered numbers reflect real-starter reliability, which is what a draft-relevant ranking
  cares about. DEF uses its own pooled full-population r (0.31,
  [[2026-08-28-bigboard-def-vorp-research-streaming-recommended]]) since a team defense doesn't
  have QB's "backup who never plays" problem the ≥8-games filter exists to fix — all 32 teams play
  essentially every scheduled game every year. DEF is excluded from the ordinal merge regardless
  (`POSITIONS_EXCLUDED_FROM_ORDINAL_MERGE`), so this doesn't affect anything today; computed for
  consistency in case a future `value rank --position DEF` or similar wants it.
- **New field, not a replacement — narrowly scoped to the ordinal board.** `vorp_season` is left
  untouched everywhere else (`value rank`, `value player`, `value roster`, waiver/free-agent
  recommendations, `stats vorp`'s printed top-20) — those consumers care about actual projected
  production, not cross-position draft-order comparability, and shrinking the number they display
  would misrepresent what it means. Only `merge_bigboard`'s sort/insert/flag logic reads
  `vorp_season_shrunk`. `data/vorp/<season>.parquet`'s schema bumped to version 2 (new column) —
  every reader of that file (`value_cmd`, `trade_cmd`, `waiver_cmd`, `freeagent_cmd`, `draft_cmd`,
  each keeping its own `VORP_SCHEMA_VERSION` constant, a pre-existing duplication not touched here)
  updated to expect version 2.
- **Real-data verification.** Re-ran `stats vorp --season 2025` after the code change. Top-5 raw
  vs. shrunk: Josh Allen 91.7→36.7, Drake Maye 77.0→30.8, Stafford 75.5→30.2, Trevor Lawrence
  67.3→26.9, Caleb Williams 40.8→16.3 — vs. top RB/WR barely moving in relative terms (McCaffrey
  280.9→188.2, Bijan Robinson 238.1→159.5, Puka Nacua 203.8→144.7). Confirms QB's top tier now
  reads roughly like current WR4-6/RB6-8 value instead of elite-skill-position value on the shared
  scale — the demotion effect the reliability research implied but the hand-review-only pass from
  [[2026-08-28-bigboard-qb-vorp-review-pass]] didn't actually apply.
- **This will flag nearly the entire board — that's expected, not a bug.** Running `value bigboard
  build --season 2025` with the new column flags 602 of 623 rows `[VORP CHANGED]`, since shrinkage
  changes every "vorp"-source row's stored number by construction. First instinct this session was
  to revert that as too disruptive — corrected: the flag mechanism is exactly the intended
  worklist for this kind of methodology change, per the `bigboard` skill's existing design (`stats
  vorp` updates the numbers, `bigboard build` flags what changed, a review pass — potentially a
  dedicated LLM pass with fresh context, given the volume here — resolves each flag). Reverting to
  dodge a large flag count defeats the mechanism's purpose.
- **Resolution strategy for the review pass, so it doesn't have to re-derive this from scratch:**
  shrinkage is a single constant multiplier per position, so it never changes order *within* a
  position — only how positions interleave with each other. That means most of the 602 flagged
  rows don't need independent judgment from first principles; the correct new cross-position order
  is mechanically determined by the shrunk values. The real judgment work is narrower: (1) identify
  which rows are genuinely hand-promoted overrides (Lamar Jackson, Joe Burrow, Daniel Jones,
  Jayden Daniels, Brock Purdy, Kyler Murray, Justin Fields, A.J. Brown, Jauan Jennings, Kenneth
  Walker III, Ashton Jeanty, Zach Charbonnet, and any others carrying an `[INJURY REVIEW`/`[ROLE-
  CHANGE REVIEW` marker with an explicit "moved from X -> here") and keep those pinned at their
  current rank rather than swept into a mechanical re-sort; (2) mechanically re-derive order for
  every other flagged row using `vorp_season_shrunk`; (3) spot-check that each pinned row's *new*
  neighbors (after the rest of the board shifts around it) still make sense, since the context a
  promotion was justified against may have changed.

## Data

- `cli/src/sleeper_agent/stats/vorp.py`: `POSITION_YOY_RELIABILITY` dict, `PlayerVorp.vorp_season_
  shrunk` field, computed inline in both `compute_vorp` and `compute_def_vorp`.
- `cli/src/sleeper_agent/commands/stats_cmd.py`: persists `vorp_season_shrunk` into
  `data/vorp/<season>.parquet`; `VORP_SCHEMA_VERSION` bumped 1 -> 2 (also bumped in `value_cmd.py`,
  `trade_cmd.py`, `waiver_cmd.py`, `freeagent_cmd.py`, `draft_cmd.py` — all independent copies of
  the same constant reading the same file).
- `cli/src/sleeper_agent/draft_tools/bigboard.py`: `merge_bigboard` reads `vorp_season_shrunk`
  instead of `vorp_season` for the `[VORP CHANGED]` comparison, the new-row sort, and
  `_insert_index_by_vorp`'s insertion point.
- Tests: `test_compute_vorp_shrinks_by_position_reliability`,
  `compute_def_vorp`'s existing test extended with a `vorp_season_shrunk` assertion, `_vorp_df`
  test helper in `test_bigboard.py` now produces `vorp_season_shrunk` directly (that's the only
  column `merge_bigboard` reads), ~25 unrelated `test_commands.py` fixtures bumped to
  `schema_version=2` for the same physical file. Full suite (424 tests), `ruff`, `ty` all pass.
- `stats vorp --season 2025` re-run for real, regenerating `data/vorp/2025.parquet` with the new
  column and schema version.
- `data/bigboard/2025.csv`: `value bigboard build --season 2025` run for real, producing 602
  flagged rows (0 added) — left in place as the review-pass worklist, not reverted.

## Outcome

Code and tests committed. `data/bigboard/2025.csv` currently carries 602 `[VORP CHANGED]` flags
from this run and is **not yet draft-usable** (`load_bigboard`'s hard-stop blocks on any unresolved
row) until a review pass resolves them — see [[2026-08-29-bigboard-vorp-shrinkage-review-pass]]
for that follow-up work, dispatched separately given the volume.
