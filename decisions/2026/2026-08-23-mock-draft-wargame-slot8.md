---
date: '2026-08-23'
kind: draft
season: '2026'
status: failed
players_involved:
  - '7547'
  - '5850'
related_wiki:
  - wiki/team/roster-philosophy.md
---

## Summary

**RUN #13 — FAILED.** Draft `wargame-draft-2026` voided on the pick clock at pick 17
(round 2, slot 8→5) with **1 of 13 live picks clicked**. Final status
`voided_pick_clock`; server log: `HARD FAIL ts=03:34:32: pick clock expired
(60s) before roster 5 selection at pick 17`. This file supersedes the run-#12
retro previously at this path.

Run #13's failure was **Drafter-side (runtime death)**: the Drafter delivered a
fresh, valid recommendation for pick 8 (Amon-Ra St. Brown, 7547), which the
Human clicked successfully. It even audit-logged an ahead-of-time pick-17 rec
(Josh Jacobs, 5850) one second later. But the Drafter process then **died with a
pi extension error** (`This extension ctx is stale after session replacement or
reload`, thrown from the monitor's `emitDirect` path on child-process exit),
so it never wrote `current_rec.json` for pick 17 — the only file the Human is
allowed to act on. The Human followed protocol exactly (waited, did not
substitute judgment), the clock expired, and the draft voided.

## Context

Clean reset to `pre_draft` between runs (keepers Diggs at 80, Darnold at 161
re-seeded). The run-#12 Drafter prompt hardening (`## No extra analysis calls`,
delete-then-write `current_rec.json` discipline) was confirmed present in
`prompt_drafter.txt` before launch.

Server configured `--grace-seconds 240` cold start before the 60s human pick
clock arms. Failure modes now on the board across four runs: #10 human
next-pick math, #11 drafter off-fixture player, #12 human rec-scan, #13
drafter process death.

## Timeline (UTC; matches server log)

| Time (UTC) | Event |
|---|---|
| ~03:28 | Drafter launched (pid 9199), backgrounded `pi --mode json -p prompt_drafter.txt`. |
| 03:29:10 | `drafter_ready` written; Drafter watcher armed. Human confirmed `pre_draft`, then `POST /start`. |
| 03:29:~ | Draft STARTED (24 keepers inserted; 228 spendable on board). |
| 03:29–03:33 | Bots take P1–P7 (McCaffrey, Nacua, Robinson, Gibbs, Achane, Kyren Williams, McBride). |
| ~03:33:32 | **Drafter rec pick 8: St. Brown (7547) in `current_rec.json`. Human clicked — OK (server ts 03:33:32).** |
| 03:33:33 | Drafter audit-logs forward rec for pick 17: Josh Jacobs (5850) to `recs.jsonl`. |
| ~03:33:33 | Drafter's watch child exits; pi-monitor `emitDirect` throws stale-ctx error → **Drafter process dies**. `current_rec.json` for pick 17 never written. |
| 03:33:32–03:34:32 | Bots take P9–P16 (Chase Brown, Taylor-K, Henry, Smith-Njigba-K, Allen, Chase, Barkley, Jeanty). Pick 17 (R2 slot 5 = roster 5) goes on the 60s clock. |
| 03:34:32 | Clock expired with no click → `voided_pick_clock`. Human stopped clicking per protocol. |
| 03:34:33 | Drafter `{"event": "done", "status": "voided_pick_clock"}` (already dead; child pid gone — no manual kill needed). |

## Pick-by-pick table (run #13)

| Rd | Pick | Player | Pos | Type | Source |
|---|---|---|---|---|---|
| 1 | 8 | Amon-Ra St. Brown (7547) | WR | live | drafter rec in `current_rec.json`, clicked verbatim |
| 2 | 17 | *(voided — clock expired)* | RB | **VOIDED** | drafter rec existed in `recs.jsonl` only (Jacobs 5850); never promoted to the contract file |
| 3–15 | — | not reached | — | — | — |
| 7 | 80 | Stefon Diggs | WR | keeper | pre-seeded (auto-resolved) |
| 14 | 161 | Sam Darnold | QB | keeper | pre-seeded (never reached) |

