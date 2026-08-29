---
date: '2026-08-29'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - Christian McCaffrey
  - Trey McBride
  - Travis Etienne
  - Joe Burrow
  - Michael Wilson
  - Courtland Sutton
  - Kenny Gainwell
  - Matthew Stafford
  - Wan'Dale Robinson
  - Dallas Goedert
  - Juwan Johnson
  - De'Zhaun Stribling
  - Dalton Schultz
  - Keenan Allen
  - Los Angeles Chargers (DEF)
related_wiki:
  - wiki/team/draft-strategy.md
  - wiki/team/role-changers.md
  - wiki/league/projected-keepers-2026.md
---

## Summary

Mock draft `1399291848010264576` ("Only Gold"), slot 8, 12 teams, PPR, 15 rounds,
`--value-season` defaulted to 2025. Run live via `.claude/skills/draft.md`'s watcher.
`--exclude-players 2449,12512` dropped Diggs and Judkins from the board (our own confirmed real
keepers, per `decisions/2026/2026-08-28-keeper-swap-darnold-to-judkins.md`). Final roster
(draft order):

1. (R1 P8) Christian McCaffrey — RB
2. (R2 P17) Trey McBride — TE
3. (R3 P32) Travis Etienne — RB
4. (R4 P41) Joe Burrow — QB
5. (R5 P56) Michael Wilson — WR
6. (R6 P65) Courtland Sutton — WR
7. (R7 P80) Kenny Gainwell — RB
8. (R8 P89) Matthew Stafford — QB
9. (R9 P104) Wan'Dale Robinson — WR
10. (R10 P113) Dallas Goedert — TE
11. (R11 P128) Juwan Johnson — TE
12. (R12 P137) De'Zhaun Stribling — WR
13. (R13 P152) Dalton Schultz — TE
14. (R14 P161) Keenan Allen — WR
15. (R15 P176) Los Angeles Chargers — DEF

Composition: 2 QB, 3 RB, 5 WR, 4 TE, 1 DEF.

## Reasoning and user retro

Mechanical through R11 (top NEED row, falling back to top-overall once starters filled). User
gave five post-draft corrections/comments, all addressed below.

- **(a) Travis Etienne (R3) — overvalued, confirmed.** Board had him rank 16 overall / RB tier 1
  (vorp 118.2), taken at pick 32. Checked `data/adp/2026-08-28.parquet` (DraftSharks consensus,
  synced the day before this draft): Etienne is **RB20, overall ADP rank 43, adp_pick 45** — we
  reached ~13 picks ahead of market. `wiki/players/7543-travis-etienne.md` confirms the underlying
  story: he signed with New Orleans (4yr/$52M) and is listed **co-RB1 with Alvin Kamara**, most
  early-down work while Kamara leans passing-downs — a real committee, not a hand-off. The
  `[MOVED: JAX→NO]` tag on the board is exactly `wiki/team/role-changers.md`'s documented gap:
  his vorp=118.2 is computed from his 2025 Jacksonville workload (presumably a fuller bell-cow
  role) and nothing in `bigboard build` re-priced it for a shared 2026 backfield the way the
  2026-08-28 injury-recovery pass explicitly re-priced Burrow/Jones/Daniels. Unlike those three,
  Etienne's bigboard row (`data/bigboard/2025.csv` line 16) has **no rationale note at all** —
  the MOVED flag surfaced live in `draft board`'s output but was never actually reviewed.
  **Action: fold into the next `bigboard` refresh** — review every `[MOVED:...]`-flagged row
  against `wiki/team/role-changers.md`'s vacated-opportunity framework, not just injury-flagged
  rows, and check ranks against `data/adp/*.parquet` where available. Filed in `todo.md`.
- **(b) Burrow (R4) not factoring in keepers — real gap, but not the one it first looked like.**
  Burrow himself isn't any roster's real keeper (checked
  `wiki/league/projected-keepers-2026.md`'s confirmed table). The actual gap: `--exclude-players`
  only dropped **our own** 2 keepers (Diggs, Judkins), not the other **15** confirmed real
  keepers across the league (Drake Maye, Bhayshul Tuten, Kenneth Walker III, Blake Corum, Luther
  Burden III, Tucker Kraft, Javonte Williams, Rashee Rice, Jonathan Taylor, Zay Flowers, Chris
  Olave, Christian Watson, George Pickens, Rico Dowdle, and Romeo Doubs pending the ruling) —
  same gap in mock #4 and #5, just never named until now. Sleeper's mock room has no knowledge of
  our real league's keepers, so every one of those players stayed in this mock's pool, got
  drafted by the room's other 11 teams on a different timeline than the real draft will produce,
  and shifted who/what was available to us pick-to-pick in ways that won't replay on draft day
  (e.g. Drake Maye, ranked above Burrow on raw vorp, is a real lock elsewhere and won't be a live
  option at all). This directly inflates how tempting a QB "value" pick like Burrow looks in a
  mock relative to the real draft. **Action: exclude all confirmed real keepers, not just ours,
  next time a mock is run against this league** — filed in `todo.md` with the full ID list.
- **(c)/(d) Stafford (R8) and the Burrow/Stafford/[blocked] Daniel Jones QB stack — real tool
  gap, fixed live.** By R12 the mechanical "top row overall once nothing is NEED" fallback
  recommended **Daniel Jones as a 3rd QB**, purely because his injury-recovery-adjusted bigboard
  rank (#64) edges out Hunter Henry (#66) — a real ranking, but the fallback has no positional cap
  and doesn't discount a QB pick's marginal value once the starter slot (and a reasonable
  buy-low backup) are both already spoken for. **User: "3 QBs should never happen in a draft"** —
  overrode live, took De'Zhaun Stribling instead. Stafford (R8) was the same pattern one round
  earlier, just less extreme (2nd backup-tier QB, not 3rd) — same root cause. **Lesson for
  `draft.md` (added below, same shape as the existing DEF-over-Stribling lesson from
  [[2026-08-28-draft-mock-draft-5-slot8]]):** before taking a top-overall QB once the starter slot
  is filled, check whether it's already the 2nd QB on the roster — if so, treat the next
  highest-value non-QB row as the real top-overall pick instead.
- **(e) DEF (R15) — no fix needed.** All the usual reputation-tier defenses were gone by our last
  pick (this board has zero DEF data, so there was never a ranked signal to go on anyway); user
  took the Chargers. Same documented gap as every prior mock — nothing new here.

## Data

- Draft ID `1399291848010264576`, `--value-season 2025` (default), `--draft-slot 8`,
  `--num-teams 12` (matches `settings.teams`), `--exclude-players 2449,12512`.
- Live tracking: single `Monitor` wrapping `draft board --notify-my-turn`, piped through `tee`
  then `grep -E "YOUR TURN|Traceback|Error"` — no tool defects this run.
- Compared Etienne's board placement against `data/adp/2026-08-28.parquet` (DraftSharks) and
  `wiki/players/7543-travis-etienne.md` (news) to verify point (a).
- Confirmed final roster via `GET /v1/draft/<id>/picks`, filtered on `draft_slot == 8`.

## Outcome

Drafted live by the user in Sleeper's mock draft room. Three follow-ups filed in `todo.md`:
review MOVED-flagged bigboard rows for role-change repricing (starting with Etienne), exclude
all confirmed league keepers (not just ours) in the next practice mock, and add a QB-stacking
guard to `draft.md`'s top-overall fallback.
