---
date: '2026-08-23'
kind: keeper
season: '2026'
week: null
status: executed
players_involved:
  - Stefon Diggs
  - Sam Darnold
related_wiki:
  - wiki/team/keeper-strategy.md
  - wiki/team/role-changers.md
  - wiki/league/season-2026.md
---

## Summary

Keepers locked in Sleeper on 2026-08-23, ahead of the Aug 28 deadline:
**Stefon Diggs at cost R7** and **Sam Darnold at cost R14**. Draft slot
confirmed as 8 of 12 (`slot_to_roster_id` on the 2026 draft object
`1389376972722835457`). Method note: this decision used a keeper-*surplus*
framework (player VORP minus the expected value of the cost-round pick) rather
than `draft keepers`' value-per-cost ranking — see
`wiki/team/keeper-strategy.md` for the standing method.

## Reasoning

Round baselines from the 2025 VORP board (12-team snake): R3=83.1, R5=33.2,
R7=14.1, R8=2.2, R14=-62.9.

- **Diggs (R7):** vorp 62.3 vs baseline 14.1 = **+48.2** surplus. Role-changer
  caveat evaluated explicitly (NE → WAS via one-year deal): confirmed starting
  slot role next to Daniels in a thin target economy; production profile
  (99/1123/5 on an 81% catch rate) is slot-possession shaped and ages
  gracefully. Keep holds unless output transfers below roughly a quarter of
  prior production. Watch-items: preseason ramp (missed entire offseason
  program), any WAS WR addition before the draft.
- **Darnold (R14):** FA pickup, so cost follows the clarified ADP-reset rule
  (resets to current ADP − 1; commissioner Aaron's reference:
  draftsharks.com/adp/ppr/sleeper/12 — Darnold at pick #174 ≈ R15 market).
  Vorp 7.0 vs baseline −62.9 = **+69.9** surplus. Converts the last pick into
  a guaranteed-startable QB and solves the QB room for near-zero opportunity
  cost, preserving the planned Drake Maye selection at R3.
- **Rejected:** Henderson (R3, −2.3 — paying exactly market price AND burning
  the Maye pick; re-draftable at market), Nix (R5, +13.0 — thin edge, and the
  Aug 19 trade chip; see below), Judkins (R8, +25.3 — real alternative to
  Darnold but loses to free QB insurance; ankle recovery variance), Kittle
  (R1, −207.0 — 33yo PUP off an Achilles tear), Ridley (R4, −182.0),
  Higgins (R9 — torn ACL, out for season; drop candidate), Ertz/Wilson/
  Thornton/Hunt — negative or unsigned-FA noise.

Trade evaluation folded in: the `2026-08-19-trade-bo-nix-trade-scouting-qb-
surplus.md` Nix-for-A.J.-Brown recommendation is **superseded/dropped**. Under
the clarified ADP-reset rule, traded players' keeper costs reset to ADP − 1 as
well, so acquiring Brown meant paying ~R2–3 full retail for 46.8 VORP while
spending both Nix and the Diggs discount slot — dominated on every axis before
even considering its low (~20–35%) acceptance odds in a league with zero
trades in its synced history.

Rule clarification recorded (Brad, per commissioner Aaron): **keeper status
for traded players and FA pickups resets to the player's ADP (then −1)**,
reference `draftsharks.com/adp/ppr/sleeper/12`. This supersedes the CLI's
`KeeperEligibleUndraftedDefault` R15 fallback (todo.md tracks replacing it
with a DraftSharks lookup). Flagged for the record: Tyrone Tracy was kept at
pick 180 in the real 2025 draft, which does not match this rule — possible
owner error or policy drift; noted, not blocking.

## Data

- `draft keepers --me --season 2026` (eligibility + last-drafted rounds;
  validated against all 17 real 2025 keeper picks in Phase E).
- Round baselines: 2025 VORP board sorted descending, mapped to 12-team snake
  pick slots (computed 2026-08-23; table preserved in
  `wiki/team/keeper-strategy.md`).
- DraftSharks Sleeper/PPR/12-team ADP page (Aaron's reference): Darnold
  pick #174, QB21 (retrieved 2026-08-23).
- Diggs 2025 line (nflverse weekly): 99 rec / 1,123 yds / 5 TD on 122 tgts,
  21 games with NE, 11.5 PPG full-PPR.
- WAS target economy scan: McLaurin (roster 7) is the only other WAS pass
  catcher rostered league-wide.

## Outcome

Executed — keepers set in Sleeper by Brad on 2026-08-23. Note: keeper picks do
not appear on the draft object's `/picks` endpoint until close to draft night,
so API-side confirmation of the `is_keeper` flags wasn't possible at log time;
re-check when the draft goes live (or at the Aug 29 rehearsal).
