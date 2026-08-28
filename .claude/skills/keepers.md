---
name: keepers
description: Choose which ≤2 keepers to lock in and at what cost, ahead of the keeper deadline each season. Use once a year, before the deadline, and re-use the same process next year.
---

# keepers

`sleeper-agent draft keepers --me --season <year>` lists every rostered player with eligibility,
cost, and VORP, ranked by **value-per-cost** (VORP ÷ cost round) — that ranking is mechanical and
answers the wrong question. Use the **keeper surplus** method instead (standing method, see
`wiki/team/keeper-strategy.md`): `surplus = player VORP − expected VORP of the pick in his cost
round` (round baselines come from the current VORP board, recomputed each year). Keeper slots are
a knapsack of exactly 2 — every candidate competes against every other candidate for the same two
slots, not against zero — so take the pair with the highest *combined* surplus, then override on:

- **Absolute production over baseline-artifact surplus.** A late-round (R13+) surplus can be
  positive purely because the replacement baseline there is deeply negative, even when the
  player's own VORP is itself below replacement. Check the raw `vorp=` figure, not just the
  surplus number — prefer a smaller surplus backed by real, positive production over a larger one
  that's mostly baseline artifact.
- **Cost ≈ market ⇒ surplus ≈ 0.** A player whose cost round matches his realistic draft price
  gains nothing by being kept — better to release and re-draft at market.
- **Eligibility loss ≠ worthlessness.** A player who's hit the 2-consecutive-season keeper cap
  (`ineligible ... kept N consecutive seasons already`) can still be drafted normally in the live
  portion — "not free this year," not "not worth having."
- **Positional need, checked correctly.** `value roster --me` shows the *current* roster's
  positional VORP breakdown — useful for spotting genuinely thin/strong positions (e.g. a
  position sitting deeply negative across every rostered player at that spot is a real signal).
  But every non-kept player, regardless of position, returns to the open draft pool at the live
  draft — **don't reason "we don't need to keep at position X because we already have player Y
  there" unless Y is also being kept**, or both leave together and the position ends up covered
  by neither.
- **Position-specific replacement quality.** Positions differ in how bad their in-season
  replacement really is — e.g. in a 1-QB league, streamable/waiver-viable backup QBs are
  plentiful, while a true every-down RB/WR has no equivalent waiver safety net. When a marginal
  keeper slot is close between a QB and a difference-making RB/WR, this favors the skill-position
  player even at a roughly tied surplus number.
- **Role changers:** VORP earned elsewhere doesn't automatically travel — check
  `wiki/team/role-changers.md` before trusting the number for a traded/signed player.
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
- **Re-run this whole analysis after any stats/VORP/bigboard data fix lands, even if a keeper
  decision already looked final and even after locking picks in Sleeper** — up until the actual
  deadline, a prior decision built on since-corrected data doesn't self-correct on its own. This
  happened for real in 2026: a postseason-games-leaking-into-season-totals bug fix swung one
  player's VORP by nearly 40 points and flipped the correct second keeper (see
  `decisions/2026/2026-08-28-keeper-swap-darnold-to-judkins.md`). Treat any upstream data-pipeline
  fix as a trigger to re-check keeper surplus, not just a data-quality footnote.
- For an injury/availability flag left explicitly unresolved by a bigboard review (search results
  too ambiguous to act on), do a fresh, date-scoped check before the keeper deadline rather than
  inheriting the ambiguity — it can be the deciding factor between two close candidates.
