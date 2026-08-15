---
date: '2026-08-09'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - Saquon Barkley
  - Derrick Henry
  - Lamar Jackson
  - Colston Loveland
  - Mike Evans
  - Joe Mixon
  - Alvin Kamara
  - James Conner
  - Aaron Jones
  - Baker Mayfield
  - Najee Harris
  - Jonnu Smith
  - Zach Ertz
  - Kareem Hunt
  - Jerry Jeudy
related_wiki:
  - team/roster-philosophy.md
---

## Summary

First rehearsal mock draft ahead of the real 2026 draft (Sat Aug 29). Ran against Sleeper mock
draft `1392286240727908352` (12 teams, 15 rounds, `best_ball: true`, no K, single DEF), drafting
from slot 8, using `sleeper-agent draft board --draft-id 1392286240727908352 --value-season
2024 [--watch]`.

**Data-currency caveat, applies to every pick below:** `--value-season 2024` was used throughout
because `stats sync --season 2025` fails. **Correction to what was believed at draft time:** this
was first diagnosed in-session as nflverse simply not having published 2025 data yet (based on a
404 against `player_stats_2025.parquet`). That diagnosis was wrong, caught while preparing to push
this entry by cross-referencing two automated maintenance commits already on `origin/main`
(`fd2e5ed`, 2026-08-10) that had independently found the real cause: nflverse renamed its release
from `player_stats` to `stats_player` months ago, and `stats_player_week_2025.parquet` exists and
is fetchable right now — confirmed directly against the GitHub API while fixing this doc. The
installed `nfl_data_py` (0.3.3) simply hardcodes the old, now-abandoned release name in
`fetch_weekly_stats`/`import_weekly_data`, so the sync fails even though the data is available.
This is a pipeline bug, not a data-publishing lag, and it's fixable (bump `nfl_data_py` or patch
the URL) rather than something to wait out. (A *third*, different explanation — "session-level
GitHub network restriction" — appears in a separate automated commit, `0d4af83`, 2026-08-11; that
doesn't match this session's own experience of unrestricted GitHub/API access, so it's likely
specific to that other session's sandbox rather than a general cause. Worth reconciling directly
in the CLI issue tracker rather than trusting any one drive-by diagnosis.)

Regardless of cause, every VORP number and "best available" ranking in this draft was priced off
**2024 season performance**, not 2025. This has two concrete consequences documented below and
analyzed further in `wiki/team/roster-philosophy.md`: 2025-rookie players are entirely invisible
to the tool (zero rows in `data/vorp/2024.parquet`), and players who changed/lost NFL roster
status after the 2024 season aren't flagged.

Final roster (slot 8, all 15 rounds, confirmed against the draft's public picks endpoint):

| Rd | Pick | Player | Pos | In-chat? |
|----|------|--------|-----|----------|
| 1 | 8 | Saquon Barkley | RB | yes |
| 2 | 17 | Derrick Henry | RB | yes |
| 3 | 32 | Lamar Jackson | QB | yes |
| 4 | 41 | Colston Loveland | TE | **no** |
| 5 | 56 | Mike Evans | WR | **no** |
| 6 | 65 | Joe Mixon | RB | yes |
| 7 | 80 | Alvin Kamara | RB | yes |
| 8 | 89 | James Conner | RB | yes |
| 9 | 104 | Aaron Jones | RB | yes |
| 10 | 113 | Baker Mayfield | QB | yes |
| 11 | 128 | Najee Harris | RB | yes |
| 12 | 137 | Jonnu Smith | TE | yes |
| 13 | 152 | Zach Ertz | TE | yes |
| 14 | 161 | Kareem Hunt | RB | yes |
| 15 | 176 | Jerry Jeudy | WR | yes |

Position totals: **2 QB, 8 RB, 2 WR, 3 TE, 0 DEF** against a starting requirement of
`QB, RB, RB, WR, WR, TE, FLEX, FLEX, DEF` + 6 bench. See `wiki/team/roster-philosophy.md` for the
full analysis of why that split happened and what to change.

## Reasoning — round by round

Reconstructed from this session's chat log plus the draft's public picks endpoint
(`GET /v1/draft/1392286240727908352/picks`), which is the authoritative source for what was
actually drafted; the chat log records what board state and recommendation I gave at each
checkpoint. The two didn't always align in real time (see Rounds 4–5 and the "stale refresh"
note), so times/order below follow pick number, not chat message order.

