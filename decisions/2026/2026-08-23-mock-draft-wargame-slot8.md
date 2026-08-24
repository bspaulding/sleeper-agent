---
date: '2026-08-23'
kind: draft
season: '2026'
status: failed
players_involved:
  - '7547'
  - '9224'
related_wiki:
  - wiki/team/roster-philosophy.md
---

## Summary

**RUN #14 — FAILED.** Draft `wargame-draft-2026` voided on the pick clock at
**pick 8** (round 1, slot 8→roster 5) with **0 of 13 live picks clicked**.
Final status `voided_pick_clock`; server log: `HARD FAIL ts=04:30:26: pick
clock expired (60s) before roster 5 selection at pick 8`. This file supersedes
the run-#13 retro previously at this path.

Run #14's failure is **Drafter-side (wrong-pick hallucination + dead alarm
path)**: the Drafter never delivered a valid rec for the actual on-clock pick
(8). It spent the full cold-start + clock window fumbling, then published a
rec for **pick 176 — its own final-round slot — not the live pick 8**. A
*correct* pick-8 recommendation (Amon-Ra St. Brown, 7547) did exist in
`recs.jsonl`, produced by the leftover `watcher2.py` from an earlier run, but
it never reached `current_rec.json` — the only file the Human is allowed to
act on. The Human followed protocol exactly (polled, refused the stale/wrong
rec, made no pick decision of its own), the clock expired, and the draft
voided.

## Context

Clean reset to `pre_draft` between runs (keepers Diggs@80, Darnold@161
re-seeded; `recs.jsonl`, `current_rec.json`, `drafter_ready`, server.log
removed). Server configured `--grace-seconds 240` (from server start) before
the 60s human pick clock arms; bots take P1–P7 almost instantly after `/start`
because this league's bot personas pick with the ticker's 0.5s poll.

Two anomalies interacted this run:

1. **A leftover `watcher2.py` (pid 5603, started 7:45PM, never killed by the
   reset scripts) kept running across resets.** It has *correct* draft
   geometry (`next_pick_no` from gaps, `owner()` via slot map) and, at
   `04:26:45Z` — 2s after draft start — computed pick 8, ran the board, chose
   Amon-Ra St. Brown (7547, 145 VORP tier-1 [NEED]) and appended a
   **verified rec** to `recs.jsonl`. It does **not** write
   `current_rec.json`, so its (correct) output was invisible to the Human
   contract channel. It also wrote the final `{"event":"done","status":...}`
   audit line at `04:30:26Z` when the draft voided.
