---
date: '2026-11-23'
kind: waiver
season: '2026'
week: 12
status: recommended
players_involved: ['5995', '8126']
related_wiki:
  - wiki/players/5995-justice-hill.md
  - wiki/players/8126-wan-dale-robinson.md
related_decisions: []
---

## Summary

Recommend a FAAB claim on Justice Hill (RB, BAL), bid **$6-$9** (target $7), funded by dropping
Wan'Dale Robinson — confirmed out for the rest of 2026 (season-ending ankle injury, IR since
2026-11-18). This isn't a marginal-upgrade speculative add; it's replacing a roster spot that is
now producing zero value for the rest of the season with the one target on this week's waiver
list that has real positive VORP and an actual role.

## Reasoning

- **Robinson's roster spot is dead weight, not just injured depth.** This league has no IR slot
  (`roster_positions`: `QB,RB,RB,WR,WR,TE,FLEX,FLEX,DEF,BN×6`, confirmed via
  `data/sleeper/league/2026.parquet`) — an IR player occupies a normal bench spot. Robinson's own
  wiki page confirms HC Robert Saleh said the day after the injury (2026-11-19) that he's out for
  the rest of the season, not just the 4-game IR minimum. There is no scenario this season where
  keeping him on the roster produces points; this is a pure opportunity-cost drop, independent of
  whether Hill specifically is the best replacement.
- **`waiver recommend --season 2026 --roster-id 5` ranked Justice Hill #1 by a wide margin** —
  the only target in the top 10 with positive VORP (6.3; everything else on the list is -8.8 or
  worse: Mark Andrews, Washington DEF, Mason Taylor, Treylon Burks, Gunnar Helm, Pat Bryant, Roman
  Wilson, Konata Mumpfield, Dawson Knox). None of those are real upgrades over anything on our
  bench; Hill is the only name this week that clears the "clear, high-value pickup" bar at all.
- **Role is real, not just a trending-count news-cycle spike**: 18.6 PPR points Week 11 vs.
  Carolina (6 car/69 yds/1 TD, 4 rec/27 yds), and he's caught 3+ passes in 6 straight games —
  consistent pass-game role behind Derrick Henry, not a one-week box-score fluke. Henry himself
  was briefly eval'd for a concussion in that game but cleared, so there's no workload-share shift
  coming from Henry's side — Hill's value is as complementary passing-down/early-down-rotation
  back, not a lead-back handcuff play. See `wiki/players/5995-justice-hill.md`.
- **Caveat weighed, not ignored**: Baltimore has a Week 13 bye immediately after this week, so
  Hill gives us exactly one week of availability before a bye — not a season-long stash case by
  itself. That's reflected in the bid (middle of the tool's suggested range, not the top), not in
  skipping the move — the Robinson spot is empty value either way, so even one good week from Hill
  is strictly better than zero from Robinson, and he remains on the roster for whatever he's worth
  after the bye too.
- **No keeper-cost conflict**: Robinson was a mid-season (Week 10) waiver/free-agent add this
  year, not a holdover from a prior-season draft/keeper slot — `draft keepers --me --season 2026`
  doesn't list him at all, so dropping him costs nothing against next year's keeper pool
  (`.claude/skills/free-agents.md`'s keeper-drop caution doesn't apply here).
- **Bid sizing**: $75 FAAB remaining, roughly 6 weeks left through the fantasy playoffs (week ~12
  of 17) — mid-season, so the tool's suggested range is a reasonable starting point rather than
  the early-season low-end default. Only ~21% rostered on Yahoo as of 2026-11-22, so competition
  risk is moderate, not high; picked $7 (middle of the $4-$12 suggested range) rather than the top,
  given the Week 13 bye limits the immediate payoff.

## Data

- `waiver recommend --season 2026 --roster-id 5`: Justice Hill RB, trending=346,527, vorp=6.3,
  suggested bid $4-$12 (top of list; next-best is Mark Andrews at vorp=-8.8).
- `value roster --me --season 2026`: RB n=4 total_vorp=255.6 avg=63.9 — RB isn't thin, this move
  isn't about positional need, it's about not carrying a dead roster slot.
- `sleeper roster show --me --season 2026`: current 15-man roster includes Wan'Dale Robinson.
- `data/sleeper/transactions/2026.parquet`: Justice Hill has no add/drop transaction this season
  (never rostered league-wide before now) — still subject to the waiver claim process, not a free
  instant add, consistent with `.claude/skills/free-agents.md`'s clearance-check guidance.
- Sources: [Bleacher Report](https://bleacherreport.com/articles/25536628-week-12-waiver-wire-breakout-fantasy-football-pickups-sundays-box-scores),
  [RotoBaller](https://www.rotoballer.com/waiver-wire-rankings-fantasy-football-week-12-2026/2001432),
  [DK Network](https://dknetwork.draftkings.com/2026/11/22/best-fantasy-football-waiver-wire-pickups-for-week-12-2/),
  [BVM Sports](https://bvmsports.com/2026/11/22/reaction-to-ravens-loss-to-panthers/),
  [WSMV (Robinson season-ending IR)](https://www.wsmv.com/2026/11/18/titans-receiver-wandale-robinson-out-season/).

## Outcome

Pending — this routine has no Sleeper write access. Recorded here for the commissioner to execute
manually in Sleeper before the Tuesday waiver cycle closes.
