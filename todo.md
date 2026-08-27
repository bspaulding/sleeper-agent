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
- Partial news sweep done 2026-08-27 as `decisions/2026/2026-08-27-bigboard-injury-status-review.md`
  (McCaffrey/Jeanty/Charbonnet/Tyson/Higgins/Pearsall moved; Jacobs/Nacua reviewed, no change).
  Left explicitly open pending a follow-up: **Judkins** (nagging knee vs. possibly-future-dated
  search results), **Olave** (resolved medical-tent exit vs. possibly-future-dated search
  results), **Thornton** (not reached). The automated sweep below picks these up.
- The `sleeper-agent: draft day` one-shot Routine existed but was broken (wrong
  `environment_id` — no repo checkout/git creds, confirmed via the 2026-08-26
  `pre-draft prep` one-shot's failed run log which shared the same bad environment) and
  stale (referenced the retired `.claude/skills/draft.md` and a `--watch` flag that no
  longer exists). Rather than fix it as a live in-draft tracker — not useful, since a
  routine's live session isn't watchable from the Claude app and Brad drafts manually in
  Sleeper anyway — repurposed 2026-08-27 into **`sleeper-agent: pre-draft news sweep`**:
  fires Saturday Aug 29, 1:00pm PT (2026-08-29T20:00:00Z, 2hrs ahead of the 3pm PT draft),
  re-checks the Judkins/Olave/Thornton opens above plus Jacobs'/Nacua's/Jeanty's statuses,
  and hand-edits `data/bigboard/2025.csv` + files a `decisions --kind bigboard` entry if
  anything material changed. The companion `sleeper-agent: pre-draft prep` one-shot fired
  2026-08-26 but hit the same bad environment and did nothing useful; it's spent now
  (won't refire) and isn't being recreated since the news-sweep Routine above covers it.
- Swept the other three cadence Routines (weekly stats/VORP, waiver reminder, trade
  scouting) for the same kind of staleness. Weekly stats/VORP sync's commands are all
  still current. Fixed 2026-08-27: `waiver window reminder`'s `waiver recommend` and
  `trade scouting`'s `trade propose` calls were both missing the now-required `--season`
  flag (they'd been silently self-correcting via each prompt's "check `--help` if stale"
  fallback — worked, but fragile); `trade scouting` also had a typo'd `sleeper sync` →
  fixed to `sleeper league sync`.
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
