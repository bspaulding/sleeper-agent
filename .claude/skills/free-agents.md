---
name: free-agents
description: Add/drop heuristics for the gap between waiver periods — when picking up an unclaimed free agent, and when dropping a bench keeper-eligible player is or isn't acceptable. Use when a roster move is worth considering outside the Tuesday waiver window.
---

# free-agents

`freeagent recommend --me --season <year>` ranks unrostered upgrades over the roster's weakest
rostered player *at the same position* — no FAAB bidding involved, this is for the gap between
waiver periods (post-waivers, or any time a rostered player's value has clearly fallen below an
available free agent's).

## When to act between waiver windows

- A rostered player's role changed for the worse (lost a starting job, injury with unclear
  timeline) and a clearly better free agent exists at the same position — don't wait for Tuesday
  if the roster spot is actively hurting the team.
- A free agent becomes newly relevant mid-week (a starter injury opens a backup's role) — check
  `wiki stale` / do a quick news-research pass on the situation before committing the swap, since
  `freeagent recommend`'s VORP data won't reflect a role change until stats catch up.

## When dropping a bench keeper-eligible player is/isn't acceptable

Every bench player who's keeper-eligible (`draft keepers` would show them as `ELIGIBLE`) has
future value beyond this season — dropping one is a real cost, not just a roster-management
convenience:

- **Acceptable**: the keeper-eligible player's value-per-cost (from `draft keepers`) is low —
  they're technically keeper-eligible but not actually worth the roster spot at that cost next
  year either. Also acceptable when the free-agent upgrade is large (`vorp_delta` well above
  replacement-level noise) and the roster is genuinely thin at that position now.
- **Not acceptable**: dropping a cheap, high-value-per-cost keeper candidate for a marginal
  same-season upgrade. A round-9 keeper candidate with strong value-per-cost is worth more to the
  team's 2-year outlook than a small in-season bump — check `draft keepers`' ranking before
  dropping anyone who appears there as `ELIGIBLE`, not just their raw current-season VORP.
- When genuinely unsure, prefer *not* dropping a keeper-eligible player for anything short of a
  clear, large upgrade — the downside of a bad drop (losing a cheap keeper slot) is asymmetric
  with the upside of a marginal in-season swap.

## Check waiver-clearance status before framing a recommendation

Before telling the user "submit a waiver claim" vs. "just add this player," check whether the
player has actually cleared waivers — don't infer it from trending-add count (that measures
interest, not eligibility).

The signal is **days since the player's most recent transaction, vs. this league's
`waiver_clear_days`** (2 for this league). Pull it from the transactions endpoint/parquet
(`data/sleeper/transactions/<season>.parquet`, or `GET
/league/<league_id>/transactions/<week>` for anything not yet synced locally) and find the
player's last `adds`/`drops` entry:

- **Recently transacted** (within `waiver_clear_days`, or never yet touched this season after
  being rostered/dropped) → still on waivers. A direct add will be rejected; it needs an actual
  `waiver`-type claim, and FAAB competition is real if others want it too.
- **No transaction in longer than `waiver_clear_days`** → already cleared. It's addable right now
  as a plain `free_agent` transaction, no claim, no bid, no waiting — recommending a waiver claim
  here just costs the user FAAB/time for nothing.

Caught this the hard way 2026-09-16: recommended a waiver claim + a bigger FAAB bid for a
free-agent DEF (New England) based on its ~92K trending-add count, without checking transaction
history. Its last transaction was 8 days prior — long cleared — and the user simply added it
instantly for free. Meanwhile a same-day pickup attempt on a *different* free agent (Tampa Bay)
correctly needed a waiver claim, because that one had changed hands via `waiver complete` just two
days earlier. Same "unrostered player with real interest" surface, opposite mechanics — always
check the transaction timestamp, not the trending count, before recommending which path applies.

## Logging the decision

`decisions new --kind freeagent --slug <slug> --season <year>` — note explicitly whether a
keeper-eligible player was dropped and why that was (or wasn't) an acceptable tradeoff.
