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
