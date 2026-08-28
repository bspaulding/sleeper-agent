---
date: '2026-08-27'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - De'Von Achane
  - James Cook
  - Drake Maye
  - Zay Flowers
  - Kyle Pitts
  - Michael Wilson
  - Kenny Gainwell
  - Matthew Stafford
  - Wan'Dale Robinson
  - Dallas Goedert
  - Juwan Johnson
  - Dalton Schultz
  - Pittsburgh Steelers (DEF)
  - Keenan Allen
  - Troy Franklin
related_wiki:
  - wiki/team/draft-strategy.md
---

## Summary

Mock draft `1398935084572143616` ("Only Gold"), slot 8, 12 teams, PPR, 15 rounds,
`--value-season` defaulted to 2025. Run live via `.claude/skills/draft.md`'s watcher (Sleeper's
own mock draft room, not the removed `wargame` simulator). `--exclude-players 2449,4943` dropped
Diggs and Darnold from the board since both are already locked real-league keepers
([[2026-08-23-keeper-diggs-r7-darnold-r14]]) — no point recommending players we can't actually
draft here. Final roster (draft order):

1. (R1 P8) De'Von Achane — RB
2. (R2 P17) James Cook — RB
3. (R3 P32) Drake Maye — QB
4. (R4 P41) Zay Flowers — WR
5. (R5 P56) Kyle Pitts — TE
6. (R6 P65) Michael Wilson — WR
7. (R7 P80) Kenny Gainwell — RB
8. (R8 P89) Matthew Stafford — QB
9. (R9 P104) Wan'Dale Robinson — WR
10. (R10 P113) Dallas Goedert — TE
11. (R11 P128) Juwan Johnson — TE
12. (R12 P137) Dalton Schultz — TE
13. (R13 P152) Pittsburgh Steelers — DEF
14. (R14 P161) Keenan Allen — WR
15. (R15 P176) Troy Franklin — WR

Composition: 2 QB, 3 RB, 5 WR, 4 TE, 1 DEF. User's post-draft note: "went very well," no
corrections.

## Reasoning

Purely mechanical this run — every pick was the top `NEED`-tagged row (R1-R6), falling back to
top-overall once all starting slots filled (R7 on), per `draft.md`'s rule. No tier-break judgment
calls were needed (unlike mock #3, which had several close NEED-vs-raw-VORP tradeoffs); the board
never presented a genuinely close call at any of our 15 picks.

- **DEF (R13):** No VORP/projection data for defenses in this pipeline (documented gap in
  `draft.md`). Checked the live picks feed (`GET /v1/draft/<id>/picks`) before picking rather than
  guessing blind — 8 of the usual top-tier units were already gone (Rams, Texans, Seahawks,
  Broncos, Eagles, Ravens, Patriots, Vikings). Took Pittsburgh on reputation (pass rush/takeaways)
  from what remained. Picked in round 13, not round 15 — deliberately not waiting for the last
  pick per the skill's explicit warning.
- No PUP/injury surprises this run (contrast mock #3's Charbonnet miss) — the live `[INJ: ...]`
  tags (shipped after that retro) surfaced cleanly at every pick, and none of the taken players
  carried a flag.

## Data

- Draft ID `1398935084572143616`, `--value-season 2025` (default), `--draft-slot 8`,
  `--num-teams 12` (matches `settings.teams`), `--exclude-players 2449,4943`.
- Live tracking: single `Monitor` wrapping `draft board --notify-my-turn` directly, piped through
  `grep -E "YOUR TURN|Traceback|Error|error:"` — no separate Bash background process (an earlier
  attempt this run started one via Bash `run_in_background` *and* a Monitor on the same command,
  which was redundant against the skill's "one process, one Monitor" rule; the Bash task was
  stopped and only the Monitor kept).
- **Skill gap found and fixed this run:** `draft.md`'s "During the draft" step says to read the
  tail of the watcher's *log file* on a `YOUR TURN` event. But grepping directly inside the
  `Monitor` command (as its own "Watching the draft" example does) means the full NEED/SURPLUS
  board never reaches disk — only the matched `YOUR TURN` line does. Worked around it this run by
  re-invoking `draft board --once` on every turn notification instead (13 extra CLI calls across
  the draft) — functionally fine, but contradicts the skill's own "don't re-invoke the CLI"
  instruction and the two conflicting setup steps (background Bash *and* Monitor-of-the-same-
  command) point at the same underlying gap. Fixed directly in `draft.md`: the watcher command now
  `tee`s to a log file before grepping, so the tail-read instruction is actually satisfiable in a
  single process. See that file's diff, same commit as this entry.

## Outcome

Recommended and drafted live by the user; no corrections needed. Cleanest run to date across the
non-wargame mock drafts (#1, #3, #4) — no retro-flagged misses, unlike #3's PUP catch.