Live picks clicked this run: **1 of 13**. Human overrides: **0**.
No picks beyond round 1 accepted.

## Drafter hit rate

- Turns reached: **1** (pick 8). Rec valid, correct id (7547), on time; clicked.
- Turns served post-crash: **0** (pick 17 onward). Drafter dead before delivery.
- Failure attribution: **100% Drafter-side** — recommendation quality was fine;
  the runtime died after exactly one turn's delivery.

## Where the pipeline struggled

1. **Drafter process crash (primary cause).** The Drafter's pi session ran its
   watcher via the monitor tool (`watch-picks` child under `pi --mode json`).
   When that child exited after the pick-8 turn, the monitor extension threw an
   unhandled error (`This extension ctx is stale after session replacement or
   reload` at `emitDirect → sendMessage`) and the whole Drafter process died.
   One good turn delivered, then silence — and a 60s clock does not wait.
   Contributing trigger, observed directly from the harness: the watcher's own
   last streamed event was `no VORP data for season 2026 — run stats vorp
   --season 2026 first` — this environment had never materialized VORP data, so
   the watcher's board render failed and its child exited; the exit path is
   exactly where the stale-ctx crash fired. So the crash was downstream of a
   missing-data condition, not a spontaneous failure.
2. **Audit log ≠ delivery.** The Drafter wrote the pick-17 rec to `recs.jsonl`
   (Josh Jacobs, 5850) at 03:33:33 — but the Human contract is
   `current_rec.json`, and that file never got a pick-17 payload. Even a
   perfect brain is worthless until the payload lands in the exact file the
   Human strips, before the pick number ticks over.
3. **Bots were fast and the clock is unforgiving.** P9–P16 took <60s total
   (bots plus auto-resolved keepers), so pick 17's clock armed almost
   immediately after pick 8 and ran its full 60s to void.
4. Carried from #12, still open: keeper rows in `/picks` poison naive
   next-pick math (recovered again this run); no `seq`/supersede marker on
   Drafter rec lines (misleading to any consumer using `tail`).

## Retro

Four distinct failure modes across four runs now:

- #10 human next-pick math
- #11 drafter off-fixture player (phantom DEF)
- #12 human rec-scan (tail vs backward scan)
- **#13 drafter runtime death (pi stale-ctx crash) after one good turn**

Recurring pattern: the *brain* keeps being correct and the *glue* keeps
failing. In #11 and #13 the kill originates in the long-running background
process (`pi --mode json` + watcher), which either advises off-fixture or
itself dies — neither recoverable from the Human side on a 60s clock.

Cheapest fixes before the next re-run, in order:

1. **Decouple rec delivery from the pi session lifetime.** Move
   `current_rec.json` writing into a small, stateless worker inside the wargame
   harness that consumes each turn's payload and never depends on the Drafter
   process surviving. In the extreme, have a supervisor auto-restart the
   Drafter on exit so a post-crash turn can still be served. Highest leverage;
   fixes both #11-style and #13-style kills.
2. **Add a `seq`/`supersedes` marker to every rec line** so any consumer can
   match "the newest line for the CURRENT pick" — never bare `tail`.
3. **Seed a real DEF tier into the fixture** so rounds 12+ are testable and
   #11 cannot recur.
4. Consider tightening the grace window to ~40s after the Human's actual ready
   signal rather than a fixed 240s so cold-start slack is not mistaken for
   budget.

Strategy notes: top-of-board shape through turn one matches #10/#12 exactly
(ARSB, with Jacobs as the planned round-2 swing) — the brain is deterministic
run-over-run and ready for precisely its first turn. The harness has now failed
to carry it to turn two in two different ways (#12 human scan, #13 drafter
death). A real draft rehearsal should not be attempted until fixes 1–2 land.

No code, data, or wiki changes made by this run. File intentionally left
uncommitted for review.