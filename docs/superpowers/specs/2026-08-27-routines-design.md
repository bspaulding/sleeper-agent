---
date: '2026-08-27'
status: implemented
related_decisions:
  - decisions/2026/2026-08-27-bigboard-injury-status-review.md
related_wiki:
  - league/season-2026.md
---

# Scheduled Routines: inventory, self-containment, and the news-freshness pattern

## Motivation

`IMPLEMENTATION_PLAN.md` §9 (Phase H) introduced Claude Code Routines (scheduled via the
`RemoteTrigger` API) so the CLI/skills work runs without Brad manually invoking it, and stated a
principle in passing: each Routine's prompt must be self-contained, since it wakes a fresh
reasoning pass each time rather than continuing a live conversation. That principle was never
written up as a real design constraint, and on 2026-08-27 it got violated: a separate
`sleeper-agent: news sweep` Routine was created to run 2 hours ahead of `waiver window reminder`
and `trade scouting`, so those decision routines would have fresh injury/news signal without each
redundantly researching the same players.

That was the wrong call, caught in review. A separate prep Routine reintroduces exactly what
self-containment exists to prevent:

- **A staleness gap.** The 2-hour buffer is arbitrary — if real news breaks in that window, the
  decision routine still acts on stale signal.
- **An implicit ordering dependency with no coordination.** Two independently-scheduled Routines
  have no locking, no shared transaction, and no failure signal between them. If the news-sweep
  Routine runs late, gets rate-limited, or dies mid-run (as `pre-draft prep` already did once,
  see Outcome below), the decision Routine has no way to know its input might be stale — it just
  proceeds silently.
- **Extra schedule-maintenance surface.** A fourth cron expression that has to stay coordinated
  with the two it feeds, for no benefit once the actual cost of "redundant" research turned out to
  be near zero (see below).

The fix: fold the same news-research step directly into each consuming Routine's own prompt, as
its first content step. This is genuinely free rather than redundant, because
`.claude/skills/news-research.md`'s "full sweep" mode is already checkpointed via
`wiki/news-sources.md`'s `last_swept` frontmatter field — whichever Routine runs it next only
covers what's new since the last sweep, regardless of who ran that one. Self-containment cost
nothing here; it only would have if the sweep were expensive to repeat, and it isn't.

## Design principles

1. **Every Routine prompt must be fully self-contained.** It must not assume another Routine ran
   first, ran recently, or ran at all. If a Routine needs fresh data another Routine also
   produces, both should independently produce it (via a cheap, checkpointed mechanism — see
   below), not depend on execution order.
2. **Cheap idempotent checkpoints, not shared scheduling, is how cross-Routine "don't redo work"
   gets solved.** `wiki/news-sources.md`'s `last_swept` is the working example: any Routine can
   call the same full-sweep step at any time and it degrades gracefully to "nothing new since
   last time" rather than "nothing happened because I assumed someone else did it."
3. **`environment_id` must be repo-bound.** A Routine's `job_config.ccr.environment_id` needs to
   point at an environment with actual GitHub access to `bspaulding/sleeper-agent` (via
   `session_context.sources: [{git_repository: {url: ...}}]`) or the session wakes up in a bare
   sandbox with no checkout and no git credentials and can't do anything (confirmed the hard way
   — see Outcome). `env_01NLJ4E1ykjYM4s3HTEJi3dZ` is the known-good environment as of this
   writing, shared by all four active Routines below.
4. **A live, multi-hour polling loop is not a useful Routine shape.** There is no way to watch a
   Routine's live session output from the Claude mobile app, so a Routine that only narrates state
   changes in real time (e.g. tracking a live draft pick-by-pick) provides no value if a human is
   already present and watching the same event directly. Prefer a Routine that does its work and
   reports a finished summary over one that streams a process nobody can see live.

## Routine inventory (as of 2026-08-27)

| Routine | Schedule | Purpose |
|---|---|---|
| `sleeper-agent: weekly stats/VORP sync` | Tuesdays 13:00 UTC | `stats sync` → `stats vorp` → `wiki stale` → news-research full sweep |
| `sleeper-agent: waiver window reminder` | Mondays 13:00 UTC | news-research full sweep → `waiver recommend` → judgment-gated `decisions new --kind waiver` |
| `sleeper-agent: trade scouting` | Wednesdays 13:00 UTC | news-research full sweep → `trade propose --all` → judgment-gated `decisions new --kind trade` |
| `sleeper-agent: pre-draft news sweep` | One-shot, 2026-08-29 13:00pm PT (20:00 UTC) | Follow-up injury/news check + hand-edit `data/bigboard/2025.csv` if warranted, ahead of the 3pm PT 2026 draft |

`sleeper-agent: news sweep` (the rejected separate-Routine approach above) and
`sleeper-agent: pre-draft prep` (an earlier one-shot that failed on the bad `environment_id` before
this was diagnosed) both exist in a disabled/spent state in the `RemoteTrigger` list — not deleted,
since the API has no delete action, only `enabled: false`.

## Outcome

- `pre-draft prep` (fired 2026-08-26) is the concrete evidence for principle 3: it woke up in an
  environment with no repo checkout and no git credentials, tried and failed every available
  clone path (HTTPS with no credential helper, missing `gh` CLI, an SSH attempt blocked by the
  session's permission classifier), and gave up after 14 turns having done none of its 8 planned
  steps. `RemoteTrigger`'s reported `ROUTINE_RUN_STATUS_SUCCEEDED` for that run is misleading —
  it means the session exited cleanly, not that it accomplished anything.
- The originally-broken `sleeper-agent: draft day` one-shot (same bad `environment_id`, plus a
  prompt referencing the since-retired `.claude/skills/draft.md` and a `--watch` flag that no
  longer exists on `draft board`) was repurposed into `pre-draft news sweep` above rather than
  fixed as a live tracker, per principle 4.
- `waiver window reminder` and `trade scouting`'s CLI invocations were both missing the
  now-required `--season` flag (recovered in practice via each prompt's own "check `--help` if
  stale" fallback, but fragile) — fixed alongside this pass.

## Out of scope / follow-up

- **A `freeagent` cadence Routine** — `decisions new --kind freeagent` already exists as a kind,
  but no Routine currently scouts free agency on a schedule the way waiver/trade do.
  Not designed here; add following the same self-contained + checkpointed-sweep shape if wanted.
- **An in-season equivalent of the bigboard's hand-reviewed ranking file** — waiver/trade
  valuation currently reads live VORP + roster context directly at decision time rather than a
  persisted, judgment-adjusted ranking artifact. Not needed today (no reported pain point), but if
  one emerges, the bigboard's mechanical/judgment split
  (`docs/superpowers/specs/2026-08-23-draft-bigboard-design.md`) is the template to reuse rather
  than re-deriving the pattern.
