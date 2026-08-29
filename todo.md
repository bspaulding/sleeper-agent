# Project TODO

## In-season

- Sync `stats --season 2026` once nflverse starts publishing weekly files
  (currently 404 pre-season — verified 2026-08-23), then `stats vorp --season
  2026`. Until then `players.parquet`'s live `injury_status` tags are the only
  current availability feed.
- Watch Hunt/Ertz FA signings: if either lands somewhere, re-run
  `sleeper players sync` + `wiki sync-frontmatter` so they stop being silently
  dropped by `filter_rostered`.
- Next `bigboard` refresh: review every `[MOVED: ...]`-flagged row (team
  changers, `sleeper_agent.value.team_changes`) against
  `wiki/team/role-changers.md`'s vacated-opportunity framework, not just
  injury-flagged rows — and check ranks against `data/adp/*.parquet`
  (DraftSharks) where available. Start with Travis Etienne: board has him
  rank 16 / RB tier 1 (vorp 118.2, from his 2025 Jacksonville workload,
  blank rationale) but DraftSharks' 2026-08-28 ADP has him RB20 / overall 43
  — the board never repriced him for the real 2026 co-RB1 committee with
  Alvin Kamara in New Orleans (`wiki/players/7543-travis-etienne.md`). See
  `decisions/2026/2026-08-29-draft-mock-draft-6-slot8.md` point (a).
