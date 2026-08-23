# Project TODO

## Keeper decision — deadline Friday, Aug 28

Run `draft keepers --me --season 2026`, make the ≤2 keeper call, log it with
`decisions new --kind keeper`. Context that should feed the call:
`wiki/team/defense-strategy.md` (draft-day plan), the 2026-08-22 injury sweep
(`wiki/news-sources.md` checkpoint), and the fact that Kareem Hunt and Zach Ertz
are **unsigned FAs** as of Aug 23 — two of the 15 roster spots are dead pending
their signings or our drops.

## Before the draft (Saturday, Aug 29)

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

- Sync `stats --season 2026` once nflverse starts publishing weekly files
  (currently 404 pre-season — verified 2026-08-23), then `stats vorp --season
  2026`. Until then `players.parquet`'s live `injury_status` tags are the only
  current availability feed.
- Watch Hunt/Ertz FA signings: if either lands somewhere, re-run
  `sleeper players sync` + `wiki sync-frontmatter` so they stop being silently
  dropped by `filter_rostered`.
