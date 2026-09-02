---
date: '2026-09-02'
kind: trade
season: '2026'
week: null
status: recommended
players_involved:
  - '6819'
  - '11563'
  - '2449'
  - '11560'
related_wiki: []
---

## Summary

Weekly `trade propose --season 2026 --me --all --top 20` scan (2025 VORP as value-season, since
2026 has no stats yet) against all 11 other rosters. Nothing this week clears the "unusually
strong" bar the way the pre-draft Aug 19 mock scan did (93.0/104.9 plausibility, far above a 78.2
runner-up) — the top hit here is 59.6, with a smoother gradient below it (54.3, 41.6, 35.9, 31.9).
Still, one package stands out as a genuine mutual-need fit rather than just balanced math, so it's
worth logging as a scouting note even at low urgency (season hasn't started, `trade_deadline` is
week 11 — see `.claude/skills/trades.md`). No offer sent; this is a recommendation for the
commissioner to act on manually in Sleeper if desired.

**Primary: give Michael Pittman (WR) to roster_id=4, get Bo Nix (QB)** — value delta +1.7,
plausibility 59.6, the top result of the whole scan.

**Alternate (touches a keeper, lower priority): give Stefon Diggs (WR) to roster_id=7, get Caleb
Williams (QB)** — value delta +2.6, plausibility 54.3.

## Reasoning

Our roster is unusually lopsided: RB +308.0 (n=5), WR +267.6 (n=5), TE +266.7 (n=3) are all
strongly above replacement, but **QB is -79.0 across 2 players (Sam Darnold, Daniel Jones)** — by
far our worst position and the only one below replacement at all. That's a real, persistent
construction gap (not a stats-noise artifact), so a same-value-or-better QB upgrade is worth
pursuing even at low season-opening urgency.

- **roster_id=4** is the cleanest fit: their WR is their weakest slot (-65.4 across 3 players)
  while their QB (Bo Nix) is roughly replacement-level for them (-5.4 across 2, so they're not
  QB-needy) — they can plausibly let Nix go for a real WR upgrade. Pittman is fully redundant on
  our side (we're 5-deep and +267.6 at WR) and directly fixes our QB hole without touching either
  of our 2026 keepers (Stefon Diggs R7, Quinshon Judkins R8 — see `wiki/league/season-2026.md`).
  This is the lead recommendation for exactly that reason: same problem solved, smaller price paid.
- **roster_id=7** is a second real fit — their QB (-27.9 avg across 2) is also a soft spot and
  their WR corps is deep (-17.4 avg across 5, i.e. below-average per player despite the count), so
  Caleb Williams for a WR is plausible for them too, and the delta is slightly better for us
  (+2.6 vs +1.7). But the WR going out is **Stefon Diggs, one of our two locked-in 2026 keepers**
  — trading a keeper is a bigger commitment than trading a bench-depth WR, and per league rules
  keeper status doesn't transfer in trades, so we'd be giving up next year's keeper slot too, not
  just this year's roster spot. Keeping this as a fallback only, not the lead offer, unless Pittman
  talks with roster_id=4 stall.
- No `wiki/league/opponents/<roster_id>.md` notes exist yet for either GM (same gap noted in the
  Aug 19 pre-draft scouting entry), so this is value/need-fit reasoning only, not adjusted for any
  known team-building tendencies.
- Per `.claude/skills/trades.md`: trade urgency should stay low this early (pre-Week-1, deadline is
  week 11) — logging this now as a watch item, not urging the commissioner to act immediately.

## Data

- `trade propose --season 2026 --me --all --top 20` (2025 value-season) full scan run against all
  11 other rosters — top plausibility hits across the whole league: roster_id=4 give Michael
  Pittman/get Bo Nix delta=+1.7 plausibility=59.6; roster_id=7 give Stefon Diggs/get Caleb Williams
  delta=+2.6 plausibility=54.3; roster_id=10 give D'Andre Swift/get Josh Allen delta=-3.2
  plausibility=41.6; roster_id=8 give Kyle Pitts/get Trevor Lawrence delta=+3.8 plausibility=35.9;
  roster_id=11 give Keenan Allen/get Patrick Mahomes delta=+0.2 plausibility=31.9. Everything else
  in the scan was plausibility-negative.
- `trade evaluate --give 6819 --get 11563 --season 2026 --json` (Pittman -> Bo Nix): `{"give_value":
  30.22, "get_value": 31.92, "value_delta": 1.70, "give_position_totals": {"WR": 30.22},
  "get_position_totals": {"QB": 31.92}}`
- `trade evaluate --give 2449 --get 11560 --season 2026 --json` (Diggs -> Caleb Williams):
  `{"give_value": 38.12, "get_value": 40.76, "value_delta": 2.64, "give_position_totals": {"WR":
  38.12}, "get_position_totals": {"QB": 40.76}}`
- Manual positional breakdown (2026 rosters x 2025 VORP, since `data/vorp/2026.parquet` doesn't
  exist pre-season): roster_id=5 (us) RB +308.0 (n=5), WR +267.6 (n=5), TE +266.7 (n=3), QB -79.0
  (n=2); roster_id=4 RB +86.4 (n=6), TE +54.1 (n=3), QB -5.4 (n=2), WR -65.4 (n=3); roster_id=7
  RB +342.0 (n=5), TE +37.8 (n=2), QB -55.8 (n=2), WR -87.1 (n=5).

## Outcome

Pending — not yet sent. Commissioner to evaluate and decide whether to open trade talks with
roster_id=4 (preferred, doesn't touch a keeper) in Sleeper. Revisit as the week-11 trade deadline
approaches, or sooner if roster_id=4's construction changes (e.g. they add a QB via waivers,
closing this window).
