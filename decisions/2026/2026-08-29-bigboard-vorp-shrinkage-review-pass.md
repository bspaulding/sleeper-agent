---
date: '2026-08-29'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Kenneth Walker III
  - Lamar Jackson
  - Joe Burrow
  - Brock Purdy
  - Kyler Murray
  - Keaton Mitchell
related_wiki: []
---

## Summary

Review pass resolving the 602 `[VORP CHANGED]` flags
[[2026-08-29-bigboard-vorp-shrinkage-by-position-reliability]] produced by switching
`merge_bigboard` to sort/insert by `vorp_season_shrunk`. First instinct was to revert the flagged
state as too disruptive — corrected mid-session: the flag mechanism is the intended worklist for
exactly this kind of methodology change, not something to dodge. Split the 602 into two classes:
**564 plain mechanical rows** (no hand-override, just sitting at their vorp-driven rank), resolved
by a deterministic stable merge-resort — since a single per-position multiplier never reorders
players *within* a position, resorting the plain rows by `vorp_season_shrunk` while holding the
**39 genuinely pinned override rows** fixed in their exact sequence slots is a well-defined,
correct operation, not 564 independent judgment calls. That left **38 pinned rows** flagged (their
stored `vorp` number legitimately changed to the new shrunk value even though their rank didn't
move) needing an actual "does this still make sense" check. Of those, **6 had an explicit
named-player board-rank anchor in their own rationale** (e.g. "moved up, behind Saquon Barkley")
that the slot-preserving resort broke, because the *named anchor player* wasn't pinned and moved
during the resort while the row referencing it stayed put. Re-anchored all 6. The other 32 checked
out — either no board-rank anchor was actually stated (their "behind X" wording described real NFL
depth-chart standing, not board position), or the local vorp inversion versus new neighbors is the
normal, expected shape of any hand-promoted/demoted row, not a new defect introduced by shrinkage.

## Reasoning

- **Why mechanical resort was safe for the 564 plain rows.** `vorp_season_shrunk = r * vorp_season`
  for a fixed per-position `r` is a strictly monotonic transform — it can never change the relative
  order of two same-position players. So resorting only changes cross-position interleaving, which
  is exactly what merge_bigboard's ordinal insertion is supposed to reflect anyway. Implementation:
  walked the old row sequence; every pinned-row slot kept its exact occupant; every other slot got
  filled, in order, from a fresh list of the 564 plain rows sorted by their (already-updated)
  shrunk vorp. This is a stable merge, not a judgment call, and is exactly the "full mechanical
  re-sort, pin genuine overrides" approach discussed (and initially not committed to) earlier this
  session.
- **Why the flags shouldn't have been reverted.** `bigboard.md`'s whole design is: `stats vorp`
  updates numbers, `bigboard build` flags what changed, a review pass resolves each flag — a large
  flag count from a real methodology change is the mechanism working as intended, not a sign to
  back out. Reverting a legitimate flagged state throws away the free "here's exactly what needs a
  second look, with before/after values" bookkeeping the flag text carries.
