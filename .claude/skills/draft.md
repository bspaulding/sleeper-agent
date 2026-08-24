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

1. Before the draft: check `wiki/team/roster-philosophy.md`, `wiki/team/draft-strategy.md`,
   `wiki/team/defense-strategy.md`, `wiki/team/rookie-evaluation.md`, `wiki/team/role-changers.md`,
   and `wiki/team/keeper-strategy.md` if they exist for standing strategy notes from prior
   seasons and general drafting theory. Run, if not already done for this season: `stats
   draft-picks sync --season <year>` (feeds the big board's rookie half), `wiki scaffold
   rookies --season <year>` and `wiki scaffold role-changers --season <prior-year>` (stub any
   missing pages for the triaged lists), and `wiki sync-frontmatter` after any `sleeper players
   sync` (keeps `nfl_team` current on already-scaffolded pages — it's only set once at scaffold
   time otherwise). Then run the **`bigboard` skill** to build/refresh
   `data/bigboard/<year>.csv` — this is what replaced "review `value rank --top 50` to build a
   mental tier list": the tier list is now a materialized, reviewed artifact, not something
   reconstructed in your head every draft. `draft board`/`watch-picks` require this file to
   exist and have zero rows flagged for review — see
   `docs/superpowers/specs/2026-08-23-draft-bigboard-design.md`.
2. During the draft: `draft board --league-id <id> --rounds 15 --me [--watch]` shows
   best-available by value, already excluding every drafted and kept player. The ranked order comes from the pre-draft big board (§1), not a live VORP sort — ties and rookie placement were already resolved during the `bigboard` skill's review, so there's nothing left to deliberate on the order itself at pick time; only the NEED/FLEX/SURPLUS tags and tier numbers (for VORP-sourced rows) are computed live, against your current roster. **Always pass
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
   - **If a refresh comes back identical to the last one, immediately retry rather than reporting
     "board unchanged."** During real-time drafting the human is on a pick clock and wants the
     fastest path to a fresh, correct board, not a diagnostic aside. Loop a few quick re-fetches
     (short/no delay) until the top-ranked player differs from the last reported board, *then*
     report — don't wait to be told a recommended player was actually already gone. Only fall back
     to flagging a possible sync issue once retries are genuinely exhausted and it's still
     identical. (2026-08-09 and 2026-08-22 mocks both hit stale single-fetch recommendations
     before this became standard.)
   - **Don't root-cause anomalies mid-pick.** If something looks wrong during a live/mock draft
     (a stale-looking refresh, an implausible roster count), do not stop to debug it in the
     moment — no raw API `curl` digging, no reading source files, no exploring the wiki. Flag it
     in one short sentence and keep moving with the refresh/recommend loop; investigate only
     after the draft (or at minimum the current pick) is done. During the 2026-08-09 mock, a
     stale board got root-caused live via direct Sleeper API calls, which cost enough time that
     two full rounds went by with no board refresh or recommendation at all — real value left on
     the board. Every second spent investigating is a second not spent picking.
   - **A wrong recommendation that gets self-corrected too late is a latency bug, not
     necessarily a staleness bug** — treat them differently. During the 2026-08-22 mock #3
     rehearsal, a Gainwell-over-Stafford recommendation was wrong because of a judgment error
     (undervaluing a backup QB's bye-week-insurance role in this league's single-QB-slot
     best-ball format — see `wiki/team/roster-philosophy.md` line ~69 on zero-scoring empty
     slots), not stale data — an immediate re-fetch confirmed the board was byte-identical. The
     correction was reasoned out correctly but took a second round-trip to post, by which point
     the original (worse) pick had already been submitted. Re-fetching more aggressively doesn't
     fix this failure mode; do the harder roster-construction/format-specific thinking (bye-week
     coverage, single-slot-position insurance, etc.) on the *first* pass, before answering, not as
     a follow-up triggered by the human pushing back with "are you sure?".
   - `--watch` polls every **5 seconds** by default (`poll_seconds` in
     `draft_tools/board.py:watch_board`) — chosen from Sleeper's own documented rate limit ("stay
     under 1000 API calls per minute, otherwise you risk being IP-blocked," per
     `docs.sleeper.com`): one picks-endpoint GET per poll at 5s means ~12 requests/minute, about
     1% of that budget, so there's no reason to poll any slower. If a draft is moving unusually
     fast (e.g. an all-bot rapid mock), it's safe to poll even faster — 1-second polling is still
     only 60 req/min, 6% of the limit — there's no rate-limit reason to ever default back toward
     the old 30s cadence that caused the missed-rounds problem above.
   - **Preferred live setup: `draft watch-picks` under a `Monitor`-tool wrapper.** Run
     `sleeper-agent draft watch-picks --draft-id <id> --value-season <year> --draft-slot <n>`
     (or `--league-id`/`--me` for the real league draft) under `Monitor` — no `--num-teams`
     or `--rounds` needed, the draft's own `settings.teams`/`settings.rounds` drive the snake
     math so a 10-team draft can't be silently scored as 12. It
     streams one line per pick (not the whole board, unlike `--watch`) and, the moment the next
     pick is mine, fetches and prints the full board inline in that same event — no separate
     round-trip. This replaced an ad hoc bash Monitor-loop script that used to be rewritten from
     scratch each draft (see `docs/superpowers/plans/2026-08-22-draft-watch-picks.md` and
     `decisions/2026/2026-08-22-draft-mock-draft-3-slot8.md`) — the snake-order math and turn
     detection are now tested project code (`draft_tools/board.py::slot_for_pick`/`watch_picks`),
     not something re-derived live. There is still no way to auto-submit the actual pick — this
     project's Sleeper client is read-only and Sleeper has no public pick-submission endpoint —
     so the human still clicks the pick in Sleeper; the goal is only to get the recommendation
     into their hands the instant it's computable.
   - **Present each pick-clock recommendation as a short table** (player, position, VORP,
     NEED/FLEX/SURPLUS status) for the top 2-4 candidates, then 1-3 sentences of the actual
     judgment call (tier cliffs, NEED vs. FLEX/SURPLUS, roster-construction risk) — not prose
     alone. Confirmed during the 2026-08-22 mock #3 as a fast-scannable format under a live pick
     clock; don't expand it into a large table — `draft board`'s own output is already the full
     dump, this is just the live decision set.
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
   - **Rookies are already placed in the main board** — the reasoning chain that used to run
     live here (round-hit-rate weighting, tier-cliff comparison, best-ball-forgives-a-slow-start
     shading, news-line tie-breaking) now runs during the `bigboard` skill's pre-draft review
     instead, calmly and without a clock. If a rookie's board position ever looks wrong mid-draft,
     that's a `bigboard` skill problem to fix after the draft (or before the next one), not
     something to re-litigate live.
   - **A `[MOVED: <old>→<new>]` tag is a different kind of signal** — that player already has a
     real VORP number computed from last season; the tag just flags that the team/scheme context
     behind it may no longer hold. It's "trust this number more or less than face value," not a
     separate bucket to weigh against the rest of the board. Check the player's wiki page (linked
     research from `wiki/team/role-changers.md`'s vacated-opportunity/scheme-continuity framework)
     before trusting the raw figure — e.g. a confirmed clean vacancy argues the real number is
     probably *better* than last season's VORP suggests, a muddied committee/depth-chart
     situation argues *worse*.
4. After the draft: file a `decisions new --kind draft --slug <slug>` entry summarizing the full
   draft (or let a running `draft-live.md` entry from `--watch` stand as the record, promoted to a
   final decision entry), and update `wiki/team/roster-philosophy.md` with anything learned.

## Notes

- If a mock draft's `draft board --me`/`--draft-slot` roster summary ever looks implausible (e.g.
  stuck at all-zero counts deep into the draft), that was a real bug once — Sleeper returns
  `roster_id: null` on every pick in a mock draft, and ownership matching used to rely on
  `roster_id` alone, silently zeroing out the whole annotation. Fixed in `board.py` (matches on
  `draft_slot` instead when resolved via `--draft-slot`) per
  `decisions/2026/2026-08-22-draft-mock-draft-2-abandoned-retro.md` — if it recurs, suspect a
  regression of this exact bug before assuming fresh data lag.
- `draft keepers`' value uses the most recently completed season's VORP by default
  (`--value-season` overrides this) — sanity-check that this is actually the right season to value
  players against before trusting the ranking blindly, especially early in a new season when a
  player's situation may have changed materially since that data was computed.
- Always validate `draft keepers` against known real keeper picks from the prior season before
  trusting it for a new season's real decision (see `IMPLEMENTATION_PLAN.md`'s Phase E DoD) — if
  the eligibility/cost for a known real case looks wrong, stop and debug before using it live.
