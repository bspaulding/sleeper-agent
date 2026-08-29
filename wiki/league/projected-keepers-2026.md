---
season: '2026'
last_updated: '2026-08-28'
source: keeper-surplus projection run 2026-08-23; confirmed against real keepers
  2026-08-28 (see decisions/2026/2026-08-28-real-keepers-confirmed-via-graphql.md)
---

# Projected keepers — 2026

**Superseded by confirmed real keepers below (2026-08-28).** Original
best-guess projection kept for reference, computed from `draft keepers`
eligibility/costs + the surplus test (`wiki/team/keeper-strategy.md`) +
owner-judgment priors.

## Confirmed real keepers (2026-08-28)

Pulled from Sleeper's GraphQL API (`league_rosters` query, `keepers` field) —
the draft object's REST `/picks` endpoint is still empty pre-draft (status
`pre_draft`), so this GraphQL field is the only source that has the real
submitted keepers before the draft starts. Costs below are from `draft
keepers --season 2026 --roster-id <N>`, i.e. our own eligibility engine
applied to the actual kept player.

| Roster | Kept | Cost | vs. projection |
|---|---|---|---|
| 1 | Drake Maye, Bhayshul Tuten | R7, R5 (ADP-reset) | Maye ✓; Tuten swapped in for Charbonnet |
| 2 | Kenneth Walker III, Blake Corum | R3, R8 (ADP-reset) | Walker ✓; Corum swapped in for Wan'Dale |
| 3 | Luther Burden III, Tucker Kraft | R4, R5 (both ADP-reset) | Neither projected player kept — full swap from Warren/Harvey |
| 4 | Javonte Williams, Rashee Rice | R8, R6 | Javonte ✓; Rice swapped in for JSN (JSN was still eligible at R1 — owner chose otherwise) |
| 5 (us) | Stefon Diggs, Quinshon Judkins | R7, R8 | ✓ exact match, our own locks |
| 6 | Jonathan Taylor, Zay Flowers | R1, R5 | ✓ exact match |
| 7 | Chris Olave, Christian Watson | R5, R5 (ADP-reset) | Olave ✓; Watson swapped in for Lawrence |
| 8 | George Pickens, Rico Dowdle | R4, R7 (ADP-reset) | Pickens ✓; Dowdle swapped in for Stafford (Dowdle was the "also considered" alt) |
| 9 | Romeo Doubs (only) | — | **⚠️ ineligible — see caveat below.** Neither Cook nor Jennings kept; only 1 keeper submitted |
| 10 | *(none)* | — | Confirmed real pass, not pending |
| 11 | *(none)* | — | Confirmed real pass, not pending |
| 12 | *(none)* | — | Confirmed real pass, not pending |

**⚠️ Roster 9 rules conflict:** Doubs was `is_keeper=True` in both the synced
2024 and 2025 draft picks for roster 9 — this repo's `draft keepers` engine
correctly flags him `ineligible: kept 2 consecutive seasons already (max
reached)` per the league's own rule
(`wiki/league/season-2026.md` — "Max 2 consecutive years on a kept player").
Sleeper accepted the submission anyway; the app does not enforce this house
rule, contrary to `wiki/league/season-2026.md`'s claim that the deadline is
"enforced directly by Sleeper." **This needs a commissioner ruling before the
draft** — either Doubs returns to the open pool (roster 9 enters the draft
with 0 or 1 keeper) or the league treats this as an approved exception. See
`decisions/2026/2026-08-28-real-keepers-confirmed-via-graphql.md`.

---

## Original projection (2026-08-23), for reference

Refresh after the Aug 28 lock and verify against the draft object's
`is_keeper` picks before trusting it on draft day.

Our own locks (executed 2026-08-28): Diggs R7, Judkins R8 — revised
(`decisions/2026/2026-08-28-keeper-swap-darnold-to-judkins.md`) from the original Diggs R7 /
Darnold R14 executed 2026-08-23, after a VORP-data fix changed Darnold's value from +7.0 to
−30.5.

**Scope note:** this whole table was computed 2026-08-23, before the 2026-08-27 postseason-VORP
fix (`decisions/2026/2026-08-27-bigboard-season-type-postseason-fix.md`) that prompted our own
revision above. Other rosters' rows haven't been re-run against the corrected VORP data and may
have shifted the same way ours did — treat rows 1–4 and 6–12 as stale until re-run, not as
confirmed.

| Roster | Projected keeps | Also considered | Notes |
|---|---|---|---|
| 1 | Drake Maye (R7), Zach Charbonnet (R6) | Pollard R4, Henry R12 | Maye is near-certain (+125 surplus); Nico Collins/Bijan ineligible |
| 2 | Kenneth Walker III (R3), Wan'Dale Robinson (FA→ADP−1) | Corum, Johnston | KWalker obvious; FA cost depends on ADP lookup |
| 3 | Jaylen Warren (R6), RJ Harvey (R4) | Michael Wilson (FA) | **A.J. Brown likely released to pool** (R2 cost too rich) |
| 4 | Javonte Williams (R8), Jaxon Smith-Njigba (R1) | Montgomery R3, Egbuka (FA) | Javonte +100 surplus; CeeDee Lamb ineligible |
| 5 | **Diggs (R7), Judkins (R8)** | Darnold (R14) | revised 2026-08-28, see decision log |
| 6 | Jonathan Taylor (R1), Zay Flowers (R5) | Fannin Jr. (FA, TE) could beat Flowers | Jefferson/Achane ineligible |
| 7 | Trevor Lawrence (FA→ADP−1), Chris Olave (R5) | Caleb Williams R6 close third | Lawrence was a waiver add with 77.9 vorp — ADP rule makes him a steal |
| 8 | Matthew Stafford (FA→ADP−1), George Pickens (R4) | Rico Dowdle (FA) | Stafford +90–150 surplus under ADP rule; Gibbs ineligible |
| 9 | James Cook (R2), Jauan Jennings (R6) | weak board otherwise | Doubs/Bigsby maxed out |
| 10 | Kenny Gainwell (FA→ADP−1), Kyle Pitts (R9) | Ferguson R10 | Gainwell 88.6 vorp as an FA add is the league's biggest ADP-rule windfall |
| 11 | D'Andre Swift (R4), Keenan Allen (R11) | Goff R7, Shaheed R10 | Jacobs ineligible |
| 12 | Travis Etienne (R6), Courtland Sutton (R4) | Tyler Warren R7, Rachaad White R11 | Barkley ineligible |

## What this means for our draft board

~24 players come off the pool. Consequences to internalize before Saturday:

- **Drake Maye is probably gone** (roster 1's keep). The "Maye at R3" mock
  plan needs a new QB target — or a trade for one.
- **The early rounds are refilled with superstars**: CMC, Bijan, Chase, Lamb,
  Barkley, Jefferson, Gibbs, Nacua, McBride, Achane, Kyren Williams are all
  ineligible and re-enter at market price. Early-round value will be stronger
  than a normal startup draft; expect aggressive runs.
- **A.J. Brown, if released**, becomes a legitimate use of an early pick.
- FA-add windsfalls (Stafford, Lawrence, Gainwell, Wan'Dale) mean several
  good players stay off the pool despite being cheap keeps for *their*
  owners.
