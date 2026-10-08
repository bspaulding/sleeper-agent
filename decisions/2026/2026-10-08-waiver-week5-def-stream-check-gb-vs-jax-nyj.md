---
date: '2026-10-08'
kind: waiver
season: '2026'
week: 5
status: proposed
players_involved: ['GB', 'JAX', 'NYJ']
related_wiki: []
related_decisions:
  - decisions/2026/2026-09-24-waiver-week3-def-stream-check-hold-ne.md
  - decisions/2026/2026-08-28-bigboard-def-vorp-research-streaming-recommended.md
---

## Summary

Week 5 DEF check before Thursday night (TB @ DAL; no roster players involved). Currently rostered
DEF is Green Bay. Recommendation: stream, not hold.

## Reasoning

Opponent implied points (from `data/stats/schedules/2026.parquet` spread/total; opponent offense
quality is what predicts DEF output, r≈0.32):

- GB: home vs CHI, GB 3-pt underdog, total 45.5 -> CHI implied ~24.3 (worst of the group).
- JAX: home vs PHI, JAX 6.5-pt favorite, total 42.5 -> PHI implied ~18.0.
- NYJ: home vs CLE, NYJ 2.5-pt favorite, total 39.5 -> CLE implied ~18.5.
- LAC: home vs DEN, 3.5-pt favorite, total 42.5 -> DEN implied ~19.5.

JAX and NYJ are unrostered league-wide as of the 2026-10-08 sync. JAX was dropped by another
roster this week, so it may still be in the waiver window (claim, not instant add); NYJ is the
fallback. Drop GB for the add.

## Outcome

Proposed; awaiting manager decision and execution in Sleeper.
