---
date: '2026-08-23'
kind: draft
season: '2026'
status: failed
players_involved:
  - '7547'
  - '5850'
  - '5022'
  - '5892'
  - '6819'
  - '12514'
related_wiki:
  - wiki/team/roster-philosophy.md
  - wiki/team/draft-strategy.md
  - wiki/team/keeper-strategy.md
---

## Summary

**RUN FAILED — draft `wargame-draft-2026` voided on the pick clock at pick 89
(round 8) with 6 of 13 live picks made.** Final status `voided_pick_clock`;
server returned `DraftVoided: pick clock expired (60s) before roster 5
selection at pick 89`. This file supersedes the run-#8 retro previously at
this path. Run #9 got through six clean drafter-recommended picks (a first for
the wargame) before dying on a **wrong player-id recommendation** that cost
the decisive round-trip inside a 60s clock.

## Timeline (UTC)

| Time | Event |
|---|---|
| ~02:37 | Launched LLM Drafter per protocol (`nohup pi … > /tmp/wargame/drafter.jsonl`). |
| 02:38:48 | `drafter_ready` after only ~20s boot (vs ~210s in run #8). Confirmed `pre_draft`, POSTed `/start`. |
| 02:39:56 | Rec for pick 8: Amon-Ra St. Brown (7547), board-best VORP 145 tier-1 NEED. Accepted, clicked OK. |
| 02:42:12 | Rec for pick 17: Josh Jacobs with **wrong id 8347**; drafter self-corrected to 5850 at 02:42:21. Clicked 5850 OK. |
| 02:43:06 | Rec for pick 32: Dallas Goedert (5022), TE tier-1 need. Clicked OK. |
| 02:43:26 | Rec for pick 41: David Montgomery (5892). Clicked OK. |
| 02:43:44 | Rec for pick 56: Michael Pittman (6819). Clicked OK. |
| 02:43:59 | Rec for pick 65: Emeka Egbuka (12514). Clicked OK. |
| 02:44:0x–02:44:36 | Polling loop waited on pick 89 (bots idle; entries stuck at 95). Rec landed 02:44:36: Bucky Irving with **wrong id 23162** ("not on the draft board"). |
| ~02:44:4x | My click of 23162 rejected (`PlayerUnavailable`). Drafter posted CORRECTION to 11584 at 02:44:43; I retried ~5s later — **too late**: clock had expired. |
| ~02:44:55 | Server: `DraftVoided … at pick 89`. Per protocol I stopped clicking; killed drafter (it observed the void and exited cleanly). |

Note: the 60s clock on pick 89 was already deep into its window when the rec
arrived (rec latency ~35s into my turn plus a prior bad-id detour). No API
field exposes remaining clock time, so both sides flew blind.

## Pick-by-pick table

| Rd | Pick | Player | Pos | Type | Source |
|---|---|---|---|---|---|
| 1 | 8 | Amon-Ra St. Brown | WR | live | drafter-rec, accepted |
| 2 | 17 | Josh Jacobs | RB | live | drafter-rec (after id self-correction), accepted |
| 3 | 32 | Dallas Goedert | TE | live | drafter-rec, accepted |
| 4 | 41 | David Montgomery | RB | live | drafter-rec, accepted |
| 5 | 56 | Michael Pittman | WR | live | drafter-rec, accepted |
| 6 | 65 | Emeka Egbuka | WR | live | drafter-rec, accepted |
| 8 | 80 | Stefon Diggs | WR | keeper | pre-seeded |
| 8 | 89 | *(voided — clock expired)* | — | **VOIDED** | rec arrived w/ wrong id (23162→11584); correction too late |
| 11 | 113 | *(never reached)* | — | — | keeper Darnold #161 also unplayed |

Human overrides: **0**. All six completed live picks were drafter-recommended
and accepted as-is.

## Drafter hit rate

- Turns reached: **7** (picks 8, 17, 32, 41, 56, 65, 89).
- Valid recommendations received: **7/7** (right player every time).
- Correct sleeper id on first rec: **5/7** — bad ids at pick 17 (self-corrected
  in 9s, survived) and pick 89 (self-corrected in 7s, did not survive the clock).
- Clicked/completed: **6/13** live slots.
- **Overall hit rate: 6/13.**

## Where the pipeline struggled

1. **Wrong board ids are now the dominant failure mode (primary cause this
   run).** Twice the drafter recommended a real player under a stale/incorrect
   `player_id`; one such error is fatal if it happens inside the 60s clock,
   because the Human must burn a round-trip discovering the rejection and
   then wait for the correction line. The drafter's board fetch appears to be
   caching ids from an earlier snapshot — ids should be re-verified against a
   fresh `/players` fetch immediately before emitting each rec.
2. **Rec latency vs 60s clock.** The pick-89 rec arrived ~35s into my turn;
   combined with the bad-id detour (+~15s), the corrected click landed past
   expiry. Any single hiccup (bad id, slow board fetch, slow rationale) is
   unrecoverable at these latencies; two hiccups never are.
3. **No remaining-clock visibility** (unchanged from run #8): nothing in the
   API exposes time left, so the Human cannot know whether waiting ~7s for a
   promised correction is safe. A `/clock` endpoint or header would let the
   Human decide "wait for correction vs pick nothing."
4. **Duplicate/stale rec noise:** the drafter re-emitted recs for already-
   resolved picks (32 again at 02:44:08, 41 at 02:45:00, 8 at 02:42:44),
   including one *after* the void. Harmless here, but a Human matching "newest
   rec" naively could be misled; recommend tagging recs with the current
   on-clock state at emit time and suppressing stale emits.
5. **What worked:** boot time collapsed to ~20s (drafter read its docs during
   `pre_draft`); all six completed picks were correct, well-reasoned, and
   correctly attributed to the right `on_clock_pick_no`; the drafter detected
   both of its own bad ids and issued fast corrections; protocol discipline
   held (no self-directed picks, no clicks after the void).

## Retro

- Best run yet by a wide margin: first time the pipeline completed any live
  picks (6), and the failure moved from "human loop math" (run #8) to a
  narrow, fixable drafter defect (id verification + latency budget).
- Cheapest fixes before re-run: (a) drafter re-verifies `player_id` against
  the live board right before writing each rec line, and includes a fallback
  name in the same line so the Human can recover without waiting for a
  correction; (b) surface remaining pick-clock time to both agents; (c)
  target <10s rec latency once the on-clock event fires.
- Strategy notes: through six picks the drafter followed roster philosophy
  cleanly (WR beside kept Diggs → RB1 → TE need → RB2 → best-flex WRs), deferring DEF
  to the R12–14 window per defense-strategy.md. Still untested: whether that
  plan survives contact with rounds 9–15, since we've never reached pick 97.

No code, data, or wiki changes made by this run. File left uncommitted for
review.
