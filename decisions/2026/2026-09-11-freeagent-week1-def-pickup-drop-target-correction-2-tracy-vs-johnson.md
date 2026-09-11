---
date: '2026-09-11'
kind: freeagent
season: '2026'
week: 1
status: recommended
players_involved:
  - Tyrone Tracy
  - Juwan Johnson
  - Tennessee Titans
related_wiki:
  - wiki/players/11655-tyrone-tracy.md
  - wiki/players/7002-juwan-johnson.md
related_decisions:
  - decisions/2026/2026-09-11-freeagent-week1-def-pickup-titans-drop-daniel-jones.md
  - decisions/2026/2026-09-11-freeagent-week1-def-pickup-drop-target-correction-darnold-injury.md
---

## Summary

Second correction to the same DEF-pickup thread. User asked for the Juwan Johnson drop call to be
backed by actual projected playing time/snaps/targets rather than last year's VORP-flavored
ranking. On checking, 2025 usage alone doesn't clearly separate Johnson from Tyrone Tracy (similar
ppg), but each player's **2026 depth-chart trajectory** does, and it points the other way: Tracy is
the weaker asset right now. **Revised drop target: Tyrone Tracy, not Juwan Johnson.**

## Reasoning

- **2025 usage, for context (`data/stats/weekly/2025.parquet`, `data/stats/snaps/2025.parquet`).**
  Juwan Johnson: 75% season-average snap share (68% over the final 4 weeks), 102 targets, 77
  receptions, 10.6 PPR ppg across 17 games. Tyrone Tracy: 54% season-average snap share (rising to
  68% over the final 4 weeks), 48 targets, 36 receptions, 176 carries, 10.7 PPR ppg across 15
  games. Roughly a wash on paper — this is why last time's raw-VORP framing didn't distinguish
  them well.
- **2026 depth-chart reality is not a wash.** Per `wiki/players/7002-juwan-johnson.md`: Johnson is
  "still listed as the starter on the unofficial depth chart" for New Orleans despite the Saints
  adding Noah Fant (FA) and drafting Oscar Delp in Round 3 — the risk is a *capped ceiling* below
  last year's career-high volume, not a lost role. Per `wiki/players/11655-tyrone-tracy.md`: the
  Giants signed veteran Najee Harris in addition to an already-crowded Skattebo/Singletary
  backfield ("squeezing Tracy's role"); Tracy lost preseason reps to Singletary after a missed
  pass-pro block that got the QB hit and a lost fumble in back-to-back games; he's also managing a
  neck injury with Week 1 participation uncertain as of Sept 2; reporting frames his **roster spot**
  as "in real jeopardy," not just his snap share.
- **Why this flips the call.** Johnson has a real, if capped, role (still TE1 on his own depth
  chart). Tracy is buried 3rd/4th on his, has already lost preseason reps to a mistake-driven
  demotion, and carries a live injury question — a materially worse floor than a "starter with new
  target competition." Position scarcity (RB > TE on the wire) doesn't outweigh this: a
  crowded-out, banged-up RB4 isn't a usable handcuff or streamer either.

## Data

- `data/stats/weekly/2025.parquet`, `data/stats/snaps/2025.parquet` — season and trailing-4-week
  snap%/target/ppg pulls for both players.
- `wiki/players/7002-juwan-johnson.md`, `wiki/players/11655-tyrone-tracy.md` — 2026 offseason/
  preseason depth-chart and injury news.

## Outcome

Recommended: **add Tennessee Titans (TEN) D/ST, drop Tyrone Tracy** (not Juwan Johnson, not Daniel
Jones). Not yet executed in Sleeper — this CLI has no roster-transaction command; the user needs to
make the actual add/drop in the Sleeper app.
