---
date: '2026-09-16'
kind: waiver
season: '2026'
week: 2
status: executed
players_involved:
  - Bryce Young
  - Daniel Jones
related_wiki:
  - wiki/players/9228-bryce-young.md
related_decisions:
  - decisions/2026/2026-09-11-freeagent-week1-def-pickup-drop-target-correction-darnold-injury.md
  - decisions/2026/2026-09-15-waiver-week2-def-stream-titans-to-bucs.md
---

## Summary

User asked "are we sure about Jones — is there anybody better out there?" after the Week 2 DEF
stream. Re-checking surfaced a real bug in the prior session's process: `freeagent recommend --me
--season 2026` had been run **without** `--value-season 2026`, so it silently used stale valuation
data (e.g. reported Jacoby Brissett at vorp=-46.5, "+2.0 over Daniel Jones" — both numbers wrong).
Re-run with `--value-season 2026` pinned, the same command surfaces **Bryce Young** as a clear
free-agent upgrade at QB. User submitted a waiver claim: **add Bryce Young, drop Daniel Jones,
$5 bid.**

## Reasoning

- **The bug.** `value rank --season 2026 --position QB` (current, correct 2026 Week-1 VORP) shows
  Daniel Jones at vorp=-9.2 and several unrostered QBs clearly ahead of him — Bryce Young
  (13.2), Carson Wentz (0.0), C.J. Stroud (-0.8) — none of which the previous `freeagent recommend`
  run surfaced, because it wasn't pinned to the current season's value data.
- **Bryce Young is the standout, not just "better than Jones."** Week 1: 31.44 fantasy points,
  vorp=13.2 — ahead of Lamar Jackson, Jalen Hurts, Mahomes, and Purdy's Week 1 lines. Backed by more
  than one game: per `wiki/players/9228-bryce-young.md`, he had a career year in 2025 (3,011 yds,
  63.6% comp, 23 TD, career-low sacks) and is the unquestioned 2026 Panthers starter with no
  camp/injury concern — a real quality signal, not pure one-week noise, though still only one 2026
  data point.
- **Daniel Jones is the weaker asset to hold.** Coming off an Achilles tear, struggled in his
  actual return (19/31, 166 yds, 1 TD, 1 INT, 41-23 loss to Baltimore per
  `wiki/players/5870-daniel-jones.md`), vorp=-9.2. He does not appear on `draft keepers --me`'s
  ELIGIBLE list, so dropping him costs no keeper value.
- **Sam Darnold is unaffected** — still held per the 2026-09-15/16 hold decision (cheap R14 keeper
  cost, short-ish recovery timeline, no IR slot to make holding "free" either way, so the calculus
  doesn't change). Young becomes the active bridge starter in Jones's place, not a third QB kept
  alongside both.
- **Bid sizing.** `waiver recommend --me --season 2026 --value-season 2026` suggested $2-$7 for
  Young; $5 (mid-range) is reasonable given this is a real starting-QB-caliber add, not speculative
  depth, per `.claude/skills/waivers.md`'s guidance to lean toward the high end of the range for a
  target that fills a genuine roster need rather than pure depth.

## Data

- `value rank --season 2026 --position QB --top 40`, `value roster --me --season 2026`.
- `freeagent recommend --me --season 2026 --value-season 2026 --top 20` (corrected run).
- `waiver recommend --me --season 2026 --value-season 2026 --budget-remaining 100
  --weeks-remaining 16 --top 10`.
- `data/stats/weekly/2026.parquet` (Bryce Young Week 1: 31.44 fantasy points).
- `wiki/players/9228-bryce-young.md`, `wiki/players/5870-daniel-jones.md`.
- `draft keepers --me --season 2026` (confirms Jones not keeper-eligible).

## Outcome

Executed by Brad: waiver claim submitted, **add Bryce Young ($5 FAAB), drop Daniel Jones.**
Process note for future sweeps: always pin `--value-season <current season>` on `freeagent
recommend` and `waiver recommend` once in-season VORP is live — the default silently falls back to
stale data instead of erroring, which is how this got missed initially.
