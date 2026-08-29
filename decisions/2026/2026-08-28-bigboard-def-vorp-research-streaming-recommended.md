---
date: '2026-08-28'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved: []
related_wiki:
  - wiki/team/draft-strategy.md
---

## Summary

Closed out `todo.md`'s "build a real DEF ranking pass" item (originally filed from
[[2026-08-29-draft-mock-draft-7-slot8]] point (e)). Built real team-DEF VORP from actual nflverse
team-level stats and the league's live `scoring_settings` (`stats/vorp.py`'s new
`compute_def_vorp`, wired into `stats vorp` and `stats sync`'s new `data/stats/team/<season>.parquet`).
Then researched whether that ranking (or any other available signal) is predictive enough to
justify feeding it into the ordinal `data/bigboard/<season>.csv` the way every other position is.
**It isn't** — DEF's own VORP has weak year-over-year correlation (r≈0.25-0.31 depending on
metric, vs. RB VORP's r≈0.68 baseline), no alternative signal tested (pressure rate, sack rate,
points allowed, turnover points) meaningfully beats it, and in-season, the upcoming opponent's own
offensive strength predicts a defense's weekly fantasy score far better than the defense's own
recent form does (r≈0.32 vs r≈0.09). **Conclusion: DEF is a streaming position, not a draft-capital
one — data confirms `draft.md`'s existing hunch rather than overturning it.** `stats vorp`'s new
DEF computation is kept (it's correct, real infrastructure — useful raw signal and a building block
for a future streaming tool) but is explicitly excluded from the ordinal merge
(`bigboard.POSITIONS_EXCLUDED_FROM_ORDINAL_MERGE`), which the mechanical-merge failure described
below made a hard requirement, not just a judgment call. That failure also exposed and led to
fixing a second, pre-existing, position-agnostic bug in the board's insertion logic — see below.

## Reasoning

- **The build.** `compute_def_vorp` (`cli/src/sleeper_agent/stats/vorp.py`) scores each of the 32
  teams' own defensive production per game — `def_sacks`, `def_interceptions`,
  `fumble_recovery_opp`, `def_tds`, `def_safeties`, and blocked kicks (`def_fg_blocks` +
  `def_pat_blocks` + `def_punt_blocks`) from nflverse's `load_team_stats`, plus the league's tiered
  `pts_allow_*` scoring from `load_schedules`'s per-game score (REG season only, same convention as
  `_season_totals`'s existing QB/RB/WR/TE filtering) — all scored against the league's own live
  `scoring_settings`, the same "real settings, not a hardcoded table" principle `compute_vorp`
  already used. `data/sleeper/players.parquet`'s `position == "DEF"` rows supply the display name;
  Sleeper's DEF `player_id` matches nflverse's `team` code for every franchise except the Rams
  (nflverse `"LA"` vs Sleeper `"LAR"`), handled by `DEF_TEAM_CODE_ALIASES`. `stats/sync.py` now
  also syncs `data/stats/team/<season>.parquet` via a new `fetch_team_stats` wrapper. Verified the
  computed 2025 ranking against real-world memory of the season (Texans/Seahawks/Broncos/Jaguars
  top 4, Jets dead last) — it checks out.
- **The mechanical-merge failure.** Ran `value bigboard build --season 2025` expecting the 32 new
  DEF rows to merge in cleanly like any other new `source="vorp"` row. Instead they landed at board
  ranks 24-56 — ahead of legitimate rostered RB2/WR2 talent (Chris Olave, D'Andre Swift, Josh
  Allen, etc.) — because DEF's raw points/VORP scale is compressed relative to skill positions (a
  whole DEF season's fantasy-point range, roughly -90 to +40 `vorp_season`, sits inside the range a
  single skill-position replacement margin spans) while `_insert_index_by_vorp`'s cross-position
  scan assumes raw `vorp_season` is comparable across positions — an assumption that happened to
  hold for QB/RB/WR/TE (broadly similar season point scales) but silently breaks for a position
  with a much smaller absolute scoring range. Reverted `data/bigboard/2025.csv` rather than ship
  that board, then added `POSITIONS_EXCLUDED_FROM_ORDINAL_MERGE = frozenset({"DEF"})` in
  `bigboard.py`, filtering `vorp_df` before the merge — this is now a hard invariant of
  `merge_bigboard` itself (tested), not a one-off manual skip, so it can't regress on a future
  `bigboard build` run.
