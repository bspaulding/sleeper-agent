---
date: '2026-09-11'
kind: freeagent
season: '2026'
week: 1
status: recommended
players_involved:
  - Tennessee Titans
  - Daniel Jones
related_wiki: []
---

## Summary

We never picked up a DEF before the season started (roster_id=5 carries no DEF, and the league
starts one). Add Tennessee Titans D/ST, drop Daniel Jones (backup QB) to make room. This is a
free-agent pickup (no FAAB competition expected), not a Tuesday waiver claim.

## Reasoning

- **Why we need a move at all.** `sleeper roster show --me --season 2026` shows 15/15 roster spots
  filled (2 QB, 5 RB, 5 WR, 3 TE) with zero DEF, against a league that starts 1 DEF
  (`roster_positions` includes `DEF`, no bench overflow — 9 starters + 6 bench = 15 total). Adding
  a DEF requires dropping someone.
- **Why DEF isn't VORP-ranked here.** Per
  `decisions/2026/2026-08-28-bigboard-def-vorp-research-streaming-recommended.md`, this codebase
  deliberately excludes DEF from ordinal/VORP ranking — a defense's own quality barely predicts its
  next game (r≈0.09) while the upcoming opponent's offensive weakness predicts it far better
  (r≈0.32). 2026 `stats sync`/`stats vorp` also aren't runnable in this environment (nflverse
  fetch blocked), so this pick is matchup-research-driven rather than tool-computed, per that
  decision's own recommended path (a future weekly-matchup streamer, not attempted here).
- **Free-agent DEF pool for our league.** Cross-referenced `data/sleeper/players.parquet`
  (`position == "DEF"`) against `data/sleeper/rosters/2026.parquet` (all 12 rosters) after
  re-syncing league data (`sleeper league sync --season 2026`). Already-rostered, so off the board:
  HOU, BAL, PIT, SEA, LV, LAC, JAX, LAR, DET, PHI, DEN, KC — notably every "Tier 1" Week 1
  defense per external rankings (Jaguars, Chargers, Steelers, Rams, Eagles, Broncos) is already
  taken in this league.
- **Matchup research (web search, since 2026 schedule/stats aren't synced locally).** Among
  available free agents, the strongest Week 1 matchup is Tennessee Titans vs. NY Jets: Jets QB Geno
  Smith was sacked more than any QB in the league last season (55) and led all QBs in
  interceptions (17) in 2025, per NBC Sports' "Getting Defensive" Week 1 rankings, which lists
  Titans-Jets as a Tier 2 streaming play. Other available candidates were weaker: Green Bay (at
  Minnesota) lost Rashan Gary and has Micah Parsons on PUP; Chicago (at Carolina) is a decent but
  unspectacular matchup; Minnesota itself is a stronger unit but faces a Packers offense that's
  scored 23+ points in 3 of the last 4 meetings. Titans' own unit is mediocre, but per the r≈0.32
  matchup-over-quality finding above, the Jets' historically bad pass protection/turnovers make
  this the best bet in our actual pool.
- **Who to drop.** `freeagent recommend --me --season 2026` flags Daniel Jones as our weakest
  roster player (vorp=-48.5, worse than free-agent Jacoby Brissett at -46.5). We're carrying 2 QBs
  (Darnold, Jones) in a 1-QB-start league; Darnold is the clearly better of the two (vorp=-30.5 per
  `draft keepers --me`) and Jones doesn't appear on our keeper-eligible list, so there's no
  keeper-value cost to cutting him (per `.claude/skills/free-agents.md`'s keeper-drop guidance).
  Backup QB is the lowest-cost bench spot to give up for a DEF add.

## Data

- `sleeper league sync --league-id 1389376972722835456 --season 2026` (re-synced stale roster
  cache before checking).
- `sleeper roster show --me --season 2026`, `freeagent recommend --me --season 2026`,
  `draft keepers --me --season 2026`.
- `data/sleeper/players.parquet` / `data/sleeper/rosters/2026.parquet` cross-reference for
  free-agent DEF pool.
- Web search: NBC Sports "Getting Defensive: Week 1 fantasy plays led by Jaguars, Chargers; top
  streaming defenses" (Tier 2: Titans vs. Jets), Sharp Football Analysis Packers-Vikings Week 1
  worksheet (Packers defensive losses, Vikings D strength).

## Outcome

Recommended: **add Tennessee Titans (TEN) D/ST, drop Daniel Jones.** Not yet executed in Sleeper —
this CLI is decision-support only and has no roster-transaction command; the user needs to make
the actual add/drop in the Sleeper app.
