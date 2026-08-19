---
date: '2026-08-19'
kind: trade
season: '2026'
week: null
status: recommended
players_involved:
  - '11563'
  - '5859'
  - '7553'
related_wiki: []
---

## Summary

`trade propose --me --all` (season 2026, value-season 2025 VORP — 2026 has no stats yet,
league is still `pre_draft`) flagged Bo Nix as an unusually strong trade chip: two
candidate packages sending him out cleared plausibility scores (93.0, 104.9) far above
everything else in the scan (next-highest outside these was 78.2; most candidates scored
negative). No offer has been sent — this is a scouting recommendation for the commissioner
to act on manually in Sleeper.

Recommended primary target: **give Bo Nix (QB), get A.J. Brown (WR) from roster_id=3**
(value delta +0.6, plausibility 93.0). Secondary/alternate: **give Bo Nix, get Kyle Pitts
(TE) from roster_id=10** (value delta +1.5, plausibility 104.9) — algorithmically more
"plausible" but fills a smaller hole for us; worth keeping in back pocket if the A.J. Brown
talks stall.

## Reasoning

Our roster (`value roster --me` equivalent, computed manually against 2025 VORP since
2026 VORP doesn't exist pre-season) is lopsided: QB +53.2 total (2 players, clear surplus
for a single-QB league), RB +64.9 (healthy), TE -36.7 (soft), **WR -130.7 (6 players,
by far our worst position)**. Bo Nix is valuable but redundant — we don't need two
plus-value QBs in a single-QB format, so shipping him for a starting-caliber piece at our
weakest spot is a clean sell-high-on-surplus move.

- **roster_id=3** is QB-starved (-71.8 total, a single rostered QB) and WR-rich (+125.5
  across 7 players) — they can afford to move a WR2/3-caliber piece like A.J. Brown for
  a real QB1 upgrade, and A.J. Brown directly fixes our single biggest positional gap
  with a genuine difference-maker, not just a depth add. This is the stronger fit for us
  even though its raw plausibility score is slightly lower than the Pitts deal.
- **roster_id=10** has the most desperate QB situation in the league (-264.0 across 3
  bad QBs) and a TE surplus (+104.8, 3 players) — Kyle Pitts addresses our TE softness,
  but that's a shallower hole than WR, so this is the fallback rather than the lead offer.
- No `wiki/league/opponents/<roster_id>.md` notes exist yet for either GM, so this is
  value/need-fit reasoning only, not adjusted for any known team-building tendencies.
- Per `.claude/skills/trades.md`: trade urgency should stay low this early (league hasn't
  even drafted for 2026 yet; trade_deadline is week 11) — but both packages cleared the
  "unusually strong" bar (need-filling on both sides, not just balanced value) that
  justifies surfacing something now rather than waiting.

## Data

- `trade propose --season 2026 --me --all --top 5` (2025 value-season) — top plausibility
  hits: roster_id=10 give Bo Nix/get Kyle Pitts delta=+1.5 plausibility=104.9;
  roster_id=3 give Bo Nix/get A.J. Brown delta=+0.6 plausibility=93.0. Full scan output
  archived in this run's session log.
- `trade evaluate --give 11563 --get 5859 --season 2026 --json` (Bo Nix -> A.J. Brown):
  `{"give_value": 46.22, "get_value": 46.80, "value_delta": 0.58, "give_position_totals":
  {"QB": 46.22}, "get_position_totals": {"WR": 46.80}}`
- `trade evaluate --give 11563 --get 7553 --season 2026 --json` (Bo Nix -> Kyle Pitts):
  `{"give_value": 46.22, "get_value": 47.70, "value_delta": 1.48, "give_position_totals":
  {"QB": 46.22}, "get_position_totals": {"TE": 47.70}}`
- Manual positional breakdown (2026 rosters x 2025 VORP): roster_id=5 (us) QB +53.2 (n=2),
  RB +64.9 (n=4), TE -36.7 (n=2), WR -130.7 (n=6); roster_id=3 WR +125.5 (n=7),
  RB +125.2 (n=5), TE -70.6 (n=2), QB -71.8 (n=1); roster_id=10 TE +104.8 (n=3),
  RB +68.5 (n=3), QB -264.0 (n=3), WR -287.0 (n=5).

## Outcome

Pending — not yet sent. Commissioner to evaluate and decide whether to open trade talks
with roster_id=3 (preferred) or roster_id=10 in Sleeper. Revisit closer to the week-11
trade deadline if this hasn't been acted on, since rosters/VORP will look different once
the season actually starts.
