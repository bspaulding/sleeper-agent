# Project TODO

## Done

- ~~Keeper decision~~ — Diggs (R7) + Darnold (R14) locked 2026-08-23; see
  `decisions/2026/2026-08-23-keeper-diggs-r7-darnold-r14.md` and
  `wiki/team/keeper-strategy.md`.

## Before the draft (Saturday, Aug 29)

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
