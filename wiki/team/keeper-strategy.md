---
last_updated: '2026-08-23'
source: 2026 keeper decision (decisions/2026/2026-08-23-keeper-diggs-r7-darnold-r14.md)
---

# Keeper strategy — standing method

How to evaluate keeper decisions in this league. Distinct from
`draft-strategy.md` (general drafting theory) and `roster-philosophy.md` (this
team's retrospectives). First written during the 2026 keeper call, where the
CLI's value-per-cost ranking was shown to answer the wrong question.

## The rule set (as confirmed)

- Up to 2 keepers per team; keeper auto-drafted **one round earlier than last
  year's draft slot** (`cost = last_round - 1`). Round 1 cost invalid (player
  drafted/kept at R1 is ineligible). Max 2 consecutive kept seasons.
- **Traded players and FA pickups reset to the player's current ADP − 1**
  (clarified 2026-08-23, commissioner Aaron). Reference source:
  `draftsharks.com/adp/ppr/sleeper/12`. The CLI's undrafted fallback (hard
  R15) predates this clarification — see todo.md.
- Non-kept players all return to the open pool; the roster is rebuilt at the
  draft except for keepers. Keeper slots are therefore a **knapsack of
  exactly 2**: every candidate competes against the others for the same two
  slots, not against zero.

## The method: keeper surplus, not value-per-cost

Value-per-cost (what `draft keepers` ranks by) rewards cheapness regardless
of what the pick would otherwise fetch. The correct test:

> **keeper surplus = player VORP − expected VORP of the pick in his cost
> round**

Keeping a player means spending that pick on him instead of the open market;
a keeper is +EV only if he beats the replacement pick at that slot. Then take
the pair with the highest combined surplus.

Round baselines shift year to year — recompute from the current VORP board
(sorted descending, mapped to snake slots). 2026's table (from 2025 VORP):

| Round | Picks | Avg VORP | Round | Picks | Avg VORP |
|---|---|---|---|---|---|
| R1 | 1–12 | 207.0 | R9 | 97–108 | −9.4 |
| R2 | 13–24 | 123.1 | R10 | 109–120 | −26.4 |
| R3 | 25–36 | 83.1 | R11 | 121–132 | −39.0 |
| R4 | 37–48 | 50.3 | R12 | 133–144 | −46.8 |
| R5 | 49–60 | 33.2 | R13 | 145–156 | −54.4 |
| R6 | 61–72 | 23.9 | R14 | 157–168 | −62.9 |
| R7 | 73–84 | 14.1 | R15 | 169–180 | −74.0 |

## Known traps

- **Late-round surpluses are inflated.** An R13–R15 keep beats a terrible
  baseline almost by definition; check the player's *absolute* production
  too, and remember the slot competes with the other keeper slot, not with
  nothing.
- **Cost ≈ market ⇒ surplus ≈ 0.** A player whose cost round matches his
  realistic draft price (check ADP) gains nothing by being kept — e.g.
  keeping a rising second-year player at R3 when the market drafts him at
  R2–R3 anyway. Better to release and re-draft at market.
- **Role changers:** VORP earned elsewhere doesn't automatically travel —
  evaluate via `wiki/team/role-changers.md` before trusting the number
  (2026 example: Diggs NE→WAS).
- **FA/trade ADP resets cut both ways:** they also mean acquiring a star via
  trade does NOT carry his old discount — traded players cost ADP − 1 to
  keep, usually full retail for good players.

## League-wide projection

Each August before the deadline, project every team's keeps (run
`draft keepers --roster-id <n> --season <y>` for all rosters, apply the
surplus test + owner-judgment priors) so draft prep knows who's off the
pool. 2026's projection lives in
`wiki/league/projected-keepers-2026.md`; verify against Sleeper's actual
`is_keeper` picks when they appear on the draft object.
