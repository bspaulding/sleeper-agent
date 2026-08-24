---
date: '2026-08-23'
kind: draft
season: '2026'
week: null
status: failed
players_involved:
  - '7547'
  - '5850'
  - '5022'
  - '5892'
  - '6794'
  - '7526'
  - '4217'
related_wiki: []
---

## Summary

**RUN #16 — FAILED, but furthest yet.** Draft `wargame-draft-2026` voided on the pick clock
at **pick 89** (round 8, slot 8 → roster 5) with **6 of 13 live picks clicked** — the best
result across all runs so far (prior best was 0/13). This run applied the fix from run #15's
retro (spawn the Drafter as a fresh, zero-context agent, never a `fork`) and it worked: no
role confusion, no wasted detour, and picks 8/17/32/41/56/65 all landed cleanly, each well
inside the 60s clock. The failure this run is new and much narrower: **the 7th live turn
(pick 89) — the first genuinely low-signal, tied-value bench decision of the draft — took
the Drafter ~57.4s of the ~60s budget**, and its (correct) rec landed only 3.6s before the
clock expired, too late for the Human to verify and submit in time.

## Context

Same setup as run #15's fix: server restarted fresh (`--grace-seconds 240`), a **fresh,
zero-context** `general-purpose` agent spawned immediately after restart (before `/start`)
to play the Drafter, and the coordinator session playing Human — Monitor-wrapped
`draft watch-picks` plus a `current_rec.json` file-watch loop per turn, cross-checking
`on_clock_pick_no` against the live smallest-missing-pick_no before every submission.

The Drafter's prompt this run also explicitly told it to look up real player ids from
`wargame_seed.json`'s board (never guess a name-slug) — the run #15 fabrication bug did not
recur; every id submitted this run was correct on the first try.

