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
- Next practice mock draft against this league: pass `--exclude-players`
  with **all** confirmed real keepers, not just our own (Diggs 2449, Judkins
  12512) — the other 15 are listed in
  `wiki/league/projected-keepers-2026.md`'s confirmed table (Drake Maye
  11564, Bhayshul Tuten 12490, Kenneth Walker III 8151, Blake Corum 11586,
  Luther Burden III 12519, Tucker Kraft 9484, Javonte Williams 7588, Rashee
  Rice 10229, Jonathan Taylor 6813, Zay Flowers 9997, Chris Olave 8144,
  Christian Watson 8167, George Pickens 8137, Rico Dowdle 7021, Romeo Doubs
  8121 pending the roster-9 eligibility ruling). Sleeper's mock room has no
  knowledge of these, so leaving them in skews the mock's pick order and
  inflates how good QB "value" reaches (e.g. Burrow, Stafford) look relative
  to the real draft. See
  `decisions/2026/2026-08-29-draft-mock-draft-6-slot8.md` point (b).
