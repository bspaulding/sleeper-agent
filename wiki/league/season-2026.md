---
season: '2026'
last_updated: '2026-08-08'
source: decisions/2026/2026-08-08-draft-draft-2026-schedule-moved-up-week.md
---

# 2026 season — key dates

Quick-reference for this league's ("Only Gold") 2026 calendar. Originally set by the
commissioner's league-launch email (2026-08-04), then moved up one week
(2026-08-08 — see `decisions/2026/2026-08-08-draft-draft-2026-schedule-moved-up-week.md`). See
the linked decision entries for full reasoning and the verbatim keeper-rule confirmation.

- **NFL week 1 opener:** Wednesday, Sept 9, 2026 — first Wednesday opener since 2012, which is
  why the draft moved to Labor Day weekend instead of the usual late-August weekday evening.
- **Draft:** Saturday, August 29, 2026, afternoon (exact time still TBD as of this writing).
  Backup date: Monday, August 31 (Labor Day), used only if enough owners object to Saturday.
- **Keeper deadline:** Friday, August 28, 2026 — the night before the draft, enforced directly by
  Sleeper.
- **Rule/league changes for 2026:** none.
- **Draft order:** Sleeper-randomized in the app.

## Keeper rules (unchanged from prior seasons)

- Keep up to 2 players from the final 2025 roster.
- Each keeper is auto-drafted one round earlier than last year's draft slot.
- No keeping 1st-rounders.
- Max 2 consecutive years on a kept player, then they return to the open pool.
- Keeper status doesn't transfer in trades — new team, new draft rank.

This matches what `sleeper_client/draft.py`'s `keeper_history` already computes
(`cost = last_round - 1`, `KeeperIneligibleCostBelowRoundOne` at cost 0,
`KeeperIneligibleMaxYearsReached` after 2 consecutive kept seasons) — no code change was needed
for the rules themselves.

## Prep plan before the deadline/draft

- Run `draft keepers --me --season 2026` well before Aug 28 to settle the 2 keeper picks (see
  `.claude/skills/draft.md`).
- Do at least one or two Sleeper mock drafts before Aug 28-29 to rehearse tiers/pacing — run
  `draft board --draft-id <mock-draft-id> --value-season 2026 --watch` alongside a mock draft
  room for a live best-available-by-value view (mock drafts have no league to resolve
  `--league-id` against, hence the direct `--draft-id` path).
- Keep news-research passes (`.claude/skills/news-research.md`) going on rostered/likely-keeper
  players in the run-up, since keeper value calls should reflect current camp/depth-chart news,
  not just last season's VORP.
