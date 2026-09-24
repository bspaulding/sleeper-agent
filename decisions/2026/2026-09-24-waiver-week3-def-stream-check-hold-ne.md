---
date: '2026-09-24'
kind: waiver
season: '2026'
week: 3
status: executed
players_involved: ['NE', 'GB', 'DET']
related_wiki: []
related_decisions:
  - decisions/2026/2026-09-23-waiver-week3-weekly-review-hold-no-moves.md
  - decisions/2026/2026-09-15-waiver-week2-def-stream-titans-to-bucs.md
  - decisions/2026/2026-08-28-bigboard-def-vorp-research-streaming-recommended.md
---

## Summary

Follow-up to the 2026-09-23 Week 3 weekly review, which covered the four weak-VORP skill spots
but omitted the DEF slot entirely — a gap, since [decisions/2026/2026-08-28-bigboard-def-vorp-research-streaming-recommended.md](2026-08-28-bigboard-def-vorp-research-streaming-recommended.md)
established DEF as a weekly-streaming slot (opponent offensive weakness predicts next-game DEF
output, r≈0.32, far better than a defense's own season-long quality, r≈0.09), not a hold. Ran the
matchup check that should have been part of the Week 3 review. **Decision: hold New England**,
explicit call by the manager after seeing the alternative.

## Reasoning

- Currently rostered DEF is New England Patriots (added Week 2 via free agent — note the
  2026-09-15 decision doc's plan was "stream Titans to Tampa Bay," but the actual executed
  transaction added NE instead; TB's Week 1 waiver claim had failed).
- **NE's Week 3 matchup**: road at Jacksonville, NE a ~3-point underdog (home_moneyline JAX -155,
  away_moneyline NE +130 per `data/stats/schedules/2026.parquet`), total_line 45.5 — mediocre, not
  a disaster but not a plus matchup either.
- **Better options were available on waivers** (checked against all-roster player_ids in
  `data/sleeper/rosters/2026.parquet` — both unrostered league-wide):
  - Green Bay: home vs. Atlanta, -250 favorite, total_line 42.5 (best combo of low total + solid
    favorite margin on the Week 3 board).
  - Detroit: home vs. NY Jets, -305 favorite, total_line 47.5.
- Presented both options to the manager; explicit decision was to stick with New England rather
  than stream. No FAAB spent, no roster move made.

## Data

- `data/stats/schedules/2026.parquet` Week 3 slate, sorted by moneyline: JAX (home, -155) vs. NE
  (away, +130), total 45.5. Best-matchup alternatives: GB (home, -250) vs. ATL, total 42.5; DET
  (home, -305) vs. NYJ, total 47.5.
- `data/sleeper/rosters/2026.parquet`: GB and DET confirmed unrostered across the league as of this
  check.

## Outcome

Held. No transaction made — manager's explicit call to stick with New England for Week 3.
