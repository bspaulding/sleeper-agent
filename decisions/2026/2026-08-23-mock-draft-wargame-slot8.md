date: '2026-08-23'
kind: draft
season: '2026'
status: failed
players_involved:
  - '8023'
  - '4943'
related_wiki:
  - wiki/team/roster-philosophy.md
  - wiki/team/defense-strategy.md
  - wiki/team/keeper-strategy.md
  - wiki/league/projected-keepers-2026.md
---

## Summary

**RUN FAILED — draft voided on the pick clock before this run could make any
selection, and before the LLM Drafter emitted a single recommendation.**
Draft `wargame-draft-2026` (slot 8, roster_id 5, snake, 12 teams, 15 rounds)
ended with status `voided_pick_clock`: "HARD FAIL: pick clock expired (60s)
before roster 5 selection at pick 8" (server log, 18:04:46). Final state: **31
of 180 picks** — my two pre-seeded keepers (Diggs #80, Darnold #161) plus 29
bot picks through pick 7. Roster 5 live picks: **0 of 13**.

This file supersedes an earlier same-day retro written to this path by a prior
attempt, which also died at pick 8 (that run got as far as queuing St. Brown
but lost the clock resolving name→player_id). This run failed *earlier* in the
pipeline: it never got a recommendation to act on.

## Pick-by-pick table

All 31 recorded picks. "Drafter-rec" / "Human-override" columns are n/a — the
drafter produced zero recommendations and the human made zero selections.
Keepers were seeded by the harness, not clicked by either role.

| Rd | Pick | Slot | Roster | Player | Pos | Type |
|---|---|---|---|---|---|---|
| 1 | 1 | 1 | 7 | Christian McCaffrey | RB | bot |
| 1 | 2 | 2 | 3 | Puka Nacua | WR | bot |
| 1 | 3 | 3 | 12 | Bijan Robinson | RB | bot |
| 1 | 4 | 4 | 9 | Jahmyr Gibbs | RB | bot |
| 1 | 5 | 5 | 10 | De'Von Achane | RB | bot |
| 1 | 6 | 6 | 8 | Kyren Williams | RB | bot |
| 1 | 7 | 7 | 1 | Trey McBride | TE | bot |
| 1 | 8 | 8 | 5 | — | — | **VOIDED (my clock expired)** |
| 1 | 10 | 9 | 6 | Jonathan Taylor | RB | keeper (seeded) |
| 1 | 12 | 12 | 4 | Jaxon Smith-Njigba | WR | keeper (seeded) |
| 2 | 21 | 9 | 9 | James Cook | RB | keeper (seeded) |
| 3 | 33 | 2 | 2 | Kenneth Walker III | RB | keeper (seeded) |
| 4 | 38 | 11 | 11 | D'Andre Swift | RB | keeper (seeded) |
| 4 | 43 | 7 | 8 | George Pickens | WR | keeper (seeded) |
| 4 | 46 | 10 | 12 | Courtland Sutton | WR | keeper (seeded) |
| 4 | 47 | 11 | 3 | RJ Harvey | RB | keeper (seeded) |
| 5 | 49 | 1 | 7 | Chris Olave | WR | keeper (seeded) |
| 5 | 58 | 10 | 6 | Zay Flowers | WR | keeper (seeded) |
| 6 | 66 | 6 | 1 | Zach Charbonnet | RB | keeper (seeded) |
| 6 | 69 | 9 | 9 | Jauan Jennings | WR | keeper (seeded) |
| 6 | 70 | 10 | 12 | Travis Etienne | RB | keeper (seeded) |
| 6 | 71 | 11 | 3 | Jaylen Warren | RB | keeper (seeded) |
| 7 | 79 | 7 | 1 | Drake Maye | QB | keeper (seeded) |
| 7 | 80 | 8 | 5 | Stefon Diggs | WR | keeper (seeded, mine) |
| 8 | 85 | 12 | 4 | Javonte Williams | RB | keeper (seeded) |
| 9 | 97 | 1 | 7 | Trevor Lawrence | QB | keeper (seeded) |
| 9 | 101 | 5 | 10 | Kyle Pitts | TE | keeper (seeded) |
| 10 | 112 | 9 | 2 | Wan'Dale Robinson | WR | keeper (seeded) |
| 10 | 116 | 5 | 10 | Kenny Gainwell | RB | keeper (seeded) |
| 11 | 126 | 6 | 8 | Matthew Stafford | QB | keeper (seeded) |
| 11 | 131 | 11 | 11 | Keenan Allen | WR | keeper (seeded) |
| 14 | 161 | 8 | 5 | Sam Darnold | QB | keeper (seeded, mine) |

## Drafter hit rate

**0 recommendations emitted → hit rate undefined/n-a.** `/tmp/wargame/recs.jsonl`
contains exactly one line: `{"ts": "2026-08-24T01:05:46Z", "event": "done",
"status": "voided_pick_clock"}`. The drafter process launched cleanly, found
the draft already terminal on its first poll, correctly appended its done event,
and exited without POSTing anything or touching the repo. Its behavior under
the void condition was correct; it simply never had work to do.

## Where the pipeline struggled

1. **Fatal: the 60-second pick-clock window was consumed entirely by human-role
   startup, before the drafter was even launched.** Server-side the clock for
   pick 8 expired at 18:04:46; the drafter was not launched until ~18:05:40.
   The prescribed loop ("launch the drafter, then poll") front-loads setup into
   a window that is already running. By the time my first poll returned, the
   draft was terminal. There was no stale-info 409 to recover from, no board
   fetch to fall back on — the failure was purely elapsed wall-time during
   bootstrap.
2. **No grace period on turn 1.** The harness starts the 60s clock as soon as
   bots complete pick 7, but the human role's instructions require several
   sequential steps (read brief → launch background drafter → first poll)
   each costing multiple seconds of model/tool latency. Turn-1 needs either a
   longer initial clock, a paused-until-first-poll start, or a pre-started
   drafter.
3. **The fallback path ("pick best-available yourself from `draft board`")
   was unreachable.** It assumes you reach your turn with time remaining; here
   the entire budget was spent before the loop began. Note also the prior
   attempt's finding stands: `draft board` output lacks Sleeper player_ids,
   which the POST endpoint requires — that gap is still open.
4. **What worked:** the mock server, keeper seeding (24 keepers incl. both of
   mine at #80/#161), slot→roster mapping (slot 8 → roster 5), and the void
   semantics all behaved exactly as documented. Status polling gave an
   unambiguous terminal signal, and both roles honored stop-on-void.

## Retro

- This is now two consecutive wargame failures at the same checkpoint (pick 8,
  round 1), for different proximate reasons (prior run: id-resolution latency;
  this run: startup latency). Common root cause: **the recommend→submit path
  is not fast enough for a hard 60s clock when anything outside steady-state
  clicking is required**, whether that's tooling gaps or process launch.
- Concrete asks before re-running: (a) start the drafter *before* the draft
  goes live, or grant a turn-1 clock ≥ 3 minutes; (b) land the `draft board`
  player-id column / `draft pick --player` helper from the prior retro;
  (c) rehearse one end-to-end smoke click against a scratch draft.
- Strategy notes are moot for this run — no decision above pick 8 was made.
  Keeper posture (Diggs r7, Darnold r14) remains sound per
  `wiki/team/keeper-strategy.md`.

No code, data, or wiki changes made. File left uncommitted for review.
