---
date: '2026-08-22'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - James Cook
  - Kyren Williams
  - Drake Maye
  - Travis Etienne
  - Stefon Diggs
  - Courtland Sutton
  - Hunter Henry
  - Kenny Gainwell
  - Dallas Goedert
  - Bo Nix
  - New England Patriots (DEF)
  - Zach Charbonnet
  - Dalton Schultz
  - Juwan Johnson
  - Jauan Jennings
related_wiki:
  - wiki/team/roster-philosophy.md
  - wiki/team/draft-strategy.md
---

## Summary

Mock draft `1397000101943062528`, slot 8, 12 teams, 15 rounds, `--value-season 2025`. Full
turn-by-turn recommendations were driven live via a `Monitor`-loop pick tracker (per
`.claude/skills/draft.md`'s preferred live setup) rather than `--watch` directly. Final roster (in
draft order):

1. (R1 P8) James Cook — RB
2. (R2 P17) Kyren Williams — RB
3. (R3 P32) Drake Maye — QB
4. (R4 P41) Travis Etienne — RB
5. (R5 P56) Stefon Diggs — WR
6. (R6 P65) Courtland Sutton — WR
7. (R7 P80) Hunter Henry — TE
8. (R8 P89) Kenny Gainwell — RB
9. (R9 P104) Dallas Goedert — TE
10. (R10 P113) Bo Nix — QB
11. (R11 P128) New England Patriots — DEF
12. (R12 P137) Zach Charbonnet — RB
13. (R13 P152) Dalton Schultz — TE
14. (R14 P161) Juwan Johnson — TE
15. (R15 P176) Jauan Jennings — WR

Composition: 2 QB, 5 RB, 3 WR, 4 TE, 1 DEF — a TE-heavy back half after both true starting slots
(RB, WR) filled by round 6-7.

## Reasoning

- **R1 (Cook):** McCaffrey/Bijan/Gibbs/Chase/Nacua/Taylor/JSN all went ahead of the pick (5 of
  first 7 picks were RB). Cook topped the remaining tier-1 RB cluster (Achane, Kyren) by ~5 VORP
  with a real tier break to tier-2 (Chase Brown, ~40 pts lower) — took the top of a thinning tier
  rather than pivot to TE/WR.
- **R2 (Kyren over McBride):** Both were the last tier-1 anchor at their position with a real
  cliff behind each (RB → Chase Brown/Henry, TE → Kyle Pitts). Kyren's raw VORP was ~28 pts higher
  than McBride's, and RB depth (only 1/2 filled) was thinning faster at that pick — took the
  higher card. McBride was gone one pick later, confirming the cliff was real.
- **R3 (Maye over Etienne-FLEX):** No tradeoff — Maye was both the top raw VORP on the board *and*
  filled the empty QB slot, beating Etienne (FLEX-only once RB hit 2/2) on both counts.
- **R4 (Etienne over Adams-NEED):** Roster sat at 0/2 WR, but neither WR (Adams, tier-1) nor RB
  (Etienne, best FLEX) showed a cliff at that pick, and this is a best-ball format (whole roster
  scores toward the weekly best lineup, no start/sit cost) — took the ~55-VORP-point edge on
  Etienne over reflexively filling the WR tag. Flagged the WR run risk explicitly; it continued
  (4 WRs gone in the following 8 picks).
- **R5 (Diggs over Stevenson-FLEX):** WR urgency became real — tier-1 WR had collapsed to just
  Diggs/Sutton after the round-4 WR run, with a cliff to tier-2 (Michael Wilson, ~20 pts lower)
  right behind. Took Diggs despite Stevenson's higher raw number, since RB was already
  well-covered (3 rostered vs. 2 slots).
- **R6 (Sutton):** Last tier-1 WR, as anticipated in R5 — TE (Pitts/Henry/Goedert) still had no
  comparable cliff, so it could wait another round without losing tier.
- **R7 (Henry over Stevenson-FLEX):** TE was the last true zero-filled starting need (RB/WR both
  covered) — took the top TE (Henry, effectively tied with Goedert at 41.4) rather than add a 4th
  RB.
- **R8 onward — all mandatory slots filled except DEF:** Pure best-value/FLEX depth
  (Gainwell, noting the MOVED tag [PIT→TB] likely overstates his 2026 role behind an entrenched
  Bucky Irving; Goedert as a 2nd quality TE).
- **R10 (Bo Nix over pure VORP-rank):** Applied the `roster-philosophy.md` bye-week-insurance
  reasoning *on the first pass* (this was the exact judgment call a prior mock — 2026-08-22 mock
  #2 — got wrong by undervaluing it): with only 1 QB rostered (Maye) and a mandatory
  no-alternate-eligible QB slot, a bye week with no backup scores zero. Nix also happened to be
  the single highest raw VORP on the board, so no value was given up either.
- **R11 (DEF, urgency-driven):** DEF isn't modeled in this tool's VORP board at all (out of
  scope), and 3 units were already gone. Recommended taking one on pure "mandatory slot, thinning
  supply" grounds since the tool has no way to rank remaining defenses; user picked New England
  directly.
- **R12-R15:** Pure best-player-available once every mandatory/starting slot (QB, 2×RB, 2×WR, TE,
  DEF) was filled — Charbonnet, Schultz, Johnson, Jennings in descending raw VORP order.

## Data

- Draft ID `1397000101943062528`, `--value-season 2025`, `--draft-slot 8`, `--num-teams 12`
  (default), `--rounds 15`.
- Pre-draft sync run: `stats draft-picks sync --season 2026` (257 rows), `wiki scaffold rookies
  --season 2026` (0 new, 14 existing), `wiki scaffold role-changers --season 2025` (1 new, 37
  existing), `wiki sync-frontmatter` (0 updated, 197 unchanged).
- Live tracking used a custom `Monitor`-tool bash loop (1s poll against
  `https://api.sleeper.app/v1/draft/<id>/picks`) rather than `draft board --watch`, per the
  skill's "fold the fetch into the detection event" guidance — computed snake order locally
  (round/slot math) to detect "next pick is mine" and fetched `draft board --draft-slot 8`
  inline in the same loop iteration. No stale-board or missed-round incidents this run.

## Outcome

**Retro note (user-flagged, 2026-08-22):** Zach Charbonnet (R12 pick) is on **PUP**
(Physically Unable to Perform) — not caught or weighed during the pick itself, since the value
board has no injury/availability signal beyond the researched-news lines shown for
rookies/role-changers, and Charbonnet's PUP status surfaced only after the pick was made. Worth
checking PUP/injury status explicitly for RB/WR depth picks in rounds 10+ going forward, rather
than trusting raw VORP alone at that stage of the draft.

## Follow-up resolution (2026-08-23)

The retro's "check PUP/injury status explicitly for RB/WR depth picks in rounds
10+" concern is now structurally addressed: `draft board` and `value rank`
render live Sleeper `[INJ: ...]` tags (commit c09f72b, same day), so an
available player's Questionable/IR/PUP designation is visible at pick time
without a manual check. Charbonnet's own PUP status was also caught in the
2026-08-22 news sweep (`wiki/players/11435-emanuel-wilson.md` covers his
Seahawks backfield; his page carries the PUP note).