One operational hiccup on the Human side (self-inflicted, not a wargame bug): the first
"wait for next rec" background loop script used a shell variable named `status`, which is a
read-only special variable in zsh (the shell this harness's Bash tool runs under) — it
failed immediately with `read-only variable: status`. Renamed to `league_status` and it
worked for the rest of the run. Worth noting in the runbook so a future run doesn't lose
time rediscovering this.

## Timeline (UTC, from server log)

| Time | Event |
|---|---|
| ~05:34:1x | Server restarted fresh, `--grace-seconds 240`. Fresh Drafter agent spawned immediately. |
| ~05:34:2x | Human: confirmed `pre_draft`, `POST /start`. Bots resolve R1 P1-7 instantly. |
| 05:38:56 | **Pick 8** (R1): Amon-Ra St. Brown (WR) — clicked. (~4.5 min after start; grace period absorbed the Drafter's cold start comfortably.) |
| 05:39:50 | **Pick 17** (R2): Josh Jacobs (RB) — clicked. (54s turnaround.) |
| 05:40:22 | **Pick 32** (R3): Dallas Goedert (TE) — clicked. (32s turnaround.) |
| 05:41:01 | **Pick 41** (R4): David Montgomery (RB) — clicked. (39s turnaround.) |
| 05:41:37 | **Pick 56** (R5): Justin Jefferson (WR) — clicked. (36s turnaround; all starters now filled.) |
| 05:42:08 | **Pick 65** (R6): Jaylen Waddle (WR) — clicked. (31s turnaround; FLEX slots now filled — roster complete except DEF/bench.) |
| 05:43:05 | Rec published for **pick 89** (R8; R7 was the pre-seeded Diggs keeper, no live turn that round): George Kittle (TE) — correct pick, correct id. **57.4s after pick 65**, only 3.6s before expiry. |
| 05:43:09 | **Pick clock expires (60s).** Server: `HARD FAIL ... pick clock expired (60s) before roster 5 selection at pick 89`. League status → `voided_pick_clock`. Human never had a viable window to verify-and-submit. |

## Live picks this run (6 of 13 clicked)

| Rd | Pick | Player | Pos | Turnaround from prior pick |
|---|---|---|---|---|
| 1 | 8 | Amon-Ra St. Brown (7547) | WR | — (first turn, grace-covered) |
| 2 | 17 | Josh Jacobs (5850) | RB | 54s |
| 3 | 32 | Dallas Goedert (5022) | TE | 32s |
| 4 | 41 | David Montgomery (5892) | RB | 39s |
| 5 | 56 | Justin Jefferson (6794) | WR | 36s |
| 6 | 65 | Jaylen Waddle (7526) | WR | 31s |
| 7 | 80 | Stefon Diggs (2449) | WR | keeper, pre-seeded |
| 8 | 89 | George Kittle (4217) — **rec published, never submitted** | TE | 57.4s (**VOIDED**) |

By pick 65, the roster was already NEED-complete (QB 1/1, RB 2/2, WR 4/2, TE 1/1 — 2 extra
WRs absorbing both FLEX slots), so pick 89 onward was pure bench/DEF value with no roster
pressure — exactly the condition that broke the Drafter's pacing.

## Drafter hit rate

- Turns reached: **6 of 7 delivered on time** (86%), a clean pass rate on every pick with a
  clear NEED signal. The one miss was the first pick with *no* NEED signal at all.
- Recommendation quality was correct on all 7 attempts, including the late one — the
  bottleneck was exclusively **latency**, not judgment or data fidelity (unlike runs #14/#15).
- Failure attribution: **Drafter-side pacing**, specifically a failure to scale deliberation
  *down* when the decision stakes are low. The Drafter's own retro (see below) confirms this
  directly: the least consequential pick of the draft took the longest to decide.

## Where the pipeline struggled

1. **Deliberation didn't scale down for low-signal decisions.** Per the Drafter's own
   post-mortem: picks 8/17/32/41 each had one obvious top-VORP player matching a clear
   roster NEED (near-mechanical), and landed in 30-55s. Pick 89 had no NEED signal (DEF not
   on the ranked board; top four candidates tied at exactly 0.0 VORP) and instead of
   recognizing "the model has no preference, just pick one," the Drafter treated the *absence*
   of a signal as a prompt to search harder — re-querying for a DEF entry with three
   different grep patterns after the first came back empty, then constructing a tiebreak
   narrative for four options it had already established were equivalent. This is the same
   family of failure as run #14's "don't root-cause anomalies mid-pick" lesson, but inverted:
   there the anomaly was a broken precondition; here there was no anomaly, just an
   information-poor decision, and open-ended search was still the wrong response.
2. **A negative search result was not treated as conclusive.** Three greps for a DEF row
   (`"  DEF  "`, `"Defense"`, `"DEF"`) against the same static 180-row output the Drafter
   already had in hand — each one a full wasted round-trip once the first came back empty.
3. **The `watch-picks` capture used a fixed sleep regardless of when the board actually
   rendered.** The background-job-plus-`sleep 10`-plus-kill pattern (documented as a
   workaround for missing GNU `timeout` on this host, per run #15's fix) always burns the
   full sleep window even if the board appeared in the first second — worth tightening to
   "kill as soon as the `<== MY PICK` marker appears in the tail," not a fixed duration.
4. **Fixed per-pick overhead (the `uv run` publish call's venv/dependency resolution) eats
   real seconds on every turn**, not just this one — it's a small, constant tax that combined
   with genuinely slow deliberation on pick 89 to close the margin to 3.6s. Not the root
   cause alone, but not free either; worth remembering when estimating how much budget is
   really available for the *judgment* part of a turn.
5. **(Minor, Human-side, self-corrected)** `status` as a bash variable name breaks under
   zsh (read-only special variable) — cost one failed background command and a rediscovery
   cycle before the fix (`league_status`). Cheap to avoid next time by not using that name at
   all in wargame Human-side polling scripts.

## Retro

Failure modes across runs now:

- #10 human next-pick math
- #11 drafter off-fixture player (phantom DEF)
- #12 human rec-scan (tail vs backward scan)
- #13 drafter runtime death (pi stale-ctx crash) after one good turn
- #14 drafter position hallucination (rec'd pick 176 for live pick 8) + dead VORP render +
  dead monitor alarm for both actors
- #15 subagent-orchestration latency (fork context confusion) + fabricated player id
- **#16 (this run) drafter pacing failure on a low-signal/tied-value decision — the first
  run to land multiple live picks (6 of 13) before voiding, and the first where recommendation
  quality was never in question at any point, only speed on exactly one turn**

The pattern keeps climbing the stack: precondition (#14) → orchestration mechanics (#15) →
now **decision-time pacing under genuine ambiguity** (#16). Every fix so far has been
necessary but not sufficient on its own — this run proves the fork fix works (6 clean picks
is real progress) while surfacing the next distinct failure mode once that layer was no
longer in the way.

Cheapest fixes before the next run, in order:

1. **Give the Drafter an explicit fast-path rule for flat/tied boards**: if the top N
   candidates are within a trivial VORP delta (e.g. <1-2 points) and/or all roster NEED slots
   are already filled, take the first clean (non-injury-flagged, non-SURPLUS) option and
   write a one-line rationale — no comparative deliberation, no re-querying. This is the
   single highest-leverage fix; it directly targets what actually happened.
2. **Treat one negative search as conclusive** — don't re-query the same static output with
   syntactic variants of a search that already came back empty.
3. **Tighten the `watch-picks` capture to exit as soon as the board renders**, not after a
   fixed sleep — checking the tail for the `<== MY PICK` marker every ~1s and killing
   immediately, rather than always waiting the full window.
4. Add `status` (and other zsh special variable names — `path`, `pipestatus`, etc.) to a
   short "don't use as a variable name in wargame Human-side scripts" note in `wargame.md`.
5. Consider whether the mock server should reset `_on_clock_since` progressively earlier for
   bench-tier rounds (i.e. a slightly longer clock deep in the draft, mirroring how real
   leagues sometimes shorten/lengthen pick clocks by round) — noted as a possible fixture
   change, not a Drafter/Human process fix, and lower priority than items 1-4 since the real
   goal is testing draft.md's live heuristics under realistic (not artificially loosened)
   time pressure.

No code, data, or wiki changes made by this run. File intentionally left uncommitted for
review.
