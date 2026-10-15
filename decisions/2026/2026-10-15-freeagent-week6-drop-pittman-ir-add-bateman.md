---
date: '2026-10-15'
kind: freeagent
season: '2026'
week: 6
status: executed
players_involved: ['6819', '7571']
related_wiki:
  - wiki/players/6819-michael-pittman.md
  - wiki/players/7571-rashod-bateman.md
---

## Summary

Dropped Michael Pittman (WR, PIT, on IR) and added Rashod Bateman (WR, BAL) as a plain
free-agent add, no FAAB. Executed by the user in Sleeper on 2026-10-15, before the Week 6
Thursday game; confirmed via `sleeper league sync` (roster 5 now holds Bateman, not Pittman).

## Reasoning

This league plays best ball, so there are no start/sit decisions — only roster moves matter.
Pittman was placed on IR before Week 5 (aggravated plantar fasciitis) and must miss at least four
games, so Week 10 (Nov 15) is the earliest return; he was also at 5.3 PPG. The roster has no IR
slot (15 spots, all full), so he was a dead bench spot.

Replacement choice weighed boom potential over average, since best ball rewards spike weeks:
Bateman (targets/PPR pts by week: 1/0.0, 9/21.8, 3/5.7, 2/6.6, 6/11.2) is one of Baltimore's top
pass-catchers with Flowers hampered and Andrews briefly out earlier. Kalif Raymond, the tool's
top VORP name (+3.0), was rejected because his targets faded to 2 and 4 the last two weeks.
Keon Coleman (BUF) was the runner-up. Bateman was dropped in Week 5, past the 2-day
`waiver_clear_days` window, so no claim or bid was needed.

Darnold checked and kept (user call, 2026-10-15): best ball means bench spots are depth, not dead
weight. His 13.7 PPG includes a Week 1 early exit; in three full games he averaged about 16.4.
Best unrostered QBs (Brissett ARI 17.9, Watson CLE 16.6, Geno Smith 14.3) are only marginally
better, and bye weeks don't favor a swap (Young's CAR bye was Week 5; Darnold's is Week 11,
Brissett's Week 14). Revisit the QB pool only if Young is hurt.

## Data

- `freeagent recommend --me --season 2026`: Raymond +36.5, Brissett +34.5, Coleman +33.5,
  Bateman +29.4 over Pittman (VORP delta; tool is blind to the IR timeline and to boom weeks).
- FAAB remaining: $75 (unchanged).

## Outcome

Executed 2026-10-15. Revisit if Bateman's role fades or if a better WR hits the wire.
