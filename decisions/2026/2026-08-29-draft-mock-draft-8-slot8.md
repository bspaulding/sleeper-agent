---
date: '2026-08-29'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - De'Von Achane
  - Trey McBride
  - Kyren Williams
  - Zay Flowers
  - Michael Wilson
  - Matthew Stafford
  - RJ Harvey
  - Rhamondre Stevenson
  - Dallas Goedert
  - Juwan Johnson
  - Troy Franklin
  - Tyrone Tracy
  - Dalton Schultz
  - Tre Tucker
  - Los Angeles Chargers (DEF)
related_wiki:
  - wiki/team/draft-strategy.md
  - wiki/players/10232-michael-wilson.md
  - wiki/players/12489-rj-harvey.md
  - wiki/players/5022-dallas-goedert.md
  - wiki/players/7002-juwan-johnson.md
  - wiki/players/11655-tyrone-tracy.md
---

## Summary

Mock draft `1399438544077860864` ("Only Gold"), slot 8, 12 teams, PPR, 15 rounds, snake.
`--value-season` defaulted to 2025. Run live via `.claude/skills/draft.md`'s watcher, no
`--exclude-players` (per the settled rule in
[[2026-08-29-draft-mock-draft-7-slot8]] point (c) — mocks never filter keepers). Final roster
(draft order):

1. (R1 P8) De'Von Achane — RB
2. (R2 P17) Trey McBride — TE
3. (R3 P32) Kyren Williams — RB
4. (R4 P41) Zay Flowers — WR
5. (R5 P56) Michael Wilson — WR
6. (R6 P65) Matthew Stafford — QB
7. (R7 P80) RJ Harvey — RB
8. (R8 P89) Rhamondre Stevenson — RB
9. (R9 P104) Dallas Goedert — TE
10. (R10 P113) Juwan Johnson — TE
11. (R11 P128) Troy Franklin — WR
12. (R12 P137) Tyrone Tracy — RB
13. (R13 P152) Dalton Schultz — TE
14. (R14 P161) Tre Tucker — WR
15. (R15 P176) Los Angeles Chargers — DEF

Composition: 1 QB, 5 RB, 4 WR, 4 TE, 1 DEF.

## Reasoning and retro

Mechanical through R10 (top NEED row, then top-overall fallback once all starters filled at R7).
One live correction at R11: the top-overall fallback surfaced Hunter Henry (would-be 4th TE);
user pushed back ("over WR?") — WR bench sat at 0 (Franklin's predecessor pick hadn't happened
yet) while TE was already 3 deep, so switched to Troy Franklin (WR) instead. Post-draft, user
asked for a full retro against sourced rankings — every pick checked against `data/bigboard/
2025.csv` (our own VORP rank) and `data/adp/2026-08-28.parquet` (DraftSharks consensus ADP),
defended or condemned on the gap between the two.

- **TE stacking, quantified.** McBride (R2, +4 picks vs ADP) was a fair elite-tier take, but
  Goedert (R9, +19), Juwan Johnson (R10, **+73**), and Schultz (R13, +40) each reached hard past
  external consensus — averaging +44 picks ahead of market for TE2–TE4. The top-overall fallback
  has no depth-aware discount for a position already stacked with surplus, only a discount for
  filled starter slots — so it kept re-surfacing TE at full VORP value with no penalty for the
  3rd/4th copy. Juwan Johnson at R10 is the sharpest evidence: +73 picks is not "our model rates
  him a bit higher," it's the fallback logic breaking down.
- **Stafford (R6, QB) was the single biggest reach: +31 picks vs ADP.** Filled the last open
  starter slot via the mechanical "top NEED row" rule, but per `draft.md`'s own research, QB has
  the worst year-over-year VORP reliability of the four core positions (r≈0.40 vs 0.67–0.71) — the
  slot was worth filling, but not at a 31-pick premium when a same-tier-ish QB was very likely
  available 1–2 rounds later. Worth a NEED-vs-cost sanity check for QB specifically, not just
  "top NEED row, no further thought."
- **Michael Wilson (R5, WR, +27 vs ADP) — flagged, not resolved.** Our own bigboard also rates him
  well above market (rank 36 vs. ADP 83 / pos-ADP WR36), so this isn't purely a fallback-logic
  bug like the TE picks — but see the research-gap finding below: nobody has ever actually
  verified this number against real news.
- **Franklin (R11, WR, +157 vs ADP) — defend despite the raw number.** This was the corrected
  pick: roster-construction-driven (0 bench WR at the time), not a value claim. Reach vs. ADP is
  the wrong lens for a need-driven bench pick.
- **Research-gap finding, new this run.** Checked `wiki stale` against the picks that showed the
  largest bigboard-vs-ADP divergence: Michael Wilson, RJ Harvey, Dallas Goedert, Juwan Johnson,
  and Tyrone Tracy all have `last_researched: never` (stub pages, no news check ever run), and
  Rhamondre Stevenson and Dalton Schultz have **no wiki page at all**. These are exactly the
  players whose high VORP rank is doing the most work to justify reaching past market ADP — and
  none of it has been sanity-checked against real news/depth-chart/injury signal. This is a more
  concrete, actionable gap than "the board seems to overrate some guys": before trusting these
  ranks in the real draft, run news research on this set.

## Data

- Draft ID `1399438544077860864`, `--value-season 2025` (default), `--draft-slot 8`,
  `--num-teams 12` (matches `settings.teams`), no `--exclude-players` (mocks never filter
  keepers, per [[2026-08-29-draft-mock-draft-7-slot8]] point (c)).
- Live tracking: single `Monitor` wrapping `draft board --notify-my-turn`, piped through `tee`
  then `grep -E "YOUR TURN|Traceback|Error"` — no tool defects this run.
- Confirmed final roster via `GET /v1/draft/<id>/picks`, filtered on `draft_slot == 8`.
- Every pick cross-checked against `data/bigboard/2025.csv` (rank/vorp) and
  `data/adp/2026-08-28.parquet` (adp_pick/ds_rank/pos_adp) to compute reach/value vs. both our
  own model and external consensus.
- `uv run sleeper-agent wiki stale` cross-referenced against the picked-player list to find the
  research-gap set (Wilson, Harvey, Goedert, Johnson, Tracy — never researched; Stevenson,
  Schultz — no page).

## Outcome

`draft.md` updated with a quantified TE depth-cap threshold (generalizing the existing QB-cap
example with a real number from this run, rather than "use judgment"). Research gap on the 7
flagged players logged here as a follow-up, not yet executed — pending user go-ahead on which to
prioritize before the real draft.
