---
date: '2026-09-23'
kind: waiver
season: '2026'
week: 3
status: recommended
players_involved: ['4943', '6819', '7553', '1479', '9228']
related_wiki:
  - wiki/players/4943-sam-darnold.md
  - wiki/players/6819-michael-pittman.md
  - wiki/players/7553-kyle-pitts.md
  - wiki/players/1479-keenan-allen.md
---

## Summary

Weekly review ahead of Week 3 waiver processing (Tue 9/29): hold the roster, no claims or
drops this week. Team is 1-1 but 334.22 total points, 3rd-highest in the 12-team league (behind
7-0-and-351.34, 2-0-and-321.58) — the Week 1 loss was a 0.72-point margin to the eventual co-leader,
and Week 2 (186.98) was the single highest score in the league that week. Record undersells the
team; no structural fix needed.

## Reasoning

Ran `freeagent recommend --me` and `waiver recommend --me`, which flagged Sam Darnold (QB,
vorp -35.0) as by far the roster's weakest link, with several street-FA QBs "upgrading" over him.
Rejected that at face value: Darnold's negative VORP is entirely an artifact of missing Weeks 1-2
with a glute injury (0 fantasy pts each week), not declining play. Fresh news
(`wiki/players/4943-sam-darnold.md`) has Seahawks HC Macdonald saying there's "a chance" he plays
Week 3 vs. Washington, decision by Friday, Week 4 more likely per Rapoport. Bryce Young (already
rostered via the 2026-09-16 waiver pickup, vorp +21.0) covers the gap in the meantime — dropping
Darnold now for a Kirk Cousins/Deshaun Watson-tier scrub would trade a returning above-replacement
starter for waiver dreck, purely because the tool's season-to-date VORP can't see an injury
absence for what it is. Same logic as the free-agents.md "check news before trusting stale VORP"
rule, just on the hold side instead of the pickup side.

Checked the other three flagged trouble spots and found the same pattern — real short-term
concern, but not a "make a move now" signal:

- **Michael Pittman** (WR, vorp -11.1, out Wk2 with a foot injury): Week 3 status still
  legitimately uncertain per HC McCarthy, but best-ball scoring means a scratch just contributes
  zero rather than costing a lineup slot — no urgency to churn the bench spot on a corresponding
  injury-return timeline.
- **Kyle Pitts** (TE, vorp -17.3, quiet Weeks 1-2): the actual cause was backup QB Cooper Rush
  playing in Penix's absence, not a Pitts role problem. Penix is back starting Week 3 (Thu night
  at GB) — reporting expects Pitts' target share to recover with him. Holding, not selling low
  into his own catalyst for improvement.
- **Keenan Allen** (WR, vorp -9.2): formally charged 9/15 with 2 DWI-related misdemeanors; CBA
  precedent suggests a possible 3-game suspension for a first offense, but nothing's been handed
  down and his attorney conference isn't until Oct 26. Noting it as a risk to monitor, not acting
  on unconfirmed discipline.

Considered `waiver recommend`'s top non-QB target, Tre Tucker (WR, LV, vorp 7.7, suggested bid
$4-$13, $95 FAAB remaining) as a speculative bench add. Passed: our WR corps is already elite
(JSN #1 overall by VORP, Diggs top-10, Boston top-12), Tucker's Week 2 breakout came with Brock
Bowers out and is expected to shrink once Bowers returns, and a national waiver-wire piece this
week frames Tucker as directly comparable to Denzel Boston — a player we already roster. No clear
edge over standing pat.

## Data

- `sleeper league sync` / `stats sync --season 2026` refreshed before this review.
- Matchup scores pulled directly from `GET /league/<id>/matchups/{1,2}` (no local CLI command for
  this yet): Week 1 roster 5 147.24 vs roster 10 147.96 (L by 0.72); Week 2 roster 5 186.98 vs
  roster 6 150.78 (W) — 186.98 was the league's top score in Week 2.
- Season standings (`GET /league/<id>/rosters`): roster 5 is 1-1-0, 334.22 fpts, 3rd of 12 by total
  points.
- `value roster --me`: QB total_vorp -13.9 (Darnold-driven, expected to normalize on his return),
  WR +60.3, RB +43.3, TE +10.7, DEF +8.0 — no other position is a problem.
- FAAB spent to date: $5 (Bryce Young waiver claim, Wk2) of $100; $95 remaining.

## Outcome

Holding. Re-run this review after Friday's Darnold game-status call and after Week 3 games, ahead
of the Tue 9/29 waiver deadline.