2. **`draft watch-picks --me` renders are broken in this environment**: the
   board render raises `no VORP data for season 2026 — run stats vorp
   --season 2026 first` (2026 VORP was never materialized here — same
   condition that aborted run #13). The watcher child exits on that render,
   so the monitor alarm path is dead for BOTH the Drafter and the Human:
   every monitor spawned across all runs has a 0-byte stderr and delivered
   zero events (27 stale `.stderr` files in `~/.pi/agent/monitor/`), and this
   Human's alarm (mon_b03f0001) was dead by end-of-run with no output.

## Timeline (UTC; local PDT here was UTC−7)

| Time (UTC) | Event |
|---|---|
| 04:25:0x | Reset: server restarted, `--grace-seconds 240` (arms ~04:29:05). |
| 04:26:0x | Drafter launched (pid 10572), backgrounded `pi --mode json -p prompt_drafter.txt`. |
| 04:26:2x | `drafter_ready` written. Human confirmed `pre_draft`, then `POST /start`. |
| 04:26:43 | **Draft STARTED** (31 rows visible = 7 live picks + 24 keeper rows, all keeper pick_nos > 8, so smallest missing pick_no is 8; 180-pick space). |
| 04:26:44-45 | Bots take P1–P7 (McCaffrey, Nacua, Bijan, Gibbs, Achane, Kyren Williams, McBride). **Pick 8 = roster 5 on clock.** |
| 04:26:45 | Leftover `watcher2.py` computes pick 8, recs **Amon-Ra St. Brown (7547)** → `recs.jsonl` only (`verified=True`). Never reaches `current_rec.json`. |
| 04:26:45–04:30:12 | Drafter fumbles: `watch-picks` render fails (`no VORP data for season 2026`); checks own monitor stderr (empty); `find`/`ls`; attempts pandas/pyarrow reads of `data/sleeper/players.parquet` (3 dependency attempts) to resolve Chase Brown (9224). Violates its own "No extra analysis calls" rule from the first second. |
| 04:30:13 | Drafter publishes via `wargame_publish_rec.py --pick 176 --player 9224 --name "Chase Brown"` → writes `current_rec.json` (WRONG PICK; live clock is on pick 8) + appends audit line to `recs.jsonl`. |
| 04:30:14-15 | Drafter reads back and self-validates its 176 rec; then its pi session dies on the known monitor stale-ctx error (`This extension ctx is stale after session replacement or reload`, thrown from `emitDirect` on child exit — same signature as run #13). |
| 04:30:26 | Human pick clock (armed 04:29:05 + 60s) expires → server `HARD FAIL at pick 8`; status `voided_pick_clock`. Human stops clicking per protocol. Drafter already exited on its own (no kill needed). |
| 04:30:26 | `watcher2.py` appends `{"event":"done","status":"voided_pick_clock"}` to `recs.jsonl`. |

## Pick-by-pick table (run #14 — 0 of 13 live picks reached)

| Rd | Pick | Player | Pos | Type | Source |
|---|---|---|---|---|---|
| 1 | 1 | Christian McCaffrey (4034) | RB | live | bot (roster 7) |
| 1 | 2 | Puka Nacua (9493) | WR | live | bot (roster 3) |
| 1 | 3 | Bijan Robinson (9509) | RB | live | bot (roster 12) |
| 1 | 4 | Jahmyr Gibbs (9221) | RB | live | bot (roster 9) |
| 1 | 5 | De'Von Achane (9226) | RB | live | bot (roster 10) |
| 1 | 6 | Kyren Williams (8150) | RB | live | bot (roster 8) |
| 1 | 7 | Trey McBride (8130) | TE | live | bot (roster 1) |
| 1 | 8 | *(voided — clock expired)* | — | **VOIDED** | drafter rec never valid: `current_rec.json` held pick-176 rec (Chase Brown 9224) at expiry; correct rec (St. Brown 7547) existed only in `recs.jsonl` via leftover watcher |
| 2–15 | 9–180 | not reached | — | — | — |
| 7 | 80 | Stefon Diggs (2449) | WR | keeper | pre-seeded (auto-resolved) |
| 14 | 161 | Sam Darnold (4943) | QB | keeper | pre-seeded (never reached) |

Live picks clicked this run: **0 of 13**. Human overrides: **0**.
No picks beyond round 1 accepted.

## Drafter hit rate

- Turns reached: **0 of 1**. The single live on-clock turn (pick 8) was never
  served correctly: no drafter rec for pick 8 ever landed in
  `current_rec.json` (the file stayed absent until 04:30:13, when it received
  the pick-176 rec — and stayed there until void).
- The one correct rec for pick 8 was authored by the *leftover watcher2.py*,
  not the LLM Drafter, and sat in the audit channel only.
- Recommendation *quality* was never the bottleneck: both candidate picks
  (St. Brown WR @145.0 tier-1; Chase Brown RB @140.3 tier-1) are defensible
  value picks for a 0/2 RB, 1/2 WR roster. The bottleneck was **pick-number
  correctness and delivery channel**.
- Failure attribution: **100% Drafter-side** (wrong pick_no hallucinated;
  prompt rules violated: extra tool calls, rec for a pick not on the clock),
  compounded by environment bugs (2026 VORP render gap, monitor stale-ctx
  crash) that removed every working alarm path.

## Where the pipeline struggled

1. **Drafter hallucinated the draft position (primary cause).** With the
   board render dead (`no VORP data for season 2026`), the Drafter had no
   live board. It instead anchored on the *keeper fixture* (pick 161 =
   Darnold) and its own enumeration of roster 5's round-slots
   (8,17,32,…,152), and reasoned "the board printed after Darnold (pick
   161)… our next pick is 176," then hard-coded `--pick 176`. It never
   fetched `/picks` and computed the *smallest missing pick_no* (8) — the
   exact gap logic the CLI's `_next_unmade_pick_no` encodes and the fixture
   keeps requiring. It also failed its prompt's "No extra analysis calls":
   the parquet/dependency detour (3 attempts) burned the whole window.
2. **Monitor alarm path is dead for everyone.** The watcher child exits on
   the VORP render failure, and the pi-monitor extension then throws the
   stale-ctx error on child exit (`emitDirect`), killing the pi session that
   owns the monitor — this run *and* run #13, and consistent with every
   previous run's empty `mon_*.stderr` files. This Human's "on-clock alarm"
   delivered zero events all run; the Drafter's delivered zero too. The
   no-blocking-loops rule ("never wait via blocking loops") collides with an
   alarm mechanism that does not work in this environment; the Human's manual
   poll loop was the only thing that kept the clock honest.
3. **Correct rec existed in the wrong channel.** `watcher2.py`'s verified
   pick-8 rec (St. Brown) landed in `recs.jsonl` at 04:26:45 but never in
   `current_rec.json` — the Human contract. Contract discipline held on the
   Human side (absent/WRONG file → no click), and the run failed cleanly
   rather than clicking the wrong-pick rec. Still: one correct rec, one
   reachable publish script, and no path between them for 3.5 minutes.
4. **Keeper rows still poison naive next-pick math.** During polling, the
   Human observed 31 rows in `/picks` (7 live + 24 keeper) and computed
   next=32 by `len+1` before noticing the void reason said pick 8. The
   run-#13 retros's "next-pick math" open item is unchanged: any consumer
   that counts rows instead of `pick_no` gaps is misled.
5. **Current_rec.json left dirty.** The wrong pick-176 rec remained in
   `current_rec.json` after the void (the Drafter died before its
   delete-on-end step). Harmless here (Human stopped), but a stale-slot
   hazard for any subsequent run on this harness.

## Retro

Failure modes across runs now:

- #10 human next-pick math
- #11 drafter off-fixture player (phantom DEF)
- #12 human rec-scan (tail vs backward scan)
- #13 drafter runtime death (pi stale-ctx crash) after one good turn
- **#14 drafter position hallucination (rec'd pick 176 for live pick 8) +
  dead VORP render + dead monitor alarm for both actors**

Pattern sharpened: the *brain* errs on **state read**, the *glue* errs on
**liveness**, and the clock forgives neither. In #14 the Drafter had no live
board at all (VORP render), so it invented one from keeper anchors — a
hallucination that no Human-side protocol can detect (the rec was
well-formed, verified, non-empty; only the pick number was wrong).

Cheapest fixes before the next run, in order:

1. **Fix the board render precondition.** Materialize 2026 VORP (or point
   the wargame at a season that exists) so `watch-picks`/`watch board` can
   render. Without this, the Drafter has no board, the watcher child exits,
   and both monitor alarms die. This is the root enabler for everything else.
2. **Decouple rec delivery from the pi monitor lifetime (carry-over from
   #13).** The stale-ctx crash on child exit killed the Drafter again (and
   every monitor). Either stop using the extension's event path for this
   exercise or run the watcher as an independent process (like watcher2.py,
   which did NOT crash across two runs) and let the publish script own
   `current_rec.json`.
3. **Have the Drafter derive "on-clock pick" from `/picks` gap logic, never
   from the board's max row.** The fixture will keep interleaving keeper rows
   at 80/161; the only reliable signal is smallest missing `pick_no`. Export
   `_next_unmade_pick_no` as a CLI one-liner the Drafter is *required* to run
   (and re-run if the number agrees with the rec target).
4. **Human-side guard: verify the rec's pick_no against the live smallest
   missing pick_no before frame.** The Human already categorically refuses
   mismatches (did here); make that a logged, observable action rather than
   silent do-nothing so retros can distinguish "no rec" from "wrong rec."
5. Kill stray scaffolding between runs (`pkill -f watcher2.py` alongside the
   existing pkill) so a leftover correct rec in `recs.jsonl` cannot be
   mistaken for the LLM Drafter's output, and document `current_rec.json`
   cleanup after each terminal state.

Strategy notes: pick-8 value shape was again St. Brown @145 tier-1 (matches
#10/#12/#13 deterministically) — the *board's* answer was available 2
seconds into the draft; only the channel and the LLM's state-comprehension
lost it. Chase Brown @140.3 as the "RB hole" pick was a reasonable *final*-
round answer to a draft that in reality never left round 1.

No code, data, or wiki changes made by this run. File intentionally left
uncommitted for review.

## Postscript (post-void, 21:38Z)

Exactly one alarm event ever reached the Human from `mon_b03f0001` — the line
`no VORP data for season 2026 — run stats vorp --season 2026 first` — seen
~12 minutes after the void (the child `watch-picks` had been polling since
start; its board-render error finally surfaced as a streamed event). So the
monitor path is not *never* emitting — it emits the render-failure line once,
way too late, and only because the child kept retrying a dead draft. Same
takeaway as above: the alarm is unusable during a live 60s clock because its
on-my-turn render crashes (VORP gap) and its event delivery lags by minutes.
The stale child was killed at 21:38; `mon_b03f0001` is no longer registered.