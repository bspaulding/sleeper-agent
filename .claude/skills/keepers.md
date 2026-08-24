---
name: keepers
description: Choose which ≤2 keepers to lock in and at what cost, ahead of the keeper deadline each season. Use once a year, before the deadline, and re-use the same process next year.
---

# keepers

`sleeper-agent draft keepers --me --season <year>` lists every rostered player with eligibility,
cost, and VORP, already ranked by **value-per-cost** (VORP ÷ cost round), not raw value — that
ranking is mechanical, but the final call is not:

- Pick **at most 2** keepers. The tool ranks eligible players by value-per-cost; the top 2 by that
  metric is the default recommendation, but override it when:
  - A cheap round-9 keeper's raw value is low in absolute terms even though its value-per-cost is
    high — check the tool's raw `vorp=` figure too, not just the ranking position. A replacement-level
    round-9 keeper isn't worth a roster spot even at a great "price."
  - A player about to lose keeper eligibility (already kept 2 consecutive seasons, per the
    `ineligible ... kept N consecutive seasons already` line) can still be drafted normally in the
    live portion — don't treat "ineligible as a keeper" as "not worth having," just "not free
    this year."
  - Positional need matters: check `value roster --me` for where the roster is thin. A
    moderate-value keeper at a scarce position can be worth more than the tool's raw
    value-per-cost ranking implies, since VORP alone doesn't model roster construction.
- Log the final decision with `decisions new --kind keeper --slug <slug> --season <year>`,
  filling in Summary/Reasoning/Data with the specific players, costs, and why (including why any
  top-ranked-by-tool candidate was passed over, if one was).

## Notes

- `draft keepers`' value uses the most recently completed season's VORP by default
  (`--value-season` overrides this) — sanity-check that this is actually the right season to value
  players against before trusting the ranking blindly, especially early in a new season when a
  player's situation may have changed materially since that data was computed.
- Always validate `draft keepers` against known real keeper picks from the prior season before
  trusting it for a new season's real decision (see `IMPLEMENTATION_PLAN.md`'s Phase E DoD) — if
  the eligibility/cost for a known real case looks wrong, stop and debug before using it live.
