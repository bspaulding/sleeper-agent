---
date: '2026-08-23'
kind: draft
season: '2026'
status: failed
players_involved:
  - '7547'
  - '2449'
  - '4943'
related_wiki:
  - wiki/team/roster-philosophy.md
  - wiki/team/draft-strategy.md
  - wiki/team/defense-strategy.md
  - wiki/team/keeper-strategy.md
---

## Summary

**RUN FAILED — draft voided on the pick clock at pick 17 (round 2) with 1 of
13 live picks made.** Draft `wargame-draft-2026` (slot 8, roster_id 5, snake,
12 teams, 15 rounds) ended `voided_pick_clock`: "HARD FAIL: pick clock expired
(60s) before roster 5 selection at pick 17" (server log). Final state:
**38 picks** — live picks 1–16 plus 22 future-position keeper seeds (incl. my
Diggs #80 / Darnold #161).

This file supersedes the same-day retro previously at this path (that run
voided at pick 8 with zero recommendations emitted). This run is a partial
step forward, not a pass: the LLM Drafter produced **exactly one timely
recommendation** (pick 8), I accepted and clicked it inside the window, and
then the drafter lost the thread entirely — it never emitted a pick-17 rec,
and its internal state model had drifted to believing my next pick was **#32**
(round 3) while the real on-clock pick was **#17**. Per protocol I made no
pick decision myself and let the draft void.

## Pick-by-pick table

| Rd | Pick | Slot | Roster | Player | Pos | Type | Source |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | 7 | Christian McCaffrey | RB | bot | — |
| 1 | 2 | 2 | 3 | Puka Nacua | WR | bot | — |
| 1 | 3 | 3 | 12 | Bijan Robinson | RB | bot | — |
| 1 | 4 | 4 | 9 | Jahmyr Gibbs | RB | bot | — |
| 1 | 5 | 5 | 10 | De'Von Achane | RB | bot | — |
| 1 | 6 | 6 | 8 | Kyren Williams | RB | bot | — |
| 1 | 7 | 7 | 1 | Trey McBride | TE | bot | — |
| 1 | 8 | 8 | 5 (me) | Amon-Ra St. Brown | WR | **live** | **drafter-recommended** (accepted) |
| 1 | 9 | 9 | 2 | Chase Brown | RB | bot | — |
| 1 | 10 | 10 | 6 | Jonathan Taylor | RB | keeper | seeded |
| 1 | 11 | 11 | 11 | Derrick Henry | RB | bot | — |
| 1 | 12 | 12 | 4 | Jaxon Smith-Njigba | WR | keeper | seeded |
| 2 | 13 | 12 | 4 | Josh Allen | QB | bot | — |
| 2 | 14 | 11 | 11 | Ja'Marr Chase | WR | bot | — |
| 2 | 15 | 10 | 6 | Saquon Barkley | RB | bot | — |
| 2 | 16 | 9 | 2 | Ashton Jeanty | RB | bot | — |
| 2 | 17 | 8 | 5 (me) | — | — | **VOIDED (clock expired)** | no rec arrived; correctly did nothing |
| 2–14 | various | — | various | remaining keeper seeds incl. Diggs #80 / Darnold #161 (mine) | — | keeper | seeded |

The one recommendation, verbatim from `recs.jsonl`:

> `{"ts": "…T01:31:59Z", "on_clock_pick_no": 8, "player_id": "7547",
> "player_name": "Amon-Ra St. Brown", "position": "WR", "rationale":
> "Board-best VORP (145.0, tier-1) fills WR need next to kept Diggs; with the
> turn at pick 17 a tier-1 RB (Chase Brown/Henry) has better fall odds than
> ARSB does if we wait."}`

Sound reasoning, correct id, emitted ~30s after process launch — accepted
without override and clicked immediately (no 409).

## Drafter hit rate

- Recommendations emitted: **1** (for pick 8 only).
- Turns needing a rec reached: **2** (picks 8, 17); timely recs: **1/2**.
- Live picks made: **1 of 13**. Human overrides: **0**. Stale-409 retries: **0**.
- **Overall hit rate: 1/13.** Timely-rec rate on reached turns: 50%.

## Where the pipeline struggled

1. **Fatal: after pick 8 the drafter stopped tracking the live draft.** Its
   post-pick turns (timestamps 01:32:45 → 01:37:24 UTC) were spent on:
   a failed `--value-season 2026` board call (~40s, "no VORP data for season
   2026"), a CLI usage error (~50s), two full 97-row board re-fetches, then a
   raw keeper-seed audit via hand-rolled picks greps — exactly the mid-draft
   side-investigation that `roster-philosophy.md` standing rule 4 forbids.
   Its last recorded reasoning stated "On the clock at pick 32 (round 3)" and
   planned a Josh Jacobs rec for a pick that would have been mine *three*
   selections later than the one that killed us. The true next pick was 17;
   by the time it finished bookkeeping, the clock had expired.
2. **State model has no shared source of truth.** The drafter recomputed
   on-clock ownership from raw picks each cycle (correct per the prompt), but
   nothing cross-checked its conclusion. A wrong intermediate belief ("round
   2 is over") propagated silently. There is also no heartbeat/progress event
   in `recs.jsonl`, so from my side "drafter is confused about the pick
   number" was indistinguishable from "drafter is quiet" until the void.
3. **Bot pacing vs. deliberation asymmetry.** Bots filled picks 9–16 well
   inside one 60s window, so my pick-17 turn began roughly a minute after my
   pick-8 click. The drafter's per-turn cost (30–90s, worse when a call
   errors) cannot survive that cadence once it falls behind by even one
   turn — and it fell behind immediately after spending its momentum on the
   pick-8 rec.
4. **Repeated CLI invocation friction.** Two of its eight completed turns
   died on argument errors (`--value-season 2026` unsupported; missing
   required flags). Under a live clock each error is a full turn burned. The
   working invocation from the prompt (`--league-id wargame-league-2026 --me`
   + `--value-season`) was eventually used correctly, but only after the
   detour.
5. **What worked:** server seeding and void semantics were clean; the
   stop-on-void discipline held (nothing clicked after the flip); and the
   single end-to-end success (rec → accept → click → server ack for ARSB)
   proves the happy path works when the drafter is watching the right pick.

## Retro

- Fifth wargame run, fifth failure, but the first with a completed live pick.
  Progression across runs: 0 picks / 0 recs → 1 pick / 1 timely rec. The
  bottleneck has moved from "can the drafter produce any rec at all" (fixed —
  cold start now fits turn 1) to "can it stay synchronized turn over turn."
- Concrete asks before re-running: (a) the drafter should recompute and
  **assert** next_pick_no every cycle against the picks feed and refuse to
  reason about any other number — the pick-32 drift is the single fatal bug;
  (b) emit a rec for the *current* on-clock pick before any post-pick
  audit/wiki work (newest-wins already supports refinement); (c) cache the
  board once and diff the picks feed instead of re-fetching all 97 rows per
  turn; (d) add heartbeat events (`{"event":"poll","next_pick_no":N}`) to
  `recs.jsonl` so stale-or-wrong state is visible to the Human mid-clock;
  (e) hardcode the exact known-good CLI invocation in-session to stop
  burning turns on flag errors.
- Strategy notes: the pick-8 logic itself (ARSB over reaching for RB, trusting
  tier-1 RB fall odds to pick 17) was defensible and partially validated — a
  tier-1 RB *did* fall to 17 territory (Stevenson/Henderson/Dowdle were all
  sitting there per the drafter's own board snapshot). We'll never know if it
  would have converted that plan, which is the real loss.

No code, data, or wiki changes made by this run. File left uncommitted for
review.
