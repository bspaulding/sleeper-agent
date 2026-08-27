# Project TODO

## Mock draft feedback triage (2026-08-27, draft 1397736844753412096)

Raw feedback from a live mock draft (slot 8), triaged by replaying the draft's real picks
(`GET /v1/draft/1397736844753412096/picks`, fetched and analyzed 2026-08-27) against the actual
`position_tag`/`compute_vorp` code, not guessed from the complaint text alone.

- **"Too many RBs, still!" is a ranking/VORP issue, not a tagging issue — confirmed separate from
  the shared-FLEX-pool bug fixed 2026-08-27 (`position_tag`/`remaining_flex_capacity` in
  `board.py`, now two independent NEED-or-SURPLUS + FLEX tags), per direct clarification.** The
  board is recommending too many RBs near
  the top of the list itself (a value/replacement-baseline question), not because of any
  NEED/FLEX/SURPLUS mistagging. Needs its own investigation into why RB ranks so richly relative
  to WR right now — start with `stats/vorp.py`'s `compute_replacement_ranks`/
  `DEFAULT_FLEX_WEIGHTS` (the replacement-level baseline per position) rather than `board.py`.
  Likely connects to the VORP-projection gap below (a stale/retrospective baseline could be
  misjudging RB scarcity for the coming season) but confirm before assuming they're the same fix.
  **Quantified 2026-08-27** (`wiki/team/bigboard-external-comparison.md`): our top 12 runs 8 RB vs.
  5–7 in two published external top-12s — real, but a moderate rebalance, not evidence the board
  is drastically broken. **Re-verified after the postseason-VORP bug fix same day** (see below) —
  still 8 RB in the top 12, unchanged by that fix, so this is genuine replacement-level scarcity
  (RB's rank-35 replacement level is worse in ppg terms than WR's, at the same replacement rank),
  not a data bug. Still open: is 8-vs-5-7 worth tuning `DEFAULT_FLEX_WEIGHTS`, or is it correct as-is.
- **Injury severity note missing — confirms an existing todo item, not a new one.** `[INJ:
  <status>]` (`board.py`/`board_app.py`) just echoes Sleeper's raw `injury_status` string
  verbatim with no severity/impact judgment. This is the same gap as the "bigboard... does not
  take into account injury statuses" item below (bigboard notes for role-changers/injuries) —
  this mock draft is a live confirmation that gap is still open, not a separate ask.
- **VORP has no projected-output signal — fundamental, needs its own spec, not a quick fix.**
  Confirmed via `cli/src/sleeper_agent/stats/vorp.py::compute_vorp`: it is purely retrospective,
  built only from a completed `--value-season`'s actual weekly stats — there is no projections
  data source anywhere in the pipeline. Needed: (a) a projections data feed/sync (same shape as
  the existing nflverse weekly-stats sync), (b) a `vorp_projected` metric (VORP over replacement
  using projected rather than realized season output) alongside today's realized-stats VORP, (c)
  a decision on how `bigboard build`/live `draft board` blend or choose between the two (and
  whether this changes the bigboard spec's "VORP stays purely quantitative" constraint). Scope as
  a new doc under `docs/superpowers/specs/`, not a one-line change.
  **Narrowed 2026-08-27** (`decisions/2026/2026-08-27-bigboard-season-type-postseason-fix.md`):
  most of the "overvalued" evidence gathered below (McCaffrey, Kyren Williams, Etienne, Swift,
  Pitts, the whole QB group) turned out to be a real, separate bug — postseason games silently
  counted into "season" VORP — not the projection gap. **Fixed** (`stats/vorp.py` now filters
  `season_type == "REG"`; `data/vorp/2025.parquet` and `data/bigboard/2025.csv` regenerated, 370
  tests passing). What's left after that fix — Chase, A.J. Brown, DeVonta Smith, Nico Collins
  undervalued; nothing forward-looking to catch injury-recovery/repeatability risk — is the real,
  still-open projection gap this item describes.
- ~~**Compare our bigboard/VORP ranking against Sleeper's own rankings and analyze.**~~ **Done
  2026-08-27** — Sleeper doesn't expose a real ranking via its public API (`search_rank` is a
  search-relevance field contaminated by real-world fame, not fantasy value — confirmed via Tom
  Brady/Todd Gurley). Compared against two published external rankings (Bleacher Report, ESPN
  Field Yates) instead; see `wiki/team/bigboard-external-comparison.md` and
  `decisions/2026/2026-08-27-bigboard-external-consensus-comparison.md`. Feeds the two items above.

## Before the draft (Saturday, Aug 29)

- bigboard evals currently include special placings for rookies, but do not (i think?)
  take into account injury statuses and other news about a player, like a reduced role
  for role changers. We should make sure this is taken into account and that the bigboard
  has notes for those players that were moved out of their vorp slot for a some reason.
- Easter Egg / Fun Draft reviewer: Yahoo Fantasy Used to have these draft grade
  reports they would email out after the draft. It would be fun to have a tongue-in-cheek
  reviewer for the whole league, driven by an llm skill. We would want it to look at each
  resulting roster post draft, and use our own rankings + some LLM persona to write a quick
  graded (A-F) review of each drafter. It could also grant some superlative "trophies"
  to certain players.
- Verify our `is_keeper` flags (Diggs/Darnold) once they appear on the draft
  object's `/picks` endpoint (not visible pre-lock as of Aug 23), and diff
  `wiki/league/projected-keepers-2026.md` against the real inserted set.
- One more full news sweep (`news-research.md`) on Aug 27–28 — statuses still
  fluid: Kittle PUP/practice clearance, Olave post-medical-tent, Thornton return,
  Judkins nagging knee.
- Create the draft-day one-shot Routine (`IMPLEMENTATION_PLAN.md` Phase H) with
  `run_once_at` set to the actual draft window — the date is now known.

## Routines first successful fire (before week 1, Sept 9)

The three recurring Routines (weekly stats/VORP Tuesdays, waiver reminder
Mondays, trade scouting Wednesdays) were created in Phase H but have never had
a genuine run — they no-op'd while implementation was unmerged. Everything is
on `main` now; verify via next scheduled firing or manual `fire_trigger`.

## In-season

- Replace `KeeperEligibleUndraftedDefault`'s hard R15 fallback with the
  clarified rule (traded/FA players reset to current DraftSharks
  Sleeper/PPR/12-team ADP − 1): needs an ADP lookup integration plus a way to
  pin/reference the ADP snapshot used at keep time.
- Sync `stats --season 2026` once nflverse starts publishing weekly files
  (currently 404 pre-season — verified 2026-08-23), then `stats vorp --season
  2026`. Until then `players.parquet`'s live `injury_status` tags are the only
  current availability feed.
- Watch Hunt/Ertz FA signings: if either lands somewhere, re-run
  `sleeper players sync` + `wiki sync-frontmatter` so they stop being silently
  dropped by `filter_rostered`.