- **Is DEF VORP even worth ranking, though?** Before just re-placing the same 32 rows at the
  bottom of the board instead, checked whether the underlying signal justifies that effort at all.
  Pulled `nflreadpy`'s `load_team_stats` + `load_schedules` for 2018-2025 (8 seasons, 7
  consecutive-year pairs, 222-224 team-year pairs) and computed real fantasy-scored season totals
  the same way `compute_def_vorp` does, plus component breakdowns and (from `load_pfr_advstats`,
  2018+) a pressure-rate proxy (team pressures / opponent pass attempts). Every candidate stat's
  own year-over-year autocorrelation is weak: turnover-scored points r=+0.18, sack rate r=+0.14,
  total fantasy points r=+0.25, points-allowed-scored points r=+0.27, points-allowed-per-game
  r=+0.28, pressure rate r=+0.30 (the "stickiest" of the bunch, consistent with turnovers being
  more luck-driven than pass-rush skill — but still far short of a usable signal). None of them
  beats raw prior-season fantasy points at predicting *next* season's fantasy points either
  (pressure rate r=+0.18, turnover points r=+0.20, points-allowed points r=+0.26, vs. raw points'
  own r=+0.25 baseline) — for comparison, the same pipeline's RB `vorp_season` year-over-year
  correlation is r=+0.68. One consecutive-year pair (2023→2024) was essentially zero (r=+0.06,
  ρ=-0.04), underscoring how volatile team defense really is year to year.
- **The in-season streaming test is the decisive result.** For every team-week from 2018-2025
  (n≈3968-4222), compared (a) that defense's own trailing 4-week fantasy-scoring average against
  that week's actual score, vs. (b) the upcoming opponent's own season-long points-per-game
  (negated, so a weak opposing offense reads as a good matchup) against that same week's score.
  (a) r=+0.09 — a defense's own recent form barely predicts its next game. (b) r=+0.32 — more than
  3x stronger — who they're playing matters far more than how good they've been. This directly
  confirms `draft.md`'s existing "DEF is far more streamable in-season than a rostered skill
  player" framing, now with a number behind it, and reframes the real lever as a weekly
  matchup-based streaming decision rather than a pre-draft ranking problem.
- **Decision: don't rank DEF in the ordinal board, at all — not even at the bottom.** Pushing the
  32 DEF rows to the very end of the board was considered (see the interrupted mid-turn
  AskUserQuestion this session) but dropped once the fuller research above landed: even the best
  available signal barely edges out raw points, all of it is weak, and the in-season matchup effect
  swamps whatever pre-draft signal exists anyway. Manufacturing a fake-precise bottom-of-board
  order out of a signal this noisy would misrepresent it as more meaningful than it is. Kept
  `draft.md`'s existing end-of-draft judgment call for DEF, now with these numbers backing it
  instead of pure intuition, and added a forward-pointing note there for a possible future
  weekly-matchup DEF streaming tool — a genuinely different, separate feature from a pre-draft
  ranking, not attempted here.
- **A second, pre-existing bug surfaced while re-running the build.** After the
  `POSITIONS_EXCLUDED_FROM_ORDINAL_MERGE` fix, re-ran `value bigboard build --season 2025` to pick
  up the 7 legitimately-new (non-DEF) veteran rows. User spot-checked one, Jacardia Wright
  (`vorp_season` -133.7), and found it at board rank 25 — next to Bijan Robinson/Jahmyr
  Gibbs/Josh Allen tier company, nowhere near where a replacement-level bench RB belongs. Root
  cause: `_insert_index_by_vorp`'s old first-violation top-down scan stops at the *first* existing
  row with lower vorp than the new one — and this board already has multiple deliberately
  hand-promoted rows breaking strict descending order (Lamar Jackson at rank 24 with
  `vorp_season` -61.1, Joe Burrow at rank 29 with -146.5, both from
  [[2026-08-28-bigboard-injury-recovery-games-missed-review]]). Burrow's anomalously-low vorp,
  sitting anomalously early in the list, acted as a false floor: *any* new row with vorp above
  -146.5 (nearly everything) got trapped immediately above him regardless of its true value — 4 of
  the 7 new rows (Jacardia Wright, Keleki Latu, Zaire Mitchell-Paden, Carter Runyon; the other 3
  had vorp low enough to scan past Burrow correctly) landed at ranks 25-28 instead of their true
  ~350-470 neighborhood. This was a latent defect already flagged in `bigboard.md`'s "known sharp
  edges" section in spirit (non-monotonic hand-promotions breaking insertion), just never
  triggered before because no new `vorp` row had been added since Burrow's promotion. Fixed
  `_insert_index_by_vorp` to count how many existing rows outrank the new one rather than scanning
  for the first that doesn't — mathematically identical result on a monotonic board, and bounds
  (rather than eliminates) the error on a non-monotonic one to roughly "how many anomalies sit
  below the new row's vorp," instead of letting one early anomaly silently swallow every later
  insertion. Reverted `data/bigboard/2025.csv` a second time and rebuilt clean; all 7 new rows now
  land in their correct deep-bench neighborhood (ranks 358-539), and Lamar Jackson/Burrow's
  hand-promoted rows are untouched (existing rows are never reordered by design).

