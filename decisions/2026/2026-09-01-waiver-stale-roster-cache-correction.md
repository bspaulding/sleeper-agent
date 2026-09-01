---
date: '2026-09-01'
kind: waiver
season: '2026'
week: null
status: recommended
players_involved:
  - Sam Darnold
  - Daniel Jones
  - Quinshon Judkins
  - TreVeyon Henderson
  - D'Andre Swift
  - Jaylen Warren
  - Tyrone Tracy
  - Stefon Diggs
  - Jaxon Smith-Njigba
  - Michael Pittman
  - Keenan Allen
  - Denzel Boston
  - Trey McBride
  - Kyle Pitts
  - Juwan Johnson
related_wiki:
  - wiki/league/season-2026.md
  - decisions/2026/2026-08-31-waiver-marshawn-lloyd-jacobs-exempt-list.md
---

## Summary

Asked to do a news sweep and a trade/add-drop analysis, `sleeper roster show --me` returned a
roster (Emanuel Wilson, Bo Nix, Rome Odunze, Jayden Higgins, Quinshon Judkins, TreVeyon Henderson,
Dont'e Thornton, Zach Ertz, Stefon Diggs, Kareem Hunt, George Kittle, Sam Darnold, Calvin Ridley,
Amon-Ra St. Brown) that didn't match the user's expectation. Root cause: `data/sleeper/rosters/
2026.parquet` (and the paired league/drafts/transactions files) was a stale local cache, last
synced Aug 30 — one day after the real Aug 29 draft — and never refreshed since. Re-ran `sleeper
league sync --league-id 1389376972722835456 --season 2026` and independently verified the result
directly against the live Sleeper API (`/v1/league/<id>/rosters` and
`/v1/draft/1389376972722835457/picks`, cross-checked owner_id and draft_slot mapping): roster_id 5
has had **zero transactions ever** — it is exactly the Aug 29 draft result, unmodified. The
Emanuel Wilson/Bo Nix/etc. set was never a real roster; where it came from is unconfirmed (most
likely a leftover snapshot from one of the several slot-8 mock drafts run during draft prep,
never overwritten by a real post-draft sync).

## Reasoning

- The corrected, verified roster: **QB** Sam Darnold, Daniel Jones. **RB** Quinshon Judkins
  (keeper, R8), TreVeyon Henderson, D'Andre Swift, Jaylen Warren, Tyrone Tracy. **WR** Stefon Diggs
  (keeper, R7), Jaxon Smith-Njigba, Michael Pittman, Keenan Allen, Denzel Boston. **TE** Trey
  McBride, Kyle Pitts, Juwan Johnson. This matches the draft pick log pick-for-pick, including both
  confirmed keepers (`wiki/league/season-2026.md`).
- Player wiki pages (`wiki/players/*.md`) themselves needed no correction — they're general
  research, not roster-scoped, and pages already existed for every real-roster player. What was
  wrong was anything that *asserted team composition* built on the stale cache: most notably
  `decisions/2026/2026-08-31-waiver-marshawn-lloyd-jacobs-exempt-list.md`, which recommended a $30
  FAAB claim on the premise that RB was our thinnest position — false against the real roster,
  which has 5 drafted RBs. Corrected in place with an "Update" section rather than deleted, per
  this project's decision-log convention of preserving history.
- No other decision-log entries needed correction: everything else referencing the phantom names
  (mock draft retrospectives, bigboard prep passes) was already correctly scoped as mock-draft or
  pre-draft-board content, not a claim about the real team.
- Added a "Post-draft roster" section to `wiki/league/season-2026.md` as the canonical reference
  point, with a reminder to re-run `sleeper league sync` before trusting `sleeper roster show --me`
  if it's been more than a few days — this bug is otherwise silent (the command errors on nothing,
  it just returns stale data).

## Data

- `GET https://api.sleeper.app/v1/league/1389376972722835456/rosters` (fetched 2026-09-01),
  roster_id 5, `total_moves: 0`.
- `GET https://api.sleeper.app/v1/draft/1389376972722835457/picks`, roster_id 5 picks cross-checked
  1:1 against the live roster's player list.
- `GET https://api.sleeper.app/v1/league/1389376972722835456/transactions/1`: no transactions for
  roster_id 5 in the log.
- `data/sleeper/rosters/2026.parquet` diff (pre- vs. post-sync, via `git show HEAD:...`): confirmed
  the pre-sync file held the phantom roster, not a decoding error on read.

## Outcome

Local Sleeper data re-synced and committed (`c844bda`). `wiki/league/season-2026.md` now carries
the verified post-draft roster. `decisions/2026/2026-08-31-waiver-marshawn-lloyd-jacobs-exempt-list.md`
corrected in place — the $30 Lloyd bid should **not** be submitted on that entry's reasoning.
No other roster-dependent decisions from this period required correction.
