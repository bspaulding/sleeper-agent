---
last_updated: '2026-08-28'
source: 2026 keeper decision (decisions/2026/2026-08-23-keeper-diggs-r7-darnold-r14.md),
  revised (decisions/2026/2026-08-28-keeper-swap-darnold-to-judkins.md)
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
(sorted descending, mapped to snake slots), **and re-recompute any time the
underlying VORP data changes** (see Known traps below — this happened for
real in 2026). 2026's table (from 2025 VORP, post-2026-08-27 postseason-VORP
fix):

| Round | Picks | Avg VORP | Round | Picks | Avg VORP |
|---|---|---|---|---|---|
| R1 | 1–12 | 195.2 | R9 | 97–108 | 1.1 |
| R2 | 13–24 | 106.0 | R10 | 109–120 | −15.2 |
| R3 | 25–36 | 73.1 | R11 | 121–132 | −24.9 |
| R4 | 37–48 | 47.6 | R12 | 133–144 | −35.8 |
| R5 | 49–60 | 37.6 | R13 | 145–156 | −43.5 |
| R6 | 61–72 | 28.1 | R14 | 157–168 | −49.5 |
| R7 | 73–84 | 14.6 | R15 | 169–180 | −57.5 |

(Prior table, superseded 2026-08-28: R1 207.0, R3 83.1, R5 33.2, R7 14.1, R8
2.2, R14 −62.9, R15 −74.0 — built on VORP data that silently included
postseason games. Kept here as a reminder of how much a data-pipeline bug can
move these numbers.)

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
- **Re-run the whole analysis after any VORP/board-data fix, before the
  deadline, even if a decision already looked final.** The 2026-08-23 pick of
  Darnold at R14 was correct given the data at the time, but the 2026-08-27
  postseason-VORP fix (`decisions/2026/2026-08-27-bigboard-season-type-postseason-fix.md`)
  changed his VORP from +7.0 to −30.5 (his team played 4 extra playoff games
  that were silently counted as "season" stats). A stale decision built on
  fixed-later data doesn't self-correct — treat any stats/VORP/bigboard
  pipeline fix as a trigger to re-run `draft keepers` and re-check surplus,
  not just a data-quality footnote. See `decisions/2026/2026-08-28-keeper-swap-darnold-to-judkins.md`.
- **A late-round surplus that's positive only because the baseline is bad is
  a weaker signal than absolute production.** Concretely: check whether the
  player's own VORP is itself positive (real, current production) before
  trusting a surplus number built off a deeply negative R13+ baseline — a
  below-replacement player can still show "surplus" purely because the
  alternative pick is worse. Prefer a smaller surplus backed by real
  production over a larger surplus that's mostly baseline artifact.
- **The current roster snapshot (`value roster --me`) is not "who's on the
  2026 team" — it's "who's on the roster today."** Every non-kept player,
  regardless of position, returns to the open draft pool at the live draft.
  Don't reason "we don't need to keep a player at position X because we
  already have player Y at position X" unless Y is *also* being kept —
  otherwise both return to the pool together and the position ends up
  covered by neither.
- **Positions differ in how bad their in-season replacement really is.** A
  1-QB league has many streamable/waiver-viable backup QBs; a true every-down
  RB has no equivalent waiver safety net. When a marginal late-round keeper
  slot is close between a QB and a difference-making RB/WR, this asymmetry
  favors keeping the skill-position player even at a roughly tied surplus
  number — the real opportunity cost of losing the QB is smaller than the
  bare baseline implies.

## League-wide projection

Each August before the deadline, project every team's keeps (run
`draft keepers --roster-id <n> --season <y>` for all rosters, apply the
surplus test + owner-judgment priors) so draft prep knows who's off the
pool. 2026's projection lives in
`wiki/league/projected-keepers-2026.md`; verify against Sleeper's actual
`is_keeper` picks when they appear on the draft object.
