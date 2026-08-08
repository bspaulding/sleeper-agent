---
date: '2026-08-08'
kind: draft
season: '2026'
week: null
status: recommended
players_involved: []
related_wiki:
  - league/season-2026.md
---

## Summary

Brad (commissioner-adjacent, relaying the league's schedule change) moved the 2026 draft up one
week from the dates recorded in `decisions/2026/2026-08-04-draft-2026-league-launch-dates.md`:
draft is now **Saturday, August 29, 2026, afternoon (exact time still TBD)**, and the keeper
deadline moves with it to the night before, **Friday, August 28, 2026**, Sleeper-enforced as
before. `wiki/league/season-2026.md` has been updated in place to the new dates since it's the
live quick-reference; the original 2026-08-04 decision entry is left as-is since it's a record of
that day's commissioner email, not a doc to rewrite.

## Reasoning

No rule changes accompany this — it's purely the whole calendar sliding seven days earlier
("same deal as before, just seven days earlier"). Everything downstream that was timed off the
original Sept 4/5/7 dates needs to shift by the same seven days:

- Keeper selection (`draft keepers`) now needs to be finalized before **Friday Aug 28**, not
  Sept 4 — Sleeper enforces this deadline directly with no grace period, per the original
  decision entry.
- The two scheduled Routines tied to these dates were updated to match:
  - `sleeper-agent: pre-draft prep` (one-shot) moved from 2026-09-02 13:00 UTC to
    **2026-08-26 13:00 UTC**, and its prompt's date references (keeper deadline, draft date,
    "Sept 4-5" mock-draft reminder) updated to the new dates.
  - `sleeper-agent: draft day` (one-shot) moved from 2026-09-05 17:00 UTC to
    **2026-08-29 17:00 UTC** (same ~1pm ET placeholder time — still TBD per the email), and its
    prompt's date references updated to the new draft/backup dates.
- Backup date (previously Monday Sept 7 / Labor Day) shifts the same seven days to **Monday,
  August 31**, per "same deal as before."
- The pre-draft prep window shrinks accordingly (today, Aug 8, to Aug 28/29 is about three weeks
  instead of four) — worth flagging in the next mock-draft/research push, but not a blocker.

## Data

- **Draft:** Saturday, August 29, 2026, afternoon (exact time still TBD). Backup: Monday,
  August 31 (Labor Day), if enough owners object to Saturday.
- **Keeper deadline:** Friday, August 28, 2026 (the night before the draft), Sleeper-enforced.
- **NFL week 1 opener:** unchanged, Wednesday, Sept 9, 2026.
- **Keeper rules:** unchanged — see the 2026-08-04 decision entry and
  `wiki/league/season-2026.md` for the full rules, still matching this project's existing
  `keeper_history` implementation.
- **Rule/league changes:** none, same as the original launch email.

## Outcome

Pending. `wiki/league/season-2026.md` and the two draft-adjacent Routines
(`sleeper-agent: pre-draft prep`, `sleeper-agent: draft day`) have been updated to the new dates
as part of this decision. `IMPLEMENTATION_PLAN.md` still references the original Sept 4/5/7 dates
in its narrative/checklist sections and should be swept to match on a future pass.
