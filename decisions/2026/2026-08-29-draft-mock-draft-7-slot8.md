---
date: '2026-08-29'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - De'Von Achane
  - Trey McBride
  - Kyren Williams
  - Joe Burrow
  - Michael Wilson
  - Courtland Sutton
  - Matthew Stafford
  - Travis Kelce
  - Dallas Goedert
  - Juwan Johnson
  - Hunter Henry
  - Tyrone Tracy Jr.
  - Woody Marks
  - Troy Franklin
  - Los Angeles Chargers (DEF)
related_wiki:
  - wiki/team/draft-strategy.md
  - wiki/league/projected-keepers-2026.md
---

## Summary

Mock draft `1399301410142597120` ("Only Gold"), slot 8, 12 teams, PPR, 15 rounds,
`--value-season` defaulted to 2025. Run live via `.claude/skills/draft.md`'s watcher. Unlike mock
#6, `--exclude-players` dropped **all 17 confirmed real league keepers** (not just our own 2) —
the fix filed in [[2026-08-29-draft-mock-draft-6-slot8]]'s retro point (b). Final roster (draft
order):

1. (R1 P8) De'Von Achane — RB
2. (R2 P17) Trey McBride — TE
3. (R3 P32) Kyren Williams — RB
4. (R4 P41) Joe Burrow — QB
5. (R5 P56) Michael Wilson — WR
6. (R6 P65) Courtland Sutton — WR
7. (R7 P80) Matthew Stafford — QB
8. (R8 P89) Travis Kelce — TE
9. (R9 P104) Dallas Goedert — TE
10. (R10 P113) Juwan Johnson — TE
11. (R11 P128) Hunter Henry — TE
12. (R12 P137) Tyrone Tracy Jr. — RB
13. (R13 P152) Woody Marks — RB
14. (R14 P161) Troy Franklin — WR
15. (R15 P176) Los Angeles Chargers — DEF

Composition: 2 QB, 4 RB, 3 WR, 5 TE, 1 DEF.

## Reasoning and user retro

Mechanical through R7 (top NEED row; QB-stacking guard applied from R8 on). Live TE-stacking
override applied ad hoc at R12-R14 (see below). User gave five post-draft comments, all addressed
below.

- **(a) Burrow (R4) taken before filling WR — new gap, not previously named.** At pick 41, WR was
  still 0/2 (no starters at all) while QB was 0/1. The mechanical "top NEED row" rule doesn't
  compare *how speculative* a NEED pick is against a fully-unfilled, non-speculative alternative
  at another position. Checked `data/bigboard/2025.csv` line 26: Burrow's rank (25th) comes from
  `2026-08-28-bigboard-injury-recovery-games-missed-review` — a hand-curated placement on his
  full-health 2026 ceiling, explicitly "placed just behind Lamar Jackson, ahead of Drake Maye" —
  while his actual season vorp is **-146.5** (single worst season/per-game distortion on the whole
  board per that review's own note). So this wasn't the same root cause as mock #6's Burrow issue
  (that was a keeper-exclusion gap, now fixed) — it's the mechanical rule not weighing a
  speculative injury-recovery bet against a completely open starter slot. No code fix yet; added
  to `draft.md` as a documented gap to watch for, since it doesn't have a clean mechanical
  resolution (would need to compare "NEED-ness" across positions, which the tool doesn't do).
- **(b) Two QBs still felt too early — same underlying cause as (a).** Burrow R4 + Stafford R7 is
  the same pattern one level up: nothing wrong with the QB-stacking guard itself (correctly capped
  us at 2, per mock #6's fix), but the guard only prevents a *3rd* QB — it doesn't second-guess
  taking the 1st or 2nd early when a speculative/negative-vorp QB outranks real starter needs. Same
  root cause and same fix (or lack of one) as (a).
- **(c) Excluding all league keepers felt counterproductive — reversing mock #6's action item.**
  User's live pushback, recorded as-is rather than re-litigated here: full keeper exclusion (17
  players) removes real players from Sleeper's mock pool, but since Sleeper's own mock room has no
  concept of our real league's keepers, the other 11 (CPU-autopick) teams in this room still draft
  as if those players *are* available in some counterfactual sense — the mock's actual pick-by-pick
  flow doesn't otherwise resemble the real draft closely enough for full exclusion to pay for
  itself, and it makes the practice run's board less representative of "what a generic 12-team
  draft looks like." **Action: don't default to excluding all confirmed keepers in the next mock —
  treat `--exclude-players` as opt-in for testing a specific scenario, not a standing default.**
  This directly reverses [[2026-08-29-draft-mock-draft-6-slot8]]'s point (b) action item; noted
  here so the next mock doesn't silently re-apply it without re-asking.
- **(d) 5 TEs (before the R12-14 override) — real gap, fixed live, guard added.** Board order kept
  surfacing TE rows in the top-overall fallback well past any usable depth (5 rostered by R11).
  Applied the same logic as the existing QB-stacking guard live at R12/R13/R14 (skipped Dalton
  Schultz each time, took RB/WR bench instead) and generalized the guard in `draft.md` to any
  position, not just QB — see that file's new "Same cap for any position" section. No hard number
  defined (informally ~3-4 for TE/RB/WR depending on FLEX capacity vs. 2 for QB) — left as a
  judgment call rather than a fixed constant, since the right depth depends on FLEX capacity.
- **(e) DEF has no ranked data — user wants an actual research pass.** Same documented gap as
  every prior mock, but this time it's an explicit ask rather than a "nothing new here." Filed in
  `todo.md`: build a ranked defense list (recent pressure rate / takeaways / other real-season
  signal) so `draft board` can surface DEF rows the same way it does every other position, instead
  of punting to pure end-of-draft judgment.

## Data

- Draft ID `1399301410142597120`, `--value-season 2025` (default), `--draft-slot 8`,
  `--num-teams 12` (matches `settings.teams`), `--exclude-players` with all 17 confirmed real
  league keepers (2449, 12512, 11564, 12490, 8151, 11586, 12519, 9484, 7588, 10229, 6813, 9997,
  8144, 8167, 8137, 7021, 8121), per `wiki/league/projected-keepers-2026.md`.
- Live tracking: single `Monitor` wrapping `draft board --notify-my-turn`, piped through `tee` then
  `grep -E "YOUR TURN|Traceback|Error"` — no tool defects this run.
- Confirmed final roster via `GET /v1/draft/<id>/picks`, filtered on `draft_slot == 8`; draft
  reached all 180 picks (12 teams x 15 rounds).
- Checked Burrow's bigboard rationale (`data/bigboard/2025.csv` line 26,
  `2026-08-28-bigboard-injury-recovery-games-missed-review`) to verify point (a).

## Outcome

Drafted live by the user in Sleeper's mock draft room. `draft.md` updated in place with the
generalized position-stacking guard (d) and the unresolved speculative-NEED-vs-open-starter gap
(a/b) documented as a known limitation. Two follow-ups filed in `todo.md`: don't default to
full-keeper-exclusion in the next mock (c), and build a real DEF ranking pass (e).
