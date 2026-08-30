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

## Process follow-ups (from 2026-08-30 post-draft ADP comparison)

See `decisions/2026/2026-08-30-draft-adp-market-comparison-post-draft-review.md` for the full
pick-by-pick review this came out of.

- Add an explicit "held out of all preseason game action as a precaution" (or equivalent
  team-sourced caution signal) as a hard downgrade flag in the `bigboard` skill's review pass —
  Daniel Jones (R10, our single biggest reach, -89 vs. ADP) was flagged in our own rationale as a
  conservative/modest bump, yet the specific signal that the team itself was hedging (zero
  preseason snaps despite "looking sharp" in practice) wasn't weighted as its own downgrade
  trigger. Currently this kind of signal only gets caught if a human happens to reread the news
  and connects it; it should be a named check.
- Add a standing rule (`draft.md` and/or `bigboard.md`) to treat a bigboard row's own
  "defer to ADP"/"no wiki news on file" annotation as a hard stop against overriding it live at
  the table. Keenan Allen (R12, -58 vs. ADP) is the clearest failure: the board's own rationale
  said to defer fully to the ADP signal given the size of the gap, and we reached anyway with no
  new information to justify it.
- When a cited news source itself contains a caveat that undercuts the pick's thesis (e.g. Juwan
  Johnson's own beat report warning about more multi-TE sets diluting his target share), that
  caveat needs to actually move the bigboard placement, not just get quoted in the rationale text
  underneath an unchanged rank.
- Fold "committee backfield taken at bell-cow pricing" into `wiki/team/draft-strategy.md`'s RB
  section as a named, recurring failure mode, not a one-off — D'Andre Swift (R3) and Jaylen Warren
  (R4) both walked into backfields where beat reporters were already live-reporting a real committee
  (Monangai in CHI, Dowdle in PIT under a new HC) at the time of the pick, echoing the original
  mock-draft-1 "8 RB" retro in `wiki/team/roster-philosophy.md`. The signal was available in
  `wiki/players/` before the pick; it just wasn't checked against the pending pick in the moment.
