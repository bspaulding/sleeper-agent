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
  - wiki/team/draft-strategy.md
  - wiki/team/keeper-strategy.md
---

## Summary

**RUN FAILED — draft voided on the pick clock at pick 17 (round 2) after one
successful live pick.** Draft `wargame-draft-2026` (slot 8, roster_id 5, snake,
12 teams, 15 rounds) ended `voided_pick_clock`: "HARD FAIL: pick clock expired
(60s) before roster 5 selection at pick 17" (server log, ~18:13:08 local).
Final state: **38 of 180 picks** — 24 seeded keepers + 14 live picks. Roster 5
live picks: **1 of 13** (St. Brown at 1.08); my keepers Diggs (#80) and Darnold
(#161) were harness-seeded as usual.

This file supersedes the same-day retro previously at this path, which recorded
a failure *before* any pick (that run's draft voided at pick 8 during role
bootstrap against a server with no cold-start grace). This run got materially
further: turn 1 was recommended, clicked, and confirmed inside the window.
The failure moved to steady-state turns — and it is a latency failure, not a
correctness one.

## Pick-by-pick table

Live picks only through void plus both roster-5 keepers ("bot cascade" =
auto-picked by `make_selection` immediately after my click, same wall-clock
second).

| Rd | Pick | Slot | Roster | Player | Pos | Type | Source |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | 7 | Christian McCaffrey | RB | bot | — |
| 1 | 2 | 2 | 3 | Puka Nacua | WR | bot | — |
| 1 | 3 | 3 | 12 | Bijan Robinson | RB | bot | — |
| 1 | 4 | 4 | 9 | Jahmyr Gibbs | RB | bot | — |
| 1 | 5 | 5 | 10 | De'Von Achane | RB | bot | — |
| 1 | 6 | 6 | 8 | Kyren Williams | RB | bot | — |
| 1 | 7 | 7 | 1 | Trey McBride | TE | bot | — |
| 1 | 8 | 8 | 5 | Amon-Ra St. Brown | WR | **human click** | drafter-rec ✓ |
| 1 | 9 | 9 | 2 | Chase Brown | RB | bot | bot cascade |
| 1 | 11 | 11 | 11 | Derrick Henry | RB | bot | bot cascade |
| 1 | 13 | 13 | 4 | Josh Allen | QB | bot | bot cascade |
| 1 | 14 | 3 | 11 | Ja'Marr Chase | WR | bot | bot cascade |
| 1 | 15 | 6 | 6 | Saquon Barkley | RB | bot | bot cascade |
| 1 | 16 | 7 | 2 | Ashton Jeanty | RB | bot | bot cascade |
| 2 | 17 | 8 | 5 | — | — | **VOIDED (my clock expired)** | rec arrived ~5s late |
| 1 | 10 | 9 | 6 | Jonathan Taylor | RB | keeper (seeded) | — |
| 1 | 12 | 12 | 4 | Jaxon Smith-Njigba | WR | keeper (seeded) | — |
| 2–14 | various | — | various | 22 more keepers incl. Diggs #80 / Darnold #161 (mine) | — | keeper (seeded) | — |

## Drafter hit rate

- Recommendations emitted: **2** (`recs.jsonl`), plus the terminal done event.
- Turn 1 (pick 8): rec arrived in time (ts 18:12:02 local, launched ~40s
  earlier); rationale sound (board-best VORP tier-1 WR at 0/2-WR need, no
  flags). Human accepted as-is → clicked → 200 OK. **Hit: 1/1 actionable.**
- Turn 2 (pick 17): rec arrived ts 18:13:11 — **~65s after my pick-8 click,
  ~5s past expiry**. Never actionable. **0/1. Timely-rec rate: 1/2 (50%).**
- Zero human overrides; zero 409s; no kept-player/DEF/INJ errors in accepted
  picks.

## Where the pipeline struggled

1. **Fatal: inter-turn recommendation latency (~65s) exceeds the hard 60s
   clock.** Because `make_selection` runs the entire bot cascade synchronously,
   my next turn begins the instant my POST lands — the drafter effectively has
   60s from my previous click to poll state, fetch the board, reason, and emit.
   Turn 1 fit inside the new 90s cold-start grace (default `--grace-seconds`,
   landed since the last retro — ask (a) partially addressed); turn 2 did not.
2. **The late rec was also mislabeled**: its `on_clock_pick_no` said **8**
   when the on-clock pick was **17**. Even if timely, the accept rule
   ("newest rec matching on_clock_pick_no") would have found no match. The
   drafter appears not to have re-derived the pick number after the bot
   cascade jumped the board past its cached state.
3. **Recommendation churn under stale state:** the same late line flipped the
   pick-8 call from St. Brown to Chase Brown "superseding" a pick already
   made. Harmless here (pick locked), but newest-wins semantics + stale
   pick-number tracking is a bad combination if a retry/409 path ever hits it.
4. **Environment reset cost (pre-run):** a stale server from the prior attempt
   still held port 8321 with an already-voided draft; the first drafter launch
   correctly detected the terminal state and exited. Recovery required killing
   the stale pid and restarting via `cd cli && uv run python
   scripts/wargame_server.py --seed scripts/wargame_seed.json` (bare `python3`
   fails on module path). All pre-draft, so it didn't consume clock — but it's
   a repeatable footgun between attempts.
5. **What worked:** keeper seeding, slot→roster math, the 90s grace (turned
   certain turn-1 death into a clean first pick), synchronous bot cascade
   (state jumps are at least deterministic), unambiguous void semantics, and
   stop-on-void honored by both roles (drafter appended its done event and
   exited; I stopped clicking immediately).

## Retro

- Third wargame run, third failure — but the checkpoint moved (void-at-pick-8
  → pick made → void-at-pick-17). The binding constraint is now clearly
  **drafter per-turn latency vs. the 60s clock**, not bootstrap.
- Concrete asks before re-running: (a) drafter must emit within ~30–40s of
  each turn start — cache board state between turns instead of refetching;
  (b) recompute `on_clock_pick_no` at emit time, never reuse a cached value;
  (c) consider a per-turn grace (clock starts at first poll after arming, or
  90s on every roster-5 turn rather than once per server);
  (d) add a startup guard to the launch script: detect/port-clear a stale
  server before starting fresh.
- Strategy notes: St. Brown at 1.08 stands up fine on the recorded board
  (tier-1 VORP, WR need given only keeper Diggs). The drafter's abandoned
  Chase-Brown case (RB scarcity) is a real debate but moot — the pick was
  locked and defensible either way. Keeper posture unchanged.

No code, data, or wiki changes made by this run. File left uncommitted for
review.
