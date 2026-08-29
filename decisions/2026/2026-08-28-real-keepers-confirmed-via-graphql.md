---
date: '2026-08-28'
kind: draft
season: '2026'
week: null
status: open-question
players_involved:
  - Romeo Doubs
related_wiki:
  - wiki/league/projected-keepers-2026.md
  - wiki/league/season-2026.md
---

## Summary

Confirmed all 12 rosters' real submitted keepers a day before the draft, using an API source
this repo hadn't tried before: Sleeper's GraphQL endpoint (`https://sleeper.com/graphql`,
`league_rosters` query), which exposes a `keepers: [player_id]` field per roster. The REST
`/league/{id}/rosters` endpoint this repo already syncs does not include that field — only
`players`/`starters`/`reserve`/`taxi`. The draft object's `/picks` endpoint (what
`sleeper_client/draft.py` polls) is still empty pre-draft (`status: pre_draft`, 0 picks as of
this writing) — keeper picks aren't materialized there until the draft engine actually starts.
So GraphQL's `league_rosters.keepers` is the only source with real keeper data before the draft.

Full comparison against the 2026-08-23 projection is now in
`wiki/league/projected-keepers-2026.md`. Our own locks (roster 5: Diggs R7, Judkins R8) matched
exactly. Six of the other ten rosters swapped at least one keeper vs. what the projection
guessed — expected, since owner judgment isn't fully modeled.

## Open question: Roster 9 kept an ineligible player

Roster 9 (momsrock) submitted **Romeo Doubs** as their (only) keeper. This repo's synced draft
history shows Doubs was `is_keeper=True` in *both* the 2024 and 2025 drafts for that roster —
i.e., already kept 2 consecutive seasons. The league rule
(`wiki/league/season-2026.md`, confirmed by commissioner Aaron): "Max 2 consecutive years on a
kept player, then they return to the open pool." `draft keepers --season 2026 --roster-id 9`
correctly flags this: `ineligible Romeo Doubs   kept 2 consecutive seasons already (max
reached)`.

Sleeper accepted the submission anyway — the app does not enforce this house rule at all; it
only enforces the keeper *deadline* (timing), not keeper *eligibility* (the consecutive-year
limit is tracked manually by this repo/commissioner, not a native Sleeper league setting).
`wiki/league/season-2026.md`'s claim that the deadline is "enforced directly by Sleeper" is
therefore incomplete — worth a wording fix there once this is resolved.

**Not resolved by this entry.** Needs a commissioner ruling before Saturday's draft:
- Reject Doubs, roster 9 enters the draft with 0 keepers (or a replacement if the deadline is
  reopened for them), or
- League treats it as an approved exception and Doubs is kept anyway.

Whichever way this goes, `wiki/league/projected-keepers-2026.md`'s roster 9 row needs a follow-up
edit once the ruling lands.
