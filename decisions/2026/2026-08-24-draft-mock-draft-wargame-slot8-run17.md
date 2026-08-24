---
date: '2026-08-24'
kind: draft
season: '2026'
week: null
status: failed
players_involved: []
related_wiki: []
---

## Summary

**RUN #17 — FAILED, 0 of 13 live picks made.** Draft `wargame-draft-2026` voided on the pick
clock at **pick 8** — round 1, slot 8 (roster 5), the very first live turn of the draft —
before either the Drafter or the Human ever got a chance to act on it. This is a new failure
mode, distinct from every prior run (#10-16): it isn't a bad recommendation, a fabricated id,
a fork-context leak, or slow in-draft deliberation. It's **coordinator/Human-side setup
latency consuming the entire grace-plus-clock budget before the first live pick was ever
observed**, because the coordinator called `POST /start` and then immediately did further
setup work (spawning the Drafter agent, and — critically — asking the operating human a
clarifying question via a blocking prompt) instead of confirming a live tracking loop was
already running first. Ties the previous worst outcome (0/13, before run #15's fork fix).

## Context

Prerequisites were already satisfied coming into this run — 2025 VORP and `data/bigboard/2025.csv`
both existed from prior work this session, so this run (unlike #14) never got the chance to hit a
precondition failure; it never got that far.

Sequence of coordinator actions after starting the server (`--grace-seconds 90`):

1. `rm -rf /tmp/wargame`, confirmed seed/roster mapping, confirmed `pre_draft` via curl — fast,
   no issue.
2. Spawned the LLM Drafter as a fresh, zero-context `general-purpose` agent (per run #15/#16's
   fix — correct call, not itself a problem) with a large self-contained briefing. Agent spawn +
   the agent's own first steps (reading `draft.md`, standing up its own `watch-picks` loop) takes
   real wall-clock time that was not budgeted against the grace period.
3. `POST /start` — called immediately after the spawn kicked off, which is correct per the
   runbook ("spawn it immediately after (re)starting the server, before calling `/start`" — this
   was followed correctly for the *server* restart, but `/start` itself was then not immediately
   followed by attaching a live tracking loop).
4. Stood up the Human-side `watch-picks` Monitor — this part was fine and fast.
5. **Then asked the operating human a clarifying question (`AskUserQuestion`, about auto-submit
   vs. confirm-first policy) before checking whether a pick was already on the clock.** This step
   blocks on a real human's response time, which is unbounded relative to a 60s pick clock — by
   the time the question was answered and control returned, the first live pick (pick 8, since
   bots resolve round-1 picks 1-7 near-instantly) had already armed and expired its 60s clock
   unattended.

The first Monitor event (a bulk catch-up dump of all already-filled picks, including all 24
pre-seeded keepers scattered non-monotonically through the pick sequence) arrived *after* the
void had already happened, and a direct league-status check confirmed
`status: "voided_pick_clock"` with the server log reading:

```
wargame draft wargame-draft-2026: 24 keepers seeded, 228 available; pick clock arms after 90s grace; humans wait at roster_id=5
[draft] STARTED — keeper picks inserted
HARD FAIL ts=21:03:23: pick clock expired (60s) before roster 5 selection at pick 8
```

No per-step wall-clock timestamps were captured during setup (nothing was logged besides the
final `HARD FAIL` line), so exact durations for steps 1-5 above aren't reconstructable — but the
total elapsed time from server boot to void is bounded tightly by the server's own parameters:
90s grace + 60s pick clock ≈ 150s, with round-1 bot picks 1-7 consuming effectively none of that
window (consistent with their "instantly" resolution in run #16 too). That ~150s budget was
entirely consumed by coordinator setup steps, not by any Drafter or Human deliberation — the
Drafter agent's own last recorded action before being stopped was still re-orienting itself on
the ambiguous bulk Monitor dump, and the Human role never got as far as checking
`current_rec.json` for a first time before the void was discovered.

## Live picks this run (0 of 13 clicked)

None. Void occurred on the first live turn.

## Root cause

**Process-ordering bug on the coordinator/Human side, not a Drafter or mechanics bug.** The
runbook's "don't leave a gap" warnings (grace counts from process start; spawn the Drafter
immediately after restart, before `/start`) were followed for the *drafter-spawn-before-start*
ordering, but there's a second ordering hazard the runbook doesn't yet call out explicitly:
**nothing should happen between `POST /start` and having a live tracking/verification loop
actually attached and confirmed running — including questions to the operating human.** A
blocking human-facing prompt is exactly the kind of step whose duration is unbounded and
unbudgeted against a 60s clock; it must happen either before `/start` or be deferred until after
the first live pick's outcome is already known.

## Cheapest fixes before the next run, in order

1. **Sequence hard rule: after `POST /start`, the coordinator's very next action must be
   attaching/confirming the live Monitor watch-picks loop — no other tool calls (including
   `AskUserQuestion` or any other human-facing prompt) in between.** Any policy questions for the
   operating human (auto-submit vs. confirm-first, etc.) belong *before* `/start`, alongside the
   pre-draft league-status confirmation, not after.
2. **Treat Drafter-agent spawn as part of the timed setup window, not free.** Spawning a fresh
   zero-context agent and having it read `draft.md` + stand up its own watch loop is not
   instantaneous; either spawn it with enough `--grace-seconds` margin to comfortably absorb that
   cold start (this run used 90s, run #16 used 240s and had no trouble on the *first* turn), or
   confirm the Drafter has published a pick-8 rec (or is actively polling) before calling
   `/start` at all.
3. **A bulk catch-up Monitor dump on first attach is a signal, not just noise** — when the very
   first `watch-picks` event is a large non-monotonic dump (all keepers plus multiple rounds), a
   void may already be in progress; the coordinator should immediately cross-check league status
   in that case rather than parsing the dump for "what pick is next."
4. Consider whether `wargame.md` should say explicitly, in the "Running it" section, that no
   Human-facing questions/pauses belong between `/start` and the tracking loop being live — this
   run's mistake is exactly the kind of thing worth a one-line callout so it isn't rediscovered
   again.

## Retro

Failure modes across runs now:

- #10 human next-pick math
- #11 drafter off-fixture player (phantom DEF)
- #12 human rec-scan (tail vs backward scan)
- #13 drafter runtime death (pi stale-ctx crash) after one good turn
- #14 drafter position hallucination (rec'd pick 176 for live pick 8) + dead VORP render +
  dead monitor alarm for both actors
- #15 subagent-orchestration latency (fork context confusion) + fabricated player id
- #16 drafter pacing failure on a low-signal/tied-value decision (6/13 picks landed — best
  result yet at that point)
- **#17 (this run) coordinator/Human-side setup-ordering failure — a blocking human-facing
  question landed between `/start` and the tracking loop going live, burning the entire
  grace+clock budget before either role ever observed the first live pick. 0/13, ties the
  prior worst.**

This is a regression in outcome (0/13 vs. run #16's 6/13) but not evidence that run #16's
fixes stopped working — it's a different layer of the stack failing (pre-draft coordination
timing) that the prior 6 runs never happened to exercise, mostly because none of them had a
blocking human-facing prompt land in that specific window. Worth fixing before the next run
since it's cheap (a sequencing rule, not a design change) and otherwise unpredictably
reintroducible any time the coordinator reaches for `AskUserQuestion` at the wrong moment.

No code, data, or wiki changes made by this run beyond this decision-log entry.
