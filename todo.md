# Project TODO

## Before the draft (Saturday, Aug 29)

- Easter Egg / Fun Draft reviewer: Yahoo Fantasy Used to have these draft grade
  reports they would email out after the draft. It would be fun to have a tongue-in-cheek
  reviewer for the whole league, driven by an llm skill. We would want it to look at each
  resulting roster post draft, and use our own rankings + some LLM persona to write a quick
  graded (A-F) review of each drafter. It could also grant some superlative "trophies"
  to certain players.
- Verify our `is_keeper` flags (Diggs/Darnold) once they appear on the draft
  object's `/picks` endpoint (not visible pre-lock as of Aug 23), and diff
  `wiki/league/projected-keepers-2026.md` against the real inserted set.
- Follow up on the three cases the 2026-08-27 injury-status review left open (see
  `decisions/2026/2026-08-27-bigboard-injury-status-review.md`): **Judkins**, **Olave**,
  **Thornton**. The scheduled `sleeper-agent: pre-draft news sweep` Routine (fires
  Saturday 1:00pm PT, 2hrs ahead of the 3pm PT draft) should pick these up automatically —
  check its report before the draft in case it didn't.
- **`data/bigboard/<season>.csv` has zero DEF rows — `draft board` can never recommend a
  defense.** DEF sits at 0/1 NEED all draft and the board never surfaces a single DEF candidate.
  Needs a DEF ranking source feeding `bigboard build` before Saturday.
- **VORP has no projected-output signal — fundamental, needs its own spec, not a quick fix.**
  Confirmed via `cli/src/sleeper_agent/stats/vorp.py::compute_vorp`: it is purely retrospective,
  built only from a completed `--value-season`'s actual weekly stats — there is no projections
  data source anywhere in the pipeline. Needed: (a) a projections data feed/sync (same shape as
  the existing nflverse weekly-stats sync), (b) a `vorp_projected` metric (VORP over replacement
  using projected rather than realized season output) alongside today's realized-stats VORP, (c)
  a decision on how `bigboard build`/live `draft board` blend or choose between the two (and
  whether this changes the bigboard spec's "VORP stays purely quantitative" constraint). Scope as
  a new doc under `docs/superpowers/specs/`, not a one-line change.

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
- `draft board` has no machine-readable "it's your turn now" signal. A `--notify-my-turn` mode
  would remove the need for a second poller reimplementing `slot_for_pick`. Not urgent.
