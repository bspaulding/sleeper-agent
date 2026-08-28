# Project TODO

## Before the draft (Saturday, Aug 29)

- Verify our `is_keeper` flags (Diggs/Darnold) once they appear on the draft
  object's `/picks` endpoint (not visible pre-lock as of Aug 23), and diff
  `wiki/league/projected-keepers-2026.md` against the real inserted set.

## In-season

- Re-run `adp sync` before any live keeper/trade decision that needs a fresh
  ADP-reset number (`draft keepers`'s ADP-reset cost uses whatever snapshot
  was last synced, not a live lookup).
- Sync `stats --season 2026` once nflverse starts publishing weekly files
  (currently 404 pre-season — verified 2026-08-23), then `stats vorp --season
  2026`. Until then `players.parquet`'s live `injury_status` tags are the only
  current availability feed.
- Watch Hunt/Ertz FA signings: if either lands somewhere, re-run
  `sleeper players sync` + `wiki sync-frontmatter` so they stop being silently
  dropped by `filter_rostered`.
