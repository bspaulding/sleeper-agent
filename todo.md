# Project TODO

## In-season

- Sync `stats --season 2026` once nflverse starts publishing weekly files
  (currently 404 pre-season — verified 2026-08-23), then `stats vorp --season
  2026`. Until then `players.parquet`'s live `injury_status` tags are the only
  current availability feed.
- Watch Hunt/Ertz FA signings: if either lands somewhere, re-run
  `sleeper players sync` + `wiki sync-frontmatter` so they stop being silently
  dropped by `filter_rostered`.
- Build a real DEF ranking pass (recent pressure rate / takeaways / other
  real-season signal) so `draft board` can surface DEF rows like every other
  position instead of punting to end-of-draft judgment — user ask from
  `decisions/2026/2026-08-29-draft-mock-draft-7-slot8.md` point (e).
- Settled (2026-08-29): mocks never filter `--exclude-players` for league
  keepers — not all of them, not even our own. Only the real draft accounts
  for keepers. Not codified in `.claude/skills/draft.md` (user preference —
  keep as a decision-log-level rule, not baked into the skill); nothing left
  to do here beyond following it next time. See
  `decisions/2026/2026-08-29-draft-mock-draft-7-slot8.md` point (c).
