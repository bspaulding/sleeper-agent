---
date: '2026-09-11'
kind: freeagent
season: '2026'
week: 1
status: recommended
players_involved:
  - Sam Darnold
  - Daniel Jones
  - Juwan Johnson
  - Tennessee Titans
related_wiki: []
related_decisions:
  - decisions/2026/2026-09-11-freeagent-week1-def-pickup-titans-drop-daniel-jones.md
---

## Summary

Correction to the same-day decision
[[2026-09-11-freeagent-week1-def-pickup-titans-drop-daniel-jones]], which recommended dropping
Daniel Jones to open the DEF roster spot. That was wrong: Sam Darnold, our QB1, left Week 1's
season opener hurt. **Revised drop target: Juwan Johnson (TE3), not Daniel Jones.** The Titans
DEF pickup itself is unchanged.

## Reasoning

- **What changed.** The prior decision assumed Darnold/Jones were an ordinary starter/backup pair
  and cut the weaker-VORP one (Jones). The user flagged that Darnold "already played and had a
  terrible game, he got hurt and went out early" before that decision was acted on.
- **Verified against live data, not just player-dictionary cache.** Pulled the actual Week 1
  matchup via Sleeper's `/v1/league/<id>/matchups/1` (using `sleeper_client.http.get_json`
  directly — no CLI command exposes matchup data yet): roster_id 5 started Darnold at QB, and he
  scored 0.52 points while every other starter still shows 0.0 (their games hadn't kicked off yet
  as of this check) — consistent with an early injury exit, not just a bad game. Re-ran
  `sleeper players sync` (live Sleeper player dictionary, not the nflverse feed that's blocked in
  this environment) and confirmed `injury_status`: **Sam Darnold = Out**, **Daniel Jones = null
  (healthy)**.
- **Why this flips the drop target.** With Darnold out, Daniel Jones is our only startable QB, not
  a cuttable low-value backup — dropping him for a DEF would leave the QB slot needing an
  emergency streamer too, trading one roster problem for a worse one.
- **New drop target: Juwan Johnson.** Next-weakest bench spot that isn't now load-bearing: he's
  TE3 behind Kyle Pitts and Trey McBride, both clearly ahead of him on the depth chart, both
  healthy (`injury_status = null`). He does show up on `draft keepers --me`'s eligible list (R11
  cost, vorp=-20.9) — a real but mediocre value-per-cost keeper, not the "clear, large future
  value" `.claude/skills/free-agents.md` says is worth protecting over an active lineup need.

## Data

- `sleeper_agent.sleeper_client.http.get_json` against
  `https://api.sleeper.app/v1/league/1389376972722835456/matchups/1` (ad hoc — no `matchups`
  command exists in `sleeper_agent.commands` yet; worth adding if this comes up again).
- `sleeper players sync` (live Sleeper player dictionary) → `data/sleeper/players.parquet`
  `injury_status` column, checked for Darnold, Jones, Johnson, Pitts, McBride, Tracy.
- `draft keepers --me --season 2026` (Johnson's R11/-20.9 keeper line).

## Outcome

Recommended: **add Tennessee Titans (TEN) D/ST, drop Juwan Johnson** (not Daniel Jones). Not yet
executed in Sleeper — this CLI has no roster-transaction command; the user needs to make the
actual add/drop in the Sleeper app.
