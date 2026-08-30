# Project TODO

## In-season

- Sync `stats --season 2026` once nflverse starts publishing weekly files
  (currently 404 pre-season — verified 2026-08-23), then `stats vorp --season
  2026`. Until then `players.parquet`'s live `injury_status` tags are the only
  current availability feed.
- Watch Hunt/Ertz FA signings: if either lands somewhere, re-run
  `sleeper players sync` + `wiki sync-frontmatter` so they stop being silently
  dropped by `filter_rostered`.
- DEF ranking pass: done, but resolved as "researched and deliberately not
  ranked" rather than "shipped a ranking" — see
  `decisions/2026/2026-08-28-bigboard-def-vorp-research-streaming-recommended.md`.
  `stats vorp` now computes real team-DEF VORP, but none of the tested
  signals (own VORP, pressure rate, sack rate, points allowed) clears the
  bar for pre-draft ranking, and in-season matchup swamps a defense's own
  quality (r≈0.32 vs r≈0.09). Possible future item: a weekly DEF-streaming
  recommender (rank by upcoming opponent offensive weakness) — a different,
  unbuilt feature from the pre-draft board.

## Process follow-ups (from 2026-08-30 post-draft ADP comparison) — done 2026-08-30

See `decisions/2026/2026-08-30-draft-adp-market-comparison-post-draft-review.md` for the full
pick-by-pick review this came out of. All four items landed as skill/wiki edits rather than code
changes — the fixes are process rules for the next `bigboard` review pass and the next live draft:

- Done — added the "held out of all preseason game action as a precaution" hard downgrade flag
  to `.claude/skills/bigboard.md`'s review pass (Daniel Jones, R10).
- Done — added the "defer to ADP"/"no wiki news on file" hard-stop rule to
  `.claude/skills/draft.md` (live-draft process) with a matching annotation-language note in
  `.claude/skills/bigboard.md` (Keenan Allen, R12).
- Done — added the cited-source-caveat rule to `.claude/skills/bigboard.md`'s review pass (Juwan
  Johnson, R11).
- Done — folded "committee backfield taken at bell-cow pricing" into
  `wiki/team/draft-strategy.md`'s RB section as a named, recurring failure mode (D'Andre Swift/
  Jaylen Warren, R3/R4).
