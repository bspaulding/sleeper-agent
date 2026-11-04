---
date: '2026-11-04'
kind: waiver
season: '2026'
week: 9
status: executed
players_involved: ['TB', 'GB', 'NO', 'DET', 'DAL', "D'Andre Swift", 'Josh Allen']
related_wiki: []
related_decisions:
  - decisions/2026/2026-11-04-trade-swift-for-josh-allen.md
  - decisions/2026/2026-10-28-freeagent-week8-def-swap-nyj-for-tb.md
---

## Summary

Week 9 (Nov 5-9) weekly check. **Decision: no roster moves of any kind.** Hold Tampa Bay at DEF,
no waiver/free-agent claims, no FAAB spent ($75 remaining), and no trade offer sent. Explicit call
by the manager.

## Reasoning

- **DEF: hold TB (at CHI).** TB averages 8.9 pts/game with 2026 season VORP 26 (third among all
  defenses). `freeagent recommend --me --season 2026` surfaced no DEF upgrade.
- TB's matchup is mid-pack (9th of 30 on a rough opponent score built from opponent turnovers,
  sacks allowed, yards and TDs per game, plus own sack/INT rates). CHI's offense is high-volume
  (405 yds/g, 3.1 TD/g) but gives the ball away 1.5 times per game.
- Better-matchup free-agent defenses all had weaker baselines: NO (vs CLE, 2nd), DET (@MIA, 3rd),
  GB (@NE, 5th, 7.0 pts/g), DAL (@IND, 6th). GB was the best mix of baseline and matchup but only a
  marginal edge over TB. All four were already past `waiver_clear_days`, so each would have been a
  free instant add. RotoBaller's Week 9 article favored CHI, DAL, DET, NO and NYG as streams; the
  article text was truncated, so its view on TB is unknown.
- **Trade:** the Swift-for-Allen scouting candidate was passed on. The other side (roster 10, 5-2)
  has little need for Swift and is unlikely to accept, and QB is not costing wins right now, so a
  QB trade is not worth the trade capital before the Week 11 deadline.
- **Limits:** the matchup score is a home-built heuristic, there is no 2026 betting-line data for
  Week 9, and news searches returned no verifiable 2026 injury information (including Caleb
  Williams' status). Re-check Wednesday-Friday injury reports if circumstances change.

## Data

- `data/stats/schedules/2026.parquet` Week 9 slate (TB at CHI); `data/stats/team/2026.parquet`
  for opponent offense and own defensive rates; `data/vorp/2026.parquet` for DEF season VORP/ppg.
- `data/sleeper/rosters/2026.parquet`: GB, NO, DET, DAL, CHI, NE, etc. unrostered league-wide.
- Last transactions for candidates: DET wk 2, CHI wk 5, GB wk 5, DAL wk 5 (waiver) — all cleared.

## Outcome

Held. No transaction made — manager's explicit call for Week 9. Revisit DEF weekly.
