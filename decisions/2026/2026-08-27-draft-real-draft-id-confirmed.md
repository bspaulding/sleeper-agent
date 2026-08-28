---
date: '2026-08-27'
kind: draft
season: '2026'
week: null
status: recommended
players_involved: []
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
