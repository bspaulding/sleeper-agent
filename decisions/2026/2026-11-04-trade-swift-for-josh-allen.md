---
date: '2026-11-04'
kind: trade
season: '2026'
week: null
status: recommended
players_involved:
  - D'Andre Swift
  - Josh Allen
related_wiki: []
---

## Summary

Scouting only (no offer sent). Candidate: give D'Andre Swift (RB, CHI) to roster 10 for Josh Allen (QB, BUF). Top-plausibility result from `trade propose --all` (plausibility 83.7, value delta -3.2). Week 11 deadline is ~2 weeks out.

## Reasoning

- Our QB room is the structural hole: QB total VORP -30.9 (Young, Darnold) vs RB 222.6 across 5 RBs. Swift is surplus RB depth; Allen is a large QB upgrade at a small value cost (-3.2).
- Caveat: roster 10 (5-2) is RB-heavy already (Jeanty, Kamara, Hubbard) and has Watson as its only other QB, so the other side gets limited need-fill from Swift and may balk. Judge fit by their GM tendencies (check wiki/league/opponents/10.md if present). Other QB ideas were lower-plausibility or cost more value.
- News sweep found nothing verifiable and dated after 2026-11-03 (searches returned prior-year articles), so no injury info changes this.
- Recommendation for the commissioner: worth offering manually in Sleeper; moderately strong, not urgent. Consider a sweetener only if they push back.

## Data

`trade evaluate --give 6790 --get 4984 --season 2026 --json`:
`{"give_value": 94.9, "get_value": 91.7, "value_delta": -3.2, "give_position_totals": {"RB": 94.9}, "get_position_totals": {"QB": 91.7}}`

## Outcome

Passed 2026-11-04 by the manager: roster 10 is unlikely to accept (5-2, RB-heavy, Allen is their QB1) and QB is not costing wins. No offer sent. See decisions/2026/2026-11-04-waiver-week9-def-stream-check-hold-tb-no-moves.md.