- **The 38 remaining rows, and why 6 needed a real fix.** These are the genuinely hand-promoted/
  demoted rows (`[INJURY REVIEW`/`[ROLE-CHANGE REVIEW` with an explicit "moved from X -> here" or
  "moved #X -> #Y" — 39 total, one had `vorp=0.0` so shrinking by any factor produced no numeric
  change and never got flagged in the first place). Checked every one's rationale for an explicit
  named-player board-rank anchor ("behind Player Name", "ahead of Player Name", "alongside Player
  Name") as opposed to a real-NFL depth-chart mention (e.g. Rachaad White "behind Jacory Croskey-
  Merritt" describes Washington's actual backfield pecking order, not board rank — confirmed by
  checking whether the named player's board position would even make sense as an anchor, e.g. an
  RB can't sensibly be "behind" a WR on an NFL depth chart, so "Keaton Mitchell... behind Cooper
  Kupp" had to be a board-rank statement). Found 6 real anchors, all broken by the resort because
  the anchor player was a plain (unpinned) row that moved during it while the row citing it stayed
  fixed in its old absolute slot:
  - **Kenneth Walker III** ("behind Saquon Barkley") had drifted *above* Barkley (rank 19 vs. 20) —
    re-anchored to rank 20, right after Barkley.
  - **Lamar Jackson** ("placed right behind Josh Allen") had drifted to rank 24 while Allen (whose
    own shrunk vorp fell hard) moved to rank 33 — re-anchored to rank 32, right after Allen.
  - **Joe Burrow** ("behind Lamar Jackson, ahead of Drake Maye") followed Lamar's new position —
    re-anchored to rank 33, right after Lamar, confirmed still ahead of Maye (rank 44).
  - **Brock Purdy** ("near Herbert/Mahomes, not higher") had drifted to rank 80 while Herbert (87)
    and Mahomes (96, later 94 after the cascade) fell below him — direct contradiction of "not
    higher." Re-anchored to right after Mahomes.
  - **Kyler Murray** ("near the Baker Mayfield / game-manager-arm tier rather than alongside
    Lamar/Burrow" — from this session's earlier [[2026-08-28-bigboard-qb-vorp-review-pass]]) had
    drifted to rank 88, right next to Justin Herbert — nowhere near Mayfield (106). Re-anchored to
    right after Mayfield.
  - **Keaton Mitchell** ("moved #214 -> up, behind Cooper Kupp") had drifted *above* Kupp (rank 167
    vs. 175). Re-anchored to right after Kupp.
- **Why the other 32 weren't touched.** Two patterns: (1) most "behind X"/"ahead of X" mentions in
  this batch describe real NFL depth-chart standing (Dowdle/Gainwell/Charbonnet/White/Pacheco/
  Austin/Nailor/Jennings/Carter), unrelated to board position — no board-rank claim to check. (2)
  Several large promotions/demotions with no named anchor at all (Garrett Wilson, Malik Nabers,
  Mike Evans, Ashton Jeanty, etc.) show a "local inversion" against their new neighbors — e.g.
  Jeanty (vorp 74.0) sitting worse-ranked than Zay Flowers (vorp 52.6) immediately above him. This
  looked like a defect on first read, but McCaffrey's own long-standing, clearly-correct entry has
  the identical shape (vorp 188.2, the *highest* in its neighborhood, yet demoted to rank 4 behind
  three lower-vorp backs) — a local inversion is the mechanical signature of *any* hand-adjusted
  row, not evidence something broke. Absent a stated, checkable anchor, second-guessing these
  further would be re-litigating already-made injury/role judgment calls under a pretext, not
  fixing a shrinkage-specific problem.
- **Cleanup bug caught and fixed mid-pass.** First attempt at resolving the 38 rows only *appended*
  a resolution note after the existing `[VORP CHANGED: ...]` text instead of removing it —
  `is_unresolved()` does a literal substring check for `"[VORP CHANGED"`, so the rows stayed
  flagged (verified: a re-run of `bigboard build` still reported 38 flagged) despite carrying a
  correct-looking resolution note. Fixed by actually stripping the `[VORP CHANGED: ...]` clause via
  regex before appending the final note — same "clear the marker, don't just annotate past it"
  requirement `bigboard.md` already documents for a `[NEEDS REVIEW]`/`[VORP CHANGED]` resolution.

## Data

- `data/bigboard/2025.csv`: 564 rows mechanically resorted (rationale tagged
  `[VORP RECALIBRATED 2026-08-29: ...]`), 32 rows confirmed-kept with an explicit note, 6 rows
  re-anchored to their named board-rank reference. All `log_ref: 2026-08-29-bigboard-vorp-
  shrinkage-review-pass`.
- Verified: `value bigboard build --season 2025` reports 0 flagged; `load_bigboard` hard-validation
  (strict 1..623 ranks, no unresolved markers) passes; full test suite (424 tests) unaffected —
  this pass touched only board data, no code.
- Named-anchor audit done via targeted regex search (`behind [A-Z]...`, `ahead of [A-Z]...`,
  `alongside [A-Z]...`) across all 38 flagged rows' rationale text, then manually classified each
  match as a board-rank claim (checked against the named player's actual current rank) or an NFL
  depth-chart description (not checked against board position).

## Outcome

`data/bigboard/2025.csv` is fully resolved and draft-usable again (0 flagged rows). The board now
reflects the shrinkage methodology from [[2026-08-29-bigboard-vorp-shrinkage-by-position-reliability]]
end to end: QBs' cross-position placement is systematically discounted by their weaker
year-over-year reliability, every hand-promoted row's stated relative-position claims hold, and
nothing outside those stated claims was second-guessed.