- **Round 1 (pick 8) — Saquon Barkley, RB, vorp 322.7.** First refresh showed Barkley well clear
  of the field (#2 Jahmyr Gibbs at 257.4). Recommended and taken.
- **Round 2 (pick 17) — Derrick Henry, RB, vorp 248.4.** Gibbs, Chase, Bijan Robinson, Barkley
  himself all gone by this refresh; Henry led the next tier over James Cook (190.3). Recommended
  and taken.
- **Round 3 (pick 32) — Lamar Jackson, QB, vorp 182.5.** RB1 tier (Henry, Cook, Jacobs, Kyren
  Williams) fully drained; Jackson's VORP lead over Josh Allen (146.2) was called out explicitly
  as reflecting real positional scarcity, not a "reached for a QB" mistake, since VORP is already
  replacement-level-normalized per position. Recommended and taken.
- **Round 4 (pick 41) — Colston Loveland, TE — no chat interaction.** No board refresh or
  recommendation happened for this pick in this session at all; the next chat message after Round
  3 jumped straight to a refresh that (per the picks endpoint) actually reflected a point in time
  *after* Round 6. Loveland does not appear in `data/vorp/2024.parquet` (2025-rookie TE, zero 2024
  stats), so even a timely refresh would not have surfaced him as a `draft board` recommendation —
  the tool is structurally blind to him regardless of response speed.
- **Round 5 (pick 56) — Mike Evans, WR — no chat interaction.** Also not reviewed live. Evans
  *does* have 2024 VORP (69.4) but was well outside the top of the board at that moment —
  reconstructing the true available list as of pick 56 shows Joe Mixon (142.4), Jayden Daniels
  (138.1), Alvin Kamara (131.3), Jalen Hurts (122.5), James Conner (120.8), Aaron Jones (119.6),
  Chuba Hubbard (110.6), and Baker Mayfield (100.4) were all still on the board and higher-value
  than Evans by this tool's own ranking. Joe Mixon in particular sat on the board through both
  Rounds 4 and 5 before finally being drafted here in Round 6 — the two skipped rounds cost real
  value by the tool's own metric, not just roster-construction quality.
- **Between rounds 3 and 6, chat also hit a genuine stale-data incident**: two consecutive
  refreshes ("we're up again refresh") returned an *identical* board (still showing Lamar Jackson
  at #1) even though picks had continued in the live draft. This is what prompted "you need to
  refresh now i am running out of time" / "you were too slow, don't do that again." A background
  investigation via a direct `curl` against the raw Sleeper picks endpoint was started to root-cause
  this but interrupted by the user for being too slow itself — worth a clean follow-up investigation
  outside of draft-time pressure (see Outcome).
- **Round 6 (pick 65) — Joe Mixon, RB, vorp 142.4.** Recommended and taken once refreshes caught
  up to live state.
- **Round 7 (pick 80) — Alvin Kamara, RB, vorp 131.3.** Mixon and the two QBs (Daniels, Hurts)
  gone. Recommended and taken.
- **Round 8 (pick 89) — James Conner, RB, vorp 120.8.** Kamara gone. Recommended and taken.
- **Round 9 (pick 104) — Aaron Jones, RB, vorp 119.6.** Conner and George Kittle gone. Recommended
  and taken.
- **Round 10 (pick 113) — Baker Mayfield, QB, vorp 100.4.** Aaron Jones and Travis Kelce gone.
  Recommended and taken.
- **Round 11 (pick 128) — Najee Harris, RB, vorp 79.4.** Mayfield and Rachaad White gone.
  Recommended and taken.
- **Round 12 (pick 137) — Jonnu Smith, TE, vorp 76.5.** Najee Harris and Brian Robinson gone.
  Recommended and taken.
- **Round 13 (pick 152) — Zach Ertz, TE, vorp 70.1.** Jonnu Smith and Xavier Worthy/Tyrone Tracy
  gone. Recommended and taken.
- **Round 14 (pick 161) — Kareem Hunt, RB, vorp 49.4.** Ertz and Jauan Jennings gone. Recommended
  and taken.
- **Round 15 (pick 176) — Jerry Jeudy, WR, vorp 47.7.** Kareem Hunt gone. Recommended and taken.
  Draft declared complete after this pick; final best-available board pulled and logged to
  `decisions/2024/2026-08-09-draft-live.md`.

Every recommendation across all 13 in-chat rounds followed the same policy: **take the single
highest-VORP player still on the board, full stop.** No positional-need, bye-week, or
roster-construction weighting was applied at any point, despite `.claude/skills/draft.md`
explicitly calling this out as "draft-day judgment the tool can't automate." That's the core
finding carried into the retrospective.

## Data

**Roster requirement** (`data/sleeper/league/2026.parquet`, `roster_positions`):
`QB, RB, RB, WR, WR, TE, FLEX, FLEX, DEF, BN×6` — 15 slots, no kicker, single DEF, `best_ball:
true`.

**Drafted position totals vs. requirement:**

| Position | Drafted | Hard-required starters | Notes |
|---|---|---|---|
| QB | 2 | 1 | fine |
| RB | 8 | 2 (+ up to 2 via FLEX) | large surplus past what FLEX can absorb |
| WR | 2 | 2 (+ up to 2 via FLEX) | exactly meets starters, **zero** bench/bye cushion |
| TE | 3 | 1 (+ up to 2 via FLEX) | reasonable, on the high side |
| DEF | 0 | 1 | **slot cannot be filled at all** |

**Roster-status cross-check** (`data/sleeper/players.parquet`, synced 2026-07-26, cross-verified
against the live draft's own pick `metadata.team` field, which agreed in every case): of the 15
drafted players, 5 show `team: None` / empty despite a `status` of `"Active"` in Sleeper's own
data — **Joe Mixon, Najee Harris, Jonnu Smith, Zach Ertz, Kareem Hunt**. Sleeper's `status` field
does not mean "currently on an NFL roster"; `team` is the actual signal, and `draft board` never
reads it. One-third of this roster is composed of players with no current NFL team on record.

**Rounds with no in-chat review:** 2 of 15 (Rounds 4–5, picks 41 and 56).

**Sources used for this reconstruction:**
- `GET https://api.sleeper.app/v1/draft/1392286240727908352/picks` (authoritative pick log, 180
  total picks across all 12 teams)
- `data/vorp/2024.parquet`
- `data/sleeper/players.parquet` + `players.meta.json` (`fetched_at: 2026-07-26T00:30:49Z`)
- `data/sleeper/league/2026.parquet`

## Outcome

Full retrospective and policy recommendations written to `wiki/team/roster-philosophy.md`,
covering: (1) the two silently-skipped rounds and the stale-refresh incident, (2) the
RB-heavy/WR-light/no-DEF positional imbalance and why the pure-VORP `draft board` policy produces
it, (3) the 2024-vs-2025 data-currency gap and the team-status blind spot, and (4) whether/when to
draft DEF and what "roster construction" should mean under this league's `best_ball: true`
scoring. Fix the `nfl_data_py`/`stats sync` release-name bug (see caveat above) so `stats vorp
--season 2025` can actually run, then do a second mock draft against real 2025 VORP applying
whatever positional-balance rule comes out of that doc, before the real draft on Aug 29.
