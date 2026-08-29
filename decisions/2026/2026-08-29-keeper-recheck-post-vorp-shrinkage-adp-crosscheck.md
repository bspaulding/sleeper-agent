---
date: '2026-08-29'
kind: keeper
season: '2026'
week: null
status: confirmed
players_involved:
  - Stefon Diggs
  - Quinshon Judkins
  - TreVeyon Henderson
  - Sam Darnold
related_wiki:
  - wiki/team/keeper-strategy.md
  - wiki/league/projected-keepers-2026.md
---

## Summary

Re-ran the full keeper-surplus analysis per the `keepers` skill's explicit rule ("re-run after
any VORP/bigboard data fix, even after locking picks in Sleeper") after today's bigboard passes
(VORP-shrinkage-by-position-reliability, the 602-flag resolution, the top-250 news sweep, and two
demotion passes) regenerated both `data/vorp/2025.parquet` and `data/bigboard/2025.csv` since the
2026-08-28 keeper lock. User confirmed mid-analysis that the keeper deadline has been **extended
to draft time** (today, 2026-08-29, 3pm PT), so this was a live, actionable recheck, not a
retrospective one.

**Recommendation: no change.** Keep **Stefon Diggs (R7)** and **Quinshon Judkins (R8)** — the
picks already locked in Sleeper. TreVeyon Henderson briefly looked like a mechanical upset
(highest raw surplus on the roster) but fails a real-ADP cross-check added by this analysis; see
below.

## Reasoning

**Recomputed round baselines** (current `data/bigboard/2025.csv` rank order, joined back to
`data/vorp/2025.parquet`'s **raw** `vorp_season` — not the new `vorp_season_shrunk` column, which
is scoped to the ordinal board's cross-position sort only and would double-discount QBs if used
here):

| Round | Baseline (2026-08-28) | Baseline (now, 2026-08-29) |
|---|---|---|
| R3 | 73.1 | **27.6** |
| R7 | 14.6 | **17.7** |
| R8 | 7.0 | **-8.5** |
| R14 | -49.5 | **-35.8** |

R3's baseline collapsed mainly because two hand-pinned elite QBs (Lamar Jackson, Joe Burrow) now
sit in that rank band on potential/situation despite deeply negative raw 2025 production (injury-
shortened seasons) — a real, if unusual, effect of this session's QB-reliability and demotion
review passes, not a bug (spot-checked the actual picks-25-36 roster: Josh Jacobs 103.4, Henderson
71.5, Kyle Pitts 63.5, Nico Collins 55.0, Josh Allen 91.7, **Lamar Jackson -61.1, Joe Burrow
-146.5**, Davante Adams 50.7, Tony Pollard 53.1, Breece Hall 74.0, Michael Wilson 48.4, Garrett
Wilson -72.7).

**Fresh `draft keepers --me --season 2026` + recomputed surplus:**

| Player | Cost | VORP | Surplus | Verdict |
|---|---|---|---|---|
| TreVeyon Henderson | R3 | 71.5 | **+43.9** | Rejected — see ADP cross-check |
| Kareem Hunt | R13 | 10.7 | +44.5 | Rejected — signed to KC practice squad 2026-08-27 (Pacheco IR), no real role |
| Quinshon Judkins | R8 | 34.1 | +42.6 | **Keep** |
| Stefon Diggs | R7 | 38.1 | +20.4 | **Keep** |
| NE Patriots DEF | R14 | -6.0 | +29.8 | Rejected — own VORP negative, baseline artifact |
| Emanuel Wilson | R15 | -41.2 | +13.7 | Rejected — deeply negative absolute production |
| Sam Darnold | R14 | -30.5 | +5.3 | Rejected — near-zero, and negative absolute production |
| Bo Nix | R5 | 31.9 | -6.5 | Rejected — negative surplus now (flipped from prior positive) |
| Zach Ertz | R11 | -20.9 | -1.1 | Rejected — still unsigned FA (confirmed fresh today) |
| Rome Odunze, Jayden Higgins, Dont'e Thornton, Calvin Ridley, George Kittle | various | all negative | — | Rejected — negative surplus and negative absolute production |

**Why Henderson is a rejected near-miss, not a keeper, despite the biggest surplus number.**
This is a new check this analysis added, not previously in the `keepers` skill: cross-referencing
the *internal* board-baseline surplus against **real external ADP**, since the internal round
baseline (our own VORP-sorted board) can diverge sharply from where the market actually drafts a
player.

