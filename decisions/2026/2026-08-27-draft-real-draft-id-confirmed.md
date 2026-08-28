---
date: '2026-08-27'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - Stefon Diggs
  - Sam Darnold
  - Chris Olave
  - Christian Watson
  - Romeo Doubs
  - Rico Dowdle
  - George Pickens
  - Blake Corum
  - Kenneth Walker III
  - Jonathan Taylor
  - Zay Flowers
  - Rashee Rice
  - Javonte Williams
related_wiki:
  - wiki/league/season-2026.md
---

## Summary

User supplied the real 2026 "Only Gold" draft's Sleeper ID (`1389376972722835457`) for
confirmation ahead of Saturday. Fetched `GET /v1/draft/1389376972722835457` directly and
cross-checked it against everything already on file — it matches the ID already cited in
[[2026-08-23-keeper-diggs-r7-darnold-r14]] and the confirmed-time entry in
`wiki/league/season-2026.md` (`f973f70`), with no discrepancies.

## Reasoning

Confirmed via direct API fetch, not assumption:

- `league_id: 1389376972722835456` — matches the "Only Gold" league this project already
  operates against.
- `status: pre_draft`, `type: snake`, `settings.teams: 12`, `scoring_type: ppr`,
  `settings.rounds: 15` — all consistent with prior decisions.
- `start_time` (epoch) resolves to **2026-08-29 15:00:21 PT** — matches the "3:00pm PT" already
  recorded in `wiki/league/season-2026.md` on 2026-08-27 (`f973f70`), now cross-verified straight
  from the draft object rather than secondhand.
- `slot_to_roster_id["8"] = 5` — confirms our draft slot (8) maps to `roster_id 5`, matching the
  `ME_ROSTER_ID = 5` constant already hardcoded in `cli/src/sleeper_agent/commands/draft_cmd.py`.
- `settings.cpu_autopick: 0` — unlike the practice mock draft
  ([[2026-08-27-draft-mock-draft-4-slot8]]), a missed real pick will **not** auto-resolve. Worth
  keeping the pick clock front-of-mind Saturday; 60s pick timer, 60s nomination timer,
  autopause window 300-1020s.
- `last_picked: null`, no `/picks` returned yet — the Diggs/Darnold keeper picks aren't visible
  via the API yet either, consistent with the keeper decision's note that keeper picks don't
  surface until close to draft night. Worth a re-check closer to Saturday rather than assuming
  they're seeded.

No new information changed anything — this was a verification pass, not a correction.

## Data

- `GET https://api.sleeper.app/v1/draft/1389376972722835457` (fetched 2026-08-27).
- Cross-referenced against `decisions/2026/2026-08-23-keeper-diggs-r7-darnold-r14.md` and
  `wiki/league/season-2026.md`.

## Outcome

Confirmed, no changes needed to existing docs — the real draft ID, start time, and our
roster/slot mapping were already correct on file. Recording this pass so the confirmation itself
(and the cpu_autopick-off / not-yet-seeded-keepers flags) is on the record ahead of Saturday.

## Update 2026-08-27 (later same day) — 13 of 24 league keepers visible in draftroom UI

User shared a screenshot of the draftroom's "Keepers to Set" panel (UI-only — still not on the
`/picks` API per the not-yet-seeded note above). 13 of a possible 24 (12 teams × 2) are locked
league-wide:

| Player | Pos | Team |
|---|---|---|
| Chris Olave | WR | NO |
| Christian Watson | WR | GB |
| Romeo Doubs | WR | NE |
| Rico Dowdle | RB | PIT |
| George Pickens | WR | DAL |
| Stefon Diggs | WR | WAS |
| Sam Darnold | QB | SEA |
| Blake Corum | RB | LAR |
| Kenneth Walker III | RB | KC |
| Jonathan Taylor | RB | IND |
| Zay Flowers | WR | BAL |
| Rashee Rice | WR | KC |
| J. Williams | RB | DAL |

Diggs and Darnold are our own two ([[2026-08-23-keeper-diggs-r7-darnold-r14]]), so 11 belong to
other teams. Two cross-checks against this project's own role-changer tracking held up: Doubs
(GB→NE) and Kenneth Walker III (SEA→KC) both already carry `[MOVED: ...]` tags on the big board,
independently confirming those detections were right.

"J. Williams RB - DAL" is Javonte Williams (sleeper_id 7588, vorp 109.1, `team=DAL` for all 17
weeks of the 2025 season per `data/stats/weekly/2025.parquet`) — his 109.1 vorp is trustworthy
as-is.

**No tooling action needed for the keepers themselves** — `draft board --league-id` already
excludes `is_keeper` picks straight from the live feed once Sleeper seeds them (see
`--exclude-players`'s help text in `draft_cmd.py`), same as it will for our own Diggs/Darnold
picks. This list is scouting context, not something to hardcode.

**Worth carrying into Saturday's approach:** 7 of the 13 known keepers are WR (vs. 5 RB, 1 QB).
None of the 4 practice mock drafts this month ([[2026-08-27-draft-mock-draft-4-slot8]] and prior)
modeled any keepers — Sleeper mocks have no keeper data of their own, hence
`--exclude-players` only ever dropped *our* two. That means every mock rehearsed a fuller WR pool
than Saturday will actually have; expect the real WR board to run thinner/faster in the opening
rounds than the mocks suggested, and don't be surprised if a WR run starts earlier live than it
did in practice.
