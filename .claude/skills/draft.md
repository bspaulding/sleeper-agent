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
   Check `wiki/team/roster-philosophy.md`, `wiki/team/draft-strategy.md`, and
   `wiki/team/keeper-strategy.md` if they exist for standing strategy notes from prior seasons
   and general drafting theory.
2. During the draft: `draft board --league-id <id> --rounds 15 --me [--watch]` shows
   best-available by value, already excluding every drafted and kept player. **Always pass
   `--me`** (or `--roster-id <id>` if not drafting from this team's usual roster_id) — without
   it, the board has no roster-need annotation at all (no "My roster so far" summary, no
   NEED/FLEX/SURPLUS tags, no per-position `tier=N` numbers), which is exactly the gap that let
   the first 2026 mock draft go 8 RB/2 WR/0 DEF unnoticed. Use `--watch` for an unattended or
   semi-attended session — it polls and re-renders on every change, and mirrors the board to a
   decision-log entry (`decisions/<season>/<date>-draft-live.md`) so there's a record even if
   nobody's watching every pick.
   - For a **mock draft** (practice run before the real draft — no league object exists for it),
     use `draft board --draft-id <mock-draft-id> --value-season <year> --draft-slot <n>
     [--num-teams <n>] [--watch]` instead: it points straight at the draft's public picks
     endpoint, skipping the league lookup `--league-id` needs. `--value-season` is required in
     this mode (there's no league to infer it from); `--draft-slot` is the slot number chosen
     when starting the mock (needed for annotation, since a mock draft has no stable roster_id —
     `--me` won't resolve to anything meaningful there); `--num-teams` defaults to 12 (this
     league's size) and only matters for `--rounds` sizing. Do a mock draft or two in the run-up
     to the real one — it's cheap rehearsal for tier breaks and pacing, and a chance to
     sanity-check the value rankings against how a real room actually drafts.
   - **Never recommend a pick off stale data.** Fetch a fresh `draft board` immediately before
     every recommendation — even one from moments ago is not good enough, since picks can happen
     faster than the conversation moves (bot-heavy mock/live drafts especially). This applies
     whether you're driving `--watch` or manually re-running `draft board` once per "it's my turn"
     prompt: always issue a new fetch, never answer from a previous call's output. The first 2026
     mock draft (`decisions/2026/2026-08-09-draft-mock-draft-1-turn-by-turn.md`) lost two entire
     rounds to exactly this — the board wasn't re-fetched often/promptly enough and the picks
     happened underneath it.
   - `--watch` polls every **5 seconds** by default (`poll_seconds` in
     `draft_tools/board.py:watch_board`) — chosen from Sleeper's own documented rate limit ("stay
     under 1000 API calls per minute, otherwise you risk being IP-blocked," per
     `docs.sleeper.com`): one picks-endpoint GET per poll at 5s means ~12 requests/minute, about
     1% of that budget, so there's no reason to poll any slower. If a draft is moving unusually
     fast (e.g. an all-bot rapid mock), it's safe to poll even faster — 1-second polling is still
     only 60 req/min, 6% of the limit — there's no rate-limit reason to ever default back toward
     the old 30s cadence that caused the missed-rounds problem above.
3. Draft-day judgment the tool can't automate:
   - Positional runs: if a position is being drafted heavily by other teams, weigh reaching for
     the position against best-player-available. `draft board --me` now shows the facts this
     judgment call needs — my-roster position counts vs. the roster grid, and a per-row `tier=N`
     number that jumps when a real value cliff hits a position — but weighing reach-vs-wait
     against those facts is still a judgment call the tool doesn't make for you. See
     `wiki/team/draft-strategy.md` for the general reasoning (tiered drafting, RB strategy
     spectrum).
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
