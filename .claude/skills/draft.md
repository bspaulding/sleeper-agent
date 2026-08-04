---
name: draft
description: Choose which ≤2 keepers to lock in and at what cost, then run full-roster snake-draft strategy for the live portion of the 15-round draft. Use ahead of the keeper deadline and during the live draft.
---

# draft

## Keeper selection

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

## Live snake draft (the ~13 non-keeper spots)

This is close to a full startup draft each year (§0 of `IMPLEMENTATION_PLAN.md`), not a small
supplemental round — treat it that way:

1. Before the draft: review `value rank --top 50` (and by position) to build a mental tier list.
   Check `wiki/team/roster-philosophy.md` and `wiki/team/keeper-strategy.md` if they exist for
   standing strategy notes from prior seasons.
2. During the draft: `draft board --league-id <id> --rounds 15 [--watch]` shows best-available by
   value, already excluding every drafted and kept player. Use `--watch` for an unattended or
   semi-attended session — it polls and re-renders on every change, and mirrors the board to a
   decision-log entry (`decisions/<season>/<date>-draft-live.md`) so there's a record even if
   nobody's watching every pick.
   - For a **mock draft** (practice run before the real draft — no league object exists for it),
     use `draft board --draft-id <mock-draft-id> --value-season <year> [--num-teams <n>] [--watch]`
     instead: it points straight at the draft's public picks endpoint, skipping the league lookup
     `--league-id` needs. `--value-season` is required in this mode (there's no league to infer it
     from); `--num-teams` defaults to 12 (this league's size) and only matters for `--rounds`
     sizing. Do a mock draft or two in the run-up to the real one — it's cheap rehearsal for tier
     breaks and pacing, and a chance to sanity-check the value rankings against how a real room
     actually drafts.
3. Draft-day judgment the tool can't automate:
   - Positional runs: if a position is being drafted heavily by other teams, weigh reaching for
     the position against best-player-available — `draft board`'s ranking is value-only, it
     doesn't model positional scarcity dynamics mid-draft.
   - Bye-week and roster-construction balance (`PROJECT_PLAN.md`'s best-ball note means no
     start/sit optimization is needed — but roster *construction* balance, e.g. not stacking too
     many players from the same bye week at a thin position, still matters).
   - A player who just became keeper-ineligible after 2 years (see above) may be a value target
     if their price has dropped relative to their real ability.
4. After the draft: file a `decisions new --kind draft --slug <slug>` entry summarizing the full
   draft (or let a running `draft-live.md` entry from `--watch` stand as the record, promoted to a
   final decision entry), and update `wiki/team/roster-philosophy.md` with anything learned.

## Notes

- `draft keepers`' value uses the most recently completed season's VORP by default
  (`--value-season` overrides this) — sanity-check that this is actually the right season to value
  players against before trusting the ranking blindly, especially early in a new season when a
  player's situation may have changed materially since that data was computed.
- Always validate `draft keepers` against known real keeper picks from the prior season before
  trusting it for a new season's real decision (see `IMPLEMENTATION_PLAN.md`'s Phase E DoD) — if
  the eligibility/cost for a known real case looks wrong, stop and debug before using it live.
