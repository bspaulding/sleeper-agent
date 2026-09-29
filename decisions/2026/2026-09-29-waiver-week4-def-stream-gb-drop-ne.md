---
date: '2026-09-29'
kind: waiver
season: '2026'
week: 4
status: recommended
players_involved: ['GB', 'NE', 'PIT']
related_wiki: ['wiki/team/defense-strategy.md']
related_decisions:
  - decisions/2026/2026-09-24-waiver-week3-def-stream-check-hold-ne.md
  - decisions/2026/2026-08-28-bigboard-def-vorp-research-streaming-recommended.md
---

## Summary

Week 4 DEF stream: claim Green Bay at $0 FAAB, dropping New England. Manager placed the claim in
Sleeper on 2026-09-29 (pending Tuesday waiver processing). Status stays `recommended` until the
claim is confirmed processed.

## Reasoning

- NE is at Buffalo as a 7-point underdog (BUF -298, total 48.5); BUF implied ~27.8 points — the
  worst DEF matchup on the Week 4 board. The Week 3 hold (3-pt underdog) doesn't carry over.
- Streaming rule (opponent offensive weakness predicts DEF output, r≈0.32 vs r≈0.09 for a
  defense's own quality): GB @ TB, GB -198, total 39.5, TB implied ~17.5 — lowest total among
  unrostered options with the biggest favorite margin.
- Alternate PIT @ CLE (-148, total 38.5, CLE implied ~18) was unavailable per the manager.
- CHI (home vs NYJ, total 43.5) and DET (@ CAR, total 50.5) ranked lower.
- Caveat: no news sweep on GB/TB done for this pick; wiki notes GB is missing Micah Parsons.
- $0 bid: early-season pacing (weeks 1-4 low end) and low competition for a streaming DEF.

## Data

- `data/stats/schedules/2026.parquet` Week 4 slate; `data/sleeper/rosters/2026.parquet` for
  rostered status (GB, PIT, CHI, DET unrostered at check time; MIN/SEA/BAL/HOU/DEN rostered).

## Outcome

Claim submitted by manager: add GB, drop NE, $0 FAAB. Pending processing — update status to
`executed` (or note failure) once confirmed.
