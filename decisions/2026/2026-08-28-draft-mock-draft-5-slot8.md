---
date: '2026-08-28'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - Jaxon Smith-Njigba
  - Trey McBride
  - Travis Etienne
  - D'Andre Swift
  - Matthew Stafford
  - Michael Wilson
  - Kenny Gainwell
  - Trevor Lawrence
  - Wan'Dale Robinson
  - Dallas Goedert
  - Juwan Johnson
  - Pittsburgh Steelers (DEF)
  - Denzel Boston
  - Dalton Schultz
  - Troy Franklin
related_wiki:
  - wiki/team/draft-strategy.md
---

## Summary

Mock draft `1398941988711038976` ("Only Gold"), slot 8, 12 teams, PPR, 15 rounds,
`--value-season` defaulted to 2025. Run live via `.claude/skills/draft.md`'s watcher (Sleeper's
own mock draft room). `--exclude-players 2449,4943` dropped Diggs and Darnold from the board
since both are already locked real-league keepers ([[2026-08-23-keeper-diggs-r7-darnold-r14]]).
Final roster (draft order):

1. (R1 P8) Jaxon Smith-Njigba — WR
2. (R2 P17) Trey McBride — TE
3. (R3 P32) Travis Etienne — RB
4. (R4 P41) D'Andre Swift — RB
5. (R5 P56) Matthew Stafford — QB
6. (R6 P65) Michael Wilson — WR
7. (R7 P80) Kenny Gainwell — RB
8. (R8 P89) Trevor Lawrence — QB
9. (R9 P104) Wan'Dale Robinson — WR
10. (R10 P113) Dallas Goedert — TE
11. (R11 P128) Juwan Johnson — TE
12. (R12 P137) Pittsburgh Steelers — DEF
13. (R13 P152) Denzel Boston — WR
14. (R14 P161) Dalton Schultz — TE
15. (R15 P176) Troy Franklin — WR

Composition: 2 QB, 3 RB, 5 WR, 4 TE, 1 DEF.

## Reasoning

Mechanical through R11: every pick was the top `NEED`-tagged row (R1-R4), falling back to top
overall once all starting slots filled (R5 QB, R6 WR closed out starters; R7 on pure top-overall).
No genuinely close tier-break calls in that stretch.

- **DEF (R12) — user-flagged miscall.** Took Pittsburgh on reputation once 7 of the usual
  top-tier units were off the board (Rams, Texans, Seahawks, Broncos, Eagles, Ravens, Patriots)
  and remaining skill-position value had converged near replacement (top row only 30.4 VORP).
  **User's post-draft correction: should have taken De'Zhaun Stribling instead.** Checked the
  board render from that exact turn — Stribling was sitting at rank **7** overall (rookie WR,
  no vorp number shown since rookie value comes from `bigboard`'s round-percentile placement,
  not live VORP), clearly still above-replacement, while DEF has zero rows/data in this pipeline
  by design (`draft.md`'s documented gap) — the DEF pick was never actually a ranked comparison
  against Stribling, it was a manual override that stepped outside the board entirely on a
  defense-run/convergence heuristic. That heuristic was too eager here: a rank-7 skill-position
  player sitting on the board beats speculative DEF timing, and DEF is far more streamable
  in-season than a rostered rookie WR. **Lesson for `draft.md`:** before overriding to DEF, check
  whether the top of the board still has a clearly above-replacement skill player sitting there
  (rank inside roughly the top 10) — if so, take that player and defer DEF, even mid-run.
- **Schultz/Boston (R13) — not a tool issue.** Recommended Dalton Schultz; the room resolved
  pick 152 to Denzel Boston instead. Per the user: this was their own judgment call made faster
  than the recommendation could land, not an autopick or a bug. Re-surfaced Schultz next turn
  (still available) and he landed in R14 instead. This is an inherent property of a live
  human-in-the-loop draft (advisory latency vs. the clock), not a `draft.md`/`draft board` defect
  — no fix needed.
- No PUP/injury surprises taken this run — Zach Charbonnet's `[INJ: PUP]` tag stayed visible on
  the board the whole draft (recurring test case from mock #3's retro) and was correctly never
  picked.

## Data

- Draft ID `1398941988711038976`, `--value-season 2025` (default), `--draft-slot 8`,
  `--num-teams 12` (matches `settings.teams`), `--exclude-players 2449,4943`.
- Live tracking: single `Monitor` wrapping `draft board --notify-my-turn`, piped through
  `tee` to a scratch log then `grep -E "YOUR TURN|Traceback|Error|error:"` — the `draft.md` fix
  from mock #4 (tee-before-grep) worked cleanly this run: every `YOUR TURN` event was answered by
  reading the tee'd log tail directly, no re-invocation of the CLI needed, no skill gaps found.
- Confirmed roster via `GET /v1/draft/<id>/picks`, filtered on `draft_slot == 8` (mock drafts
  carry `roster_id: null` throughout — no league behind them — so slot, not roster_id, is the
  right filter for a mock's own picks).

## Outcome

Drafted live by the user in Sleeper's mock draft room. Two retro notes captured above: a
DEF-over-Stribling miscall in R12 (user correction, folded into `draft.md` guidance) and an
R13 advisory-vs-clock timing mismatch (user's own call, not a tool defect — no action needed).
