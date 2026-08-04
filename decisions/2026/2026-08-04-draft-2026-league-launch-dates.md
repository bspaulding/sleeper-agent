---
date: '2026-08-04'
kind: draft
season: '2026'
week: null
status: recommended
players_involved: []
related_wiki:
  - league/season-2026.md
---

## Summary

Recorded the real 2026 season dates and confirmed the standing keeper rules from the
commissioner's (Aaron's) league-launch email, sent 2026-08-04 to the "Only Gold" league list.
Recommendation: start mock drafting and pre-draft research now, since there's roughly a four-week
window before the keeper deadline/draft.

## Reasoning

The NFL 2026 opener is a Wednesday (Sept 9) — the first Wednesday kickoff since 2012 — which
pushed the whole league's draft onto Labor Day weekend instead of the usual late-August weekday
evening. That compresses the pre-draft prep window relative to a normal year and moves the draft
itself to a weekend afternoon, both of which matter for how this project's tooling and scheduled
Routines should be timed:

- The live-draft `draft board --watch` Routine (`PROJECT_PLAN.md` §8, `IMPLEMENTATION_PLAN.md`
  §9 Phase H) needs to target a Saturday-afternoon window, not a weekday evening as originally
  assumed when dates were still placeholders.
- Keeper selection (`draft keepers`) needs to be finalized and logged before Friday Sept 4 —
  Sleeper enforces the deadline directly, so there's no grace period for a late decision.
- With real dates now known, this is also the trigger `IMPLEMENTATION_PLAN.md` §0.1 and its
  cross-cutting checklist (§11) were waiting on to close out the "draft-day Routine scheduled"
  and "real dates replace placeholders" items.
- Mock drafting is a manual, interactive exercise in the Sleeper app (bots fill the other slots
  live) — there's no read/write API angle for this project's tooling to automate it — but
  `draft board --draft-id <mock-draft-id> --value-season 2026` (added alongside this decision,
  see `cli/src/sleeper_agent/commands/draft_cmd.py`) now lets it run the same best-available-by-
  value board against a standalone mock draft as it does the real live draft, since a Sleeper mock
  draft has no league object to resolve `--league-id` against. Worth running a couple of mock
  drafts before Sept 4 to rehearse tier breaks/pacing and sanity-check the VORP rankings against
  how a real room actually drafts.

## Data

From Aaron's email, "🏈 2026 Only Gold Assemble - Let's Gooo!" (2026-08-04, 11:28 AM):

- **NFL week 1 opener:** Wednesday, Sept 9, 2026.
- **Draft:** proposed Saturday, Sept 5, 2026, afternoon (exact time TBD). Backup: Monday, Sept 7
  (Labor Day) if enough owners object to Saturday.
- **Keeper deadline:** Friday, Sept 4, 2026 (the night before the draft), Sleeper-enforced.
- **Keeper rules — unchanged, matches this project's existing implementation:**
  - Keep up to 2 players from the final 2025 roster.
  - Each keeper is auto-drafted one round earlier than last year's draft slot
    (`cost = last_round - 1`, confirmed already coded in `sleeper_client/draft.py`).
  - No keeping 1st-rounders (`cost = 0` → `KeeperIneligibleCostBelowRoundOne`, already coded).
  - Max 2 consecutive years on a kept player (`KeeperIneligibleMaxYearsReached`, already coded).
  - Keeper status doesn't transfer in trades — a traded player's keeper rank resets to the new
    team, i.e. keyed by `roster_id` at time of the historical pick, which is how `keeper_history`
    already looks it up.
- **Rule/league changes:** none for 2026.
- **Draft order:** Sleeper-randomized in the app — no fixed order to pull or hardcode.
- Reference links from the email (external, for manual keeper research, not scraped by this
  project per `PROJECT_PLAN.md` §5.4): DraftSharks ADP
  (https://www.draftsharks.com/adp/ppr/sleeper/12) and a bit.ly link to prior years' keeper
  history for context.

No code change was needed for the keeper rule itself — the email confirms the existing
`last_round - 1` / round-0-invalid / max-2-years implementation is still correct for 2026. The
only code change this decision prompted is the `draft board --draft-id` mock-draft support above.

## Outcome

Pending. Draft-day Routine scheduling and mock-draft/research prep runs follow from this entry —
see `wiki/league/season-2026.md` for the quick-reference dates and `IMPLEMENTATION_PLAN.md` §0.1
/ §11 for the checklist items this closes out.
