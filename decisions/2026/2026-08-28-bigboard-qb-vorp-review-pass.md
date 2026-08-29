---
date: '2026-08-28'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Kyler Murray
  - J.J. McCarthy
  - Anthony Richardson
  - C.J. Stroud
  - Caleb Williams
  - Drake Maye
  - Tua Tagovailoa
  - Michael Penix Jr.
related_wiki:
  - wiki/team/draft-strategy.md
---

## Summary

Direct follow-up to [[2026-08-28-bigboard-qb-vorp-reliability-research]]: applied the
"weight raw QB VORP less than RB/WR/TE" calibration to the actual board, not just the docs.
Reviewed every unreviewed QB row on `data/bigboard/2025.csv` for a real 2026 situational story a
stricter, RB/WR/TE-level trust-the-VORP approach would have under-weighted, prioritizing rows
whose reputation/vorp gap looked largest. Live web research (not just the empty `wiki/players/`
stubs, which carry no actual content yet) surfaced one clear promotion — **Kyler Murray**, whose
2025 vorp (-204.1, rank 580) reflects a season cut short after 5 games by a foot injury, not
ability, and who has since been named Minnesota's 2026 starting QB over J.J. McCarthy — moved to
rank 88, just behind Mahomes. Six other candidates were reviewed and explicitly kept at their
mechanical rank, each for a stated reason: two resolve as "the low rank was already correct, not
injury-distorted" (McCarthy, Anthony Richardson — both benched/buried behind other now-confirmed
starters), two as "this is earned full-season production, not a missed-games artifact, so the
calibration doesn't call for an override" (Caleb Williams, Drake Maye), one as a wash (C.J.
Stroud), and two as "genuinely unresolved, don't guess" (Tua Tagovailoa / Michael Penix Jr.,
competing for Atlanta's job with no starter named yet). This wasn't an exhaustive sweep of all 40
QB rows — see Data for what was and wasn't covered.

## Reasoning

- **Kyler Murray (promoted, rank 580 -> 88).** 2025 ended after 5 games: a foot injury with a
  blood-flow/Lisfranc risk kept him at ~60% for months, eventually IR. Released by Arizona,
  signed Minnesota on a 1-year deal, and named the Vikings' 2026 starting QB over J.J. McCarthy
  after training camp (confirmed 2026-08-28) — a real starting job with a true WR1 (Justin
  Jefferson). This is the same shape as Burrow/Lamar Jackson/Daniel Jones/Brock Purdy's existing
  overrides (a whole season's raw VORP erased by missed time, not a real talent signal) — the
  exact pattern the reliability research explains recurs at QB. Deliberately placed lower than
  Burrow/Lamar (Baker Mayfield tier, not top-25) rather than mirroring their placement: health
  reporting here is genuinely hedged ("ups and downs concerning," "health will determine if he's
  a franchise QB") rather than Burrow's clean "no nagging injuries," and he's integrating into a
  brand-new offense/scheme, which those four other overrides didn't have to do.
- **J.J. McCarthy and Anthony Richardson (reviewed, no change — the low rank was already
  right).** Both looked like plausible injury-recovery candidates by reputation (former 1st-round
  picks with lost rookie/sophomore seasons), which is exactly the pattern the calibration says to
  take seriously. Real research says otherwise for both: McCarthy lost the 2026 QB1 job to Murray
  in camp; Richardson is 3rd string in Indianapolis behind an already-promoted Daniel Jones and
  rookie Riley Leonard. Confirms the calibration is "look harder," not "always promote" — these
  two are correctly near the bottom.
- **Caleb Williams and Drake Maye (reviewed, no change — earned production, not injury noise).**
  Both have genuinely strong stories (Williams: full year-2 continuity under Ben Johnson after an
  NFC North title; Maye: same OC in year 3 for the first time, A.J. Brown/Romeo Doubs added, a
  Super Bowl LX run) — but both played essentially full, real 2025 seasons, so their current
  `vorp_season` already reflects that production directly. The reliability finding is specifically
  about a single injury/game-script swing distorting a season total, not a general license to
  promote every QB with a good narrative; there's no missing-games artifact to correct here, so
  moving either would be projection dressed up as VORP correction. Maye's real O-line risk (21
  playoff sacks, an NFL record) roughly offsets the positive weapons/continuity story anyway.
- **C.J. Stroud (reviewed, no change — a wash).** Offensive line reportedly healthier with new
  starters, but top WR Jayden Higgins (knee) and RB depth (Jordan, Brooks) are banged up. Net
  roughly neutral; current rank stands.
- **Tua Tagovailoa and Michael Penix Jr. (reviewed, no change — genuinely unresolved).** Both
  landed in Atlanta's QB1 competition (Tua released by Miami on a bargain 1-year deal, Penix not
  yet cleared from a knee injury), with no starter named as of 2026-08-28. Neither the DEF
  streaming decision nor the QB reliability finding license guessing an unresolved competition —
  logged as explicitly revisit-later rather than silently skipped.
- **Scope, honestly bounded.** This covered the highest-likelihood candidates (biggest
  reputation/vorp gaps, teams with known QB competitions or heavy injury history) found via
  targeted web search, not all ~40 QB rows on the board. Rows not reviewed this pass: Trevor
  Lawrence, Matthew Stafford, Bo Nix, Dak Prescott, Jalen Hurts, Jared Goff, Justin Herbert, Baker
  Mayfield, Sam Darnold, Jaxson Dart, Jordan Love, Jacoby Brissett, Aaron Rodgers, Bryce Young,
  Cam Ward, Geno Smith, Tyler Shough, Joe Flacco, Mac Jones, Marcus Mariota, and every QB below
  replacement-level bench-depth (Kirk Cousins and lower) — no evidence gathered either way, still
  sitting at their mechanical rank. Not a claim they're fine, just not yet checked.

## Data

- Web research (WebSearch, 2026-08-28) on: J.J. McCarthy, Anthony Richardson, C.J. Stroud, Caleb
  Williams, Kyler Murray (two searches — the trade/injury background and current health status),
  Drake Maye, Tua Tagovailoa. `wiki/players/*.md` stubs for these players exist but carry no
  actual content (`last_researched: null`, empty `## News`) — not a usable source this pass.
- `data/bigboard/2025.csv` edited directly via the repo's own `load_bigboard_for_build` /
  `save_bigboard` / `_renumber` (not raw CSV text editing) to keep formatting and rank-renumbering
  consistent with the mechanical build path. Kyler Murray's row moved (rank 580 -> 88, vorp value
  itself unchanged at -204.1, same convention as every other hand-promoted row); six other rows'
  `rationale`/`log_ref` updated in place with no rank change.
- Verified after edits: `load_bigboard` (hard validation — ranks strictly 1..623, no unresolved
  markers) and `value bigboard build --season 2025` (0 added, 0 flagged) both pass clean. Full
  test suite (423 tests) unaffected — this pass touched only board data, no code.
- Corrected a factual error from [[2026-08-28-bigboard-qb-vorp-reliability-research]] and its
  linked docs in the same session: that entry originally (incorrectly) listed Drake Maye and J.J.
  McCarthy as already carrying hand-override rationale before this pass — they didn't; both were
  plain mechanical rows until reviewed here. Fixed in that entry, `draft.md`, and
  `wiki/team/draft-strategy.md` before this pass began.

## Outcome

`data/bigboard/2025.csv` has one real placement change (Kyler Murray, rank 580 -> 88) and six
rows newly annotated as reviewed-and-kept, all with `log_ref: 2026-08-28-bigboard-qb-vorp-review-
pass`. `value bigboard build --season 2025` still reports 0 flagged. Remaining QB rows (listed
above) are untouched and not yet reviewed under this calibration — a natural next pass if there's
appetite, not committed to happening automatically.
