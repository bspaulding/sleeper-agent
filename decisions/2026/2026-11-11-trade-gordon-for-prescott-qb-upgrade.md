---
date: '2026-11-11'
kind: trade
season: '2026'
week: null
status: recommended
players_involved:
  - Ollie Gordon II
  - Dak Prescott
related_wiki:
  - wiki/players/12495-ollie-gordon.md
  - wiki/players/3294-dak-prescott.md
  - wiki/players/3163-jared-goff.md
related_decisions:
  - decisions/2026/2026-11-04-trade-swift-for-josh-allen.md
---

## Summary

Scouting only (no offer sent). Candidate: give Ollie Gordon II (RB, MIA) to roster 9 for Dak
Prescott (QB, DAL). Not surfaced by `trade propose --all` itself (fails its strict ±10% value
tolerance), but found by hand-checking `trade evaluate` against roster 9's actual positional need —
the automated scan's top plausibility hits this week were all marginal QB-for-QB lateral moves (see
Data). Week 11 deadline is 8 days out, so per `.claude/skills/trades.md` this is the ramp-up window.

## Reasoning

- **Our structural hole is still QB** (total VORP -13.6 across Young/Smith, avg -6.8) against a
  massive RB surplus (224.9 total VORP across 4 backs, avg 56.2) — same diagnosis as the
  2026-11-04 Swift-for-Allen scouting entry, still true a week later.
- **Roster 9 (2-7) is the mirror image**: QB is their only positive position (total VORP +20.1
  across Goff/Prescott) while RB is a clear weakness (-20.1 total). They're out of playoff
  contention at 2-7, so a 2-7 team carrying two viable QBs when only one Sleeper best-ball slot
  needs filling is plausible, low-cost-to-them surplus; Goff (VORP -1.5, 18.8 ppg) still gives them
  a competent starter if they move Prescott (VORP +21.6, 19.3 ppg) — the two are close enough in raw
  per-game output (19.3 vs 18.8) that losing Prescott isn't a big quality step down for them, while
  Gordon plugs a real need (RB2 behind Jonah Coleman/Tyler Allgeier/Jordan Mason, none of whom clear
  replacement level per `value roster --roster-id 9`).
- **Value**: `trade evaluate --give 12495 --get 3294 --value-season 2026` gives give_value=18.5,
  get_value=21.6, delta=+3.1 — slightly in our favor, not just "fair." (Note: `trade propose`'s
  default `--value-season` is `season - 1` i.e. 2025 — stale preseason value, not this season's
  actual production. Re-running with explicit `--value-season 2026` is required for in-season
  scouting; without it, `trade propose --all` surfaced implausible "upgrades" like giving Diggs for
  Caleb Williams, whose actual 2026 VORP is -36.5 after a hamstring-shortened 6-game season — worse
  than either of our current QBs.)
- **Automated scan's actual top hits this week, for comparison** (all with correct 2026
  value-season): give Geno Smith for Bo Nix (roster 4, delta +1.3, plausibility 50.7) — a lateral
  QB2-for-QB2 move, Nix's VORP (-15.1) is basically the same as Smith's (-16.3), no real upgrade.
  Give Keenan Allen/Diggs for Dak Prescott also showed up (plausibility 7-9) but those give up a
  starting-caliber WR for a move Gordon accomplishes with surplus bench depth instead.
- **News sweep** (2026-11-11, full league-wide sweep just completed) found nothing on Gordon,
  Prescott, or Goff that changes this — Gordon's most recent wiki entry is a 2026-09-28 role note
  (healthy, no new injury); Prescott and Goff have no news since 2026-08-29 camp notes, both
  currently active with no injury designation.
- **Caveat**: no `wiki/league/opponents/9.md` exists yet, so roster 9's GM tendencies (rebuild vs.
  playoff-push mentality at 2-7) are unknown — recommend judging via their actual reply if offered,
  not assuming here.

## Data

`trade evaluate --give 12495 --get 3294 --season 2026 --value-season 2026 --json`:
`{"give_value": 18.5, "get_value": 21.6, "value_delta": 3.1, "give_position_totals": {"RB": 18.5}, "get_position_totals": {"QB": 21.6}}`

`value roster --me --season 2026`: QB n=2 total=-13.6 avg=-6.8; RB n=4 total=224.9 avg=56.2
`value roster --roster-id 9 --season 2026`: QB n=2 total=20.1 avg=10.0; RB n=4 total=-20.1 avg=-5.0

## Outcome

Not sent — scouting/logging only, per this routine's scope. Recommendation for the commissioner:
worth offering manually in Sleeper ahead of the Week 11 deadline (2026-11-19). Low cost to try
(Gordon is our RB4, surplus depth) for a real upgrade at our worst position; roster 9 (2-7) has
real incentive to consolidate at a position they're already strong in exchange for help at one
they're weak in. Not urgent, but worth sending this week given the deadline proximity.