- Henderson's keeper cost is **R3** (last drafted/kept R4, rookie year). His real 2026 market ADP
  (DraftKings Best Ball) is **pick 66.9 — Round 6**, and Rhamondre Stevenson is *ahead* of him on
  that same ADP board (64.5) per fresh reporting that the Patriots plan roughly a 50/50 committee
  split. Keeping him at R3 cost means paying **three rounds above his real market price** — the
  opposite of a keeper bargain, even though our own VORP model likes his 2025 per-touch production
  more than the market does.
- Our team's draft slot is 8 of 12. Natural R6 pick (even round): `6*12 - 8 + 1 = 65`. Henderson's
  ADP (66.9) sits *right next to* that pick — a real chance he's simply available for us to draft
  normally at 65 without spending a keeper slot at all. Spending an R3 keeper slot to lock in a
  player the market says we can likely get 3 rounds later is a bad trade even if our model is
  right that he's undervalued — being right about undervaluation is an argument to *draft* him
  cheap, not to *keep* him expensive.
- Cross-checked the two actual keepers the same way, as a sanity check on the method itself, not
  just on Henderson:
  - **Judkins**: keeper cost R8 vs. real ADP **5.03 (~pick 50-53)** — a genuine ~35-40 pick
    discount. Confirms the internal-surplus signal; strongest keeper on the roster by both
    methods.
  - **Diggs**: keeper cost R7 vs. real ADP **7.08 (~pick 79)** — cost ≈ market almost exactly.
    Our team's natural R7 pick (odd round): `(7-1)*12 + 8 = 80` — one slot *after* his ADP,
    meaning there's real risk another team takes him right before our turn if he's not kept. No
    keeper-cost arbitrage here (per `wiki/team/keeper-strategy.md`'s existing "cost ≈ market ⇒
    surplus ≈ 0" rule, this alone would be a wash), but the internal model still rates him well
    above the average real R7-quality producer (38.1 vs. baseline 17.7), and keeping him removes
    the coin-flip risk of losing him one pick before our own turn for zero cost (his keeper cost
    isn't a premium over market, unlike Henderson's). Net: keep, on lock-in value, not discount
    value.
- Kareem Hunt's high raw surplus is a similar false positive for a different reason: he was signed
  to the Chiefs' **practice squad** on 2026-08-27 (Pacheco to IR) — not the active roster. His
  10.7 VORP reflects last year's real (backup) production, but a practice-squad player has no
  active-roster path to weekly value; excluded same as the 2026-08-23 decision's original call,
  now on firmer footing.

**Judkins injury re-check (fresh, 2026-08-29):** minor "nagging" issue, back at full practice
Monday, Browns HC Todd Monken confirms nothing serious — consistent with the 2026-08-28 resolution,
no new concern.

## Data

- `draft keepers --me --season 2026`, run 2026-08-29 against `data/vorp/2025.parquet`
  (post-shrinkage, `schema_version=2`).
- Round baselines: raw `vorp_season` from `data/vorp/2025.parquet` joined to
  `data/bigboard/2025.csv` current rank order (not the board's own `vorp` column, which now stores
  `vorp_season_shrunk` per
  `decisions/2026/2026-08-29-bigboard-vorp-shrinkage-by-position-reliability.md` — using that
  column directly for baselines would inconsistently compare a QB-discounted, cross-position
  metric against candidates' raw keeper VORP).
- Fresh web search 2026-08-29: Kareem Hunt (KC practice squad signing, Pacheco IR), Zach Ertz
  (still unsigned FA), Quinshon Judkins (minor/resolved practice injury), TreVeyon Henderson /
  Rhamondre Stevenson committee split and DraftKings Best Ball ADP, Quinshon Judkins ADP
  (FantasyPros, 5.03), Stefon Diggs ADP (7.08).
- `wiki/players/12529-treveyon-henderson.md`, `wiki/players/4098-kareem-hunt.md`,
  `wiki/players/1339-zach-ertz.md`.

## Outcome

No change made in Sleeper — Diggs (R7) and Judkins (R8) remain the correct picks, now validated
against both the updated internal VORP board and real external ADP. Added a new cross-check step
(internal surplus vs. real ADP) to `.claude/skills/keepers.md` and refreshed the round-baseline
table in `wiki/team/keeper-strategy.md`, since the internal-board baseline swung hard enough this
session (R3: 73.1 → 27.6) that a future large swing could produce another Henderson-shaped false
positive without this check.