## Data

- `cli/src/sleeper_agent/stats/vorp.py`: `compute_def_vorp`, `DEF_STAT_COLUMN_TO_SCORING_KEY`,
  `DEF_BLOCKED_KICK_COLUMNS`, `DEF_POINTS_ALLOWED_TIERS`, `DEF_TEAM_CODE_ALIASES`.
- `cli/src/sleeper_agent/stats/{nflverse,sync}.py`: `fetch_team_stats`,
  `data/stats/team/<season>.parquet` (`TEAM_SCHEMA_VERSION`).
- `cli/src/sleeper_agent/commands/stats_cmd.py`: `cmd_stats_vorp` now appends `compute_def_vorp`
  results when `data/stats/team/`, `data/stats/schedules/`, and `data/sleeper/players.parquet` are
  all present — best-effort, same convention as other optional-input commands in this codebase.
  Ran for real: `stats sync --season 2025` (570 team rows) then `stats vorp --season 2025`; the 32
  DEF rows in `data/vorp/2025.parquet` line up with 2025 reality (Texans #1 at vorp=38.0, Jets
  last at vorp=-86.0).
- `cli/src/sleeper_agent/draft_tools/bigboard.py`: `POSITIONS_EXCLUDED_FROM_ORDINAL_MERGE`,
  filtered inside `merge_bigboard` before the insert loop; covered by
  `test_merge_bigboard_never_inserts_def_rows`. `_insert_index_by_vorp` rewritten from a
  first-violation scan to a count-of-outranking-rows sum; covered by
  `test_merge_bigboard_inserts_near_correct_neighborhood_despite_a_hand_promoted_anomaly`.
- Year-over-year and streaming analysis: throwaway scripts (not committed), pure-Python
  Pearson/Spearman since this venv carries no numpy/scipy — `nflreadpy.load_team_stats`,
  `load_schedules`, `load_pfr_advstats(stat_type="def")` for 2018-2025.
- `data/bigboard/2025.csv`: reverted twice — once for the DEF cross-position-scale mismerge, once
  for the pre-existing `_insert_index_by_vorp` scan bug it happened to expose — then re-built
  clean after both fixes. Final state: 0 DEF rows, 0 flagged rows, 7 new non-DEF rows (all
  deep-bench/practice-squad additions unrelated to this work) landing at their correct
  `vorp_season`-ordered ranks (358-539), confirmed by diffing player-id sets before/after and
  spot-checking each new row's neighbors. Lamar Jackson/Joe Burrow's hand-promoted rows
  (rank 24/29) untouched throughout.
- `.claude/skills/draft.md`'s "Defenses" section updated in the same pass: reframed from "no data"
  to "deliberately unranked," with the streaming-vs-ranking numbers above and a forward-pointing
  note on a possible future weekly-matchup DEF streaming tool.
- Full test suite (423 tests), `ruff check`/`ruff format`, and `ty check` all pass on every touched
  file.

## Outcome

`stats vorp`/`stats sync` now compute and persist real team-DEF VORP every time they run, available
for `value rank --position DEF` and similar lookups, but `value bigboard build` will never insert
DEF rows into the ordinal board again — enforced in code, not just by convention. Along the way,
fixed a second, unrelated but pre-existing latent bug in `merge_bigboard`'s insertion logic that a
hand-promoted row (any position, not DEF-specific) could trigger — now bounded rather than
unbounded. `todo.md`'s DEF item is resolved as "researched and deliberately not done" rather than
"done": the ask was satisfied (real research using recent pressure rate / takeaways / other
real-season signal, per the original wording), and the honest conclusion is that none of it clears
the bar for draft-day ranking. `draft.md`'s "Defenses" section was updated in this same pass to
reflect both findings.
