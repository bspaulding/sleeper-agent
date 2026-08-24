---
date: '2026-08-23'
kind: draft
season: '2026'
week: null
status: failed
players_involved:
  - '7547'
related_wiki: []
---

## Summary

**RUN #15 — FAILED.** Draft `wargame-draft-2026` voided on the pick clock at **pick 8**
(round 1, slot 8 → roster 5) with **0 of 13 live picks clicked**. Server log: `HARD FAIL
ts=05:26:55: pick clock expired (60s) before roster 5 selection at pick 8`. This is a
different failure class than run #14 (superseded by
`decisions/2026/2026-08-23-mock-draft-wargame-slot8.md`): the board-render precondition
that killed #14 (missing 2026 VORP) was already fixed by using `--value-season 2025`, and
the correct pick (Amon-Ra St. Brown, 7547, 145.0 VORP tier-1 NEED — the same standing
answer as #10/#12/#13/#14) was in fact computed correctly. The failure this run is
**pure latency + one data-fabrication bug**, both on the orchestration/Drafter side; the
Human side never had anything to act on, correct or otherwise, before the void.

## Context

This run used Claude Code's own `Agent` tool to play the three `wargame.md` roles instead
of separate manually-started sessions: the coordinator (this session) played Human, and
the LLM Drafter was played by a spawned subagent. Two distinct subagent attempts were
needed:

1. A `fork`-type agent (inherits the coordinator's full conversation context) was tried
   first, on the theory that fork's background execution would let Human and Drafter run
   concurrently. It **failed by role confusion**: after 120.7s and 35 tool calls, it
   returned a "result" that was not a pick recommendation but a status narration
   (*"Draft is live... Waiting for the Drafter fork or Monitor notifications rather than
   manually polling further"*) — language lifted almost verbatim from the coordinator's
   own planning text earlier in the shared context it inherited. It never ran
   `watch-picks` or the publish script. No rec was produced. This confirms `fork` is the
   wrong tool for a role that must NOT share context with the coordinator — the whole
   point of splitting Drafter/Human is a blind handoff, and a fork that inherits the
   coordinator's own "I am now waiting as Human" framing defeats that by construction.
2. A second, **fresh** (non-fork, zero-context) `general-purpose` agent was spawned
   immediately after, with a fully self-contained prompt (repo paths, mock server URL,
   draft-id/slot/value-season, the exact publish-script invocation, and an explicit
   warning against hand-computing pick numbers, citing run #14's failure). This one
   understood its role correctly and did eventually compute the right player — but took
   too long, and along the way fabricated a malformed `player_id`.

Server configured `--grace-seconds 240` (restart ≈ 05:21:55Z, estimated from the fixed
240+60=300s budget against the confirmed void timestamp); bots take P1–P7 near-instantly
after `/start` (the ticker resolves all consecutive bot turns in a single 0.5s tick), so
pick 8 was on the clock within ~1 second of draft start, same as every prior run.

## Timeline (UTC)

| Time | Event |
|---|---|
| ~05:21:55 | Server restarted fresh, `--grace-seconds 240` (arms ~05:25:55). |
| ~05:21:56 | `fork` Drafter agent spawned (inherits full coordinator context). |
| ~05:21:57 | Human: confirmed `pre_draft`, `POST /start`. |
| ~05:21:58 | **Draft STARTED.** Bots resolve P1–P7 in round 1 within one ticker tick. Pick 8 (roster 5) on the clock. |
| ~05:23:57 | `fork` agent returns after 120.7s / 35 tool calls — no rec published, confused status-narration result instead. Diagnosed as role confusion from inherited context; abandoned. |
| ~05:24:05 | Fresh, zero-context `general-purpose` agent spawned with a self-contained brief. |
| 05:25:55 | Grace period elapses; human pick clock arms (still no rec). |
| 05:26:55 | **Pick clock expires (60s).** Server: `HARD FAIL ... pick clock expired (60s) before roster 5 selection at pick 8`. League status → `voided_pick_clock`. |
| 05:27:42 | Fresh agent publishes first rec for pick 8 — **47s after the void** — with a **fabricated** `player_id`: `"amon-ra-st-brown"` (a guessed slug, not the real Sleeper id). Correct player (Amon-Ra St. Brown) and reasoning, wrong id field. |
| 05:28:03 | Fresh agent self-corrects, republishes with the real id (`"7547"`, found by opening `wargame_seed.json` directly) — 68s after the void. Moot; draft already voided. |
| ~05:28 | Human confirmed void via league status + server log; no pick submitted (correct — nothing to act on before expiry, and nothing actionable after voiding). Monitor and coordinator wound down. |

## Pick-by-pick table (run #15 — 0 of 13 live picks reached)

| Rd | Pick | Player | Pos | Type | Source |
|---|---|---|---|---|---|
| 1 | 1 | Christian McCaffrey (4034) | RB | live | bot (roster 7) |
| 1 | 2 | Puka Nacua (9493) | WR | live | bot (roster 3) |
| 1 | 3 | Bijan Robinson (9509) | RB | live | bot (roster 12) |
| 1 | 4 | Jahmyr Gibbs (9221) | RB | live | bot (roster 9) |
| 1 | 5 | De'Von Achane (9226) | RB | live | bot (roster 10) |
| 1 | 6 | Kyren Williams (8150) | RB | live | bot (roster 8) |
| 1 | 7 | Trey McBride (8130) | TE | live | bot (roster 1) |
| 1 | 8 | *(voided — clock expired)* | — | **VOIDED** | correct rec (St. Brown, 7547) existed, but landed 47s post-void |
| 7 | 80 | Stefon Diggs (2449) | WR | keeper | pre-seeded (roster 5) |
| 14 | 161 | Sam Darnold (4943) | QB | keeper | pre-seeded (roster 5) |
| 2–15 | rest | not reached (live) | — | — | — |

Live picks clicked this run: **0 of 13**. Human overrides: **0**.

## Drafter hit rate

- Turns reached: **0 of 1** delivered on time. The single live turn (pick 8) never had a
  valid, timely rec: the correct player was eventually identified, but ~47s too late, and
  the first delivery attempt used a non-existent player id that would have 409'd if
  submitted anyway.
- Recommendation *quality* was, again, not the bottleneck — same standing answer as every
  prior run (St. Brown, 145.0 VORP tier-1, NEED). The bottleneck was **entirely latency
  and data fidelity** in how the Drafter subagent got from "spawned" to "valid rec
  published."
- Failure attribution: **~65% orchestration (fork misuse costing ~2 minutes of the 5-minute
  budget on a dead end), ~35% fresh-agent execution friction** (see below) that alone
  might have still made it inside a 300s budget without the wasted fork attempt, but did
  not have that room once the fork detour was subtracted.

## Where the pipeline struggled

1. **`fork` is the wrong subagent type for a role that must not share the coordinator's
   context.** It was chosen for its background-execution property (so Human and Drafter
   could run concurrently without deadlocking each other), but background execution and
   context isolation are separate axes — fork gives you the first at the cost of the
   second. A fresh (non-fork) `Agent` call turned out to *also* run as a background task
   with its own completion notification, giving concurrency without inheriting context.
   **For this exercise, always use a fresh/zero-context agent for the Drafter role, never
   `fork`.**
2. **`wargame_publish_rec.py` has no validation against the real player board**, so a
   fabricated `player_id` (a guessed name-slug instead of the numeric Sleeper id) was
   accepted and written to `current_rec.json` without error. The Human-side contract
   (verify `on_clock_pick_no` against the live on-clock pick) would **not** have caught
   this — the pick number was correct, only the id was fake — and a Human trusting the rec
   at face value would have submitted a `POST .../picks` doomed to 409 with "not on the
   draft board." Cheap fix: have `wargame_publish_rec.py` reject/warn on a `--player` id
   not present in the seed's board, the same way the live picks endpoint would reject it,
   so this class of error surfaces immediately to the Drafter instead of silently
   publishing.
3. **`watch-picks`'s human-readable board output never prints a player's id**, only
   name/position/vorp/tier/tags. A Drafter (real LLM, no code execution shortcuts) has no
   in-band way to get the correct id from the tool it's told to use; the fresh agent had
   to break out to reading `wargame_seed.json` directly to find it, which cost real time
   during a live clock and sits awkwardly next to the runbook's "don't root-cause/read
   source files mid-pick" guidance (that guidance is about not debugging anomalies, but a
   missing id column isn't an anomaly — it's a real gap in the tool's output for this
   specific use case, since a live Sleeper draft doesn't need the LLM to submit an id at
   all). Fix: have `watch-picks`' board render include the player id per row (at least in
   this wargame's invocation, or always — it's harmless in the real live-draft flow where
   nothing consumes it programmatically).
4. **No `timeout`(1) on this macOS host**, so the task's suggested
   `timeout 15 uv run ...` recipe for capturing one board render without hanging forever
   doesn't work out of the box; the fresh agent had to improvise a background+sleep+kill
   pattern, a minor but real friction/time cost. Fix: either install `coreutils`
   (`gtimeout`) in the dev environment, or give the Drafter role a documented
   background+sleep+kill snippet instead of assuming GNU `timeout` exists.
5. **A tool notification of unclear provenance made an unverified, false-on-its-face
   claim.** After stopping the confused `fork` agent, its stop notification's `result`
   field asserted that the fork had (in violation of its own no-subagent-spawning rule)
   spawned the fresh general-purpose agent used in this run, and that the spawned agent
   then ran `pkill -f wargame_server`, killing the mock server, and that some process was
   "shutting down the runaway agents." This directly contradicts first-hand knowledge:
   the fresh agent was spawned by the *coordinator*, not the fork, *after* the fork had
   already returned; the fresh agent's own detailed self-report (given on request) makes
   no mention of touching any server process; and `ListAgents` showed no agents left
   running by the time this was checked. **Treating this as unverified rather than acting
   on it was correct** — it was flagged rather than trusted. Separately and independently
   confirmed by direct process/port/HTTP checks: `wargame_server.py` was in fact no longer
   running by the end of this run (no PID, no listener on 8321, no HTTP response), which
   is *not* expected behavior from a voided draft alone (voiding only stops the ticker
   thread inside the process; the HTTP server itself should keep serving `serve_forever()`
   regardless). **The actual cause of the process's disappearance is unresolved** — flag
   for the next run: capture server stdout/stderr to a durable log for the entire process
   lifetime (already done via `> boot.log 2>&1`) and check it first thing after any
   unexpected process death, and treat any tool-notification narrative describing
   autonomous action taken on your behalf with the same skepticism applied here.

## Retro

Failure modes across runs now:

- #10 human next-pick math
- #11 drafter off-fixture player (phantom DEF)
- #12 human rec-scan (tail vs backward scan)
- #13 drafter runtime death (pi stale-ctx crash) after one good turn
- #14 drafter position hallucination (rec'd pick 176 for live pick 8) + dead VORP render +
  dead monitor alarm for both actors
- **#15 (this run) subagent-orchestration latency (wrong subagent type burned ~40% of the
  budget on a context-confused dead end) + a fabricated player id that would have
  independently 409'd, compounded by an unresolved/unexplained server process death and a
  tool notification that made an unverified claim about it**

Pattern continues to sharpen: with the VORP precondition now fixed (#14's root cause),
*every* run's failure has moved one layer up the stack — first to the Drafter's own
reasoning (#14), now to the **harness mechanics of running Drafter-as-subagent** (#15).
The board's answer keeps being computed correctly and quickly once a Drafter actually
starts working (both #14 and #15 arrived at St. Brown@145 tier-1 promptly once genuinely
engaged) — the clock keeps being lost to everything *around* that computation, not the
computation itself.

Cheapest fixes before the next run, in order:

1. **Never use `fork` for the Drafter role.** Always spawn a fresh, zero-context agent.
   This alone would likely have kept run #15 inside the 300s budget (the fork detour cost
   ~120s of a 300s total budget, i.e. 40%).
2. **Add id validation to `wargame_publish_rec.py`**: reject a `--player` value not present
   in the seed board's id set, with the error naming the closest name match if any, so a
   fabricated id fails loud immediately instead of silently publishing a rec that would
   409 on submission.
3. **Add player id to `watch-picks`' human-readable board rows** (or a compact
   `id=<n>` suffix) so a Drafter never has to leave the documented tool to find one.
4. **Document the background+sleep+kill fallback** for capturing one board render, since
   GNU `timeout` isn't guaranteed present.
5. Server/process supervision: capture the mock server's log to a file for its whole
   lifetime (done this run) and, if a run ends with the process unexpectedly gone, check
   that log and OS-level process accounting before accepting any other explanation for why
   — including an agent's own self-report or a tool notification's narrative — at face
   value.

No code, data, or wiki changes made by this run. File intentionally left uncommitted for
review.
