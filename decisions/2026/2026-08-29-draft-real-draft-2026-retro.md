---
date: '2026-08-29'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - Stefon Diggs
  - Quinshon Judkins
  - Jaxon Smith-Njigba
  - Trey McBride
  - D'Andre Swift
  - Jaylen Warren
  - Kyle Pitts
  - Michael Pittman
  - Daniel Jones
  - Juwan Johnson
  - Keenan Allen
  - Sam Darnold
  - Tyrone Tracy Jr.
  - Denzel Boston
related_wiki:
  - wiki/team/draft-strategy.md
  - wiki/team/keeper-strategy.md
---

## Summary

Ran the real 2026 "Only Gold" draft (draft_id `1389376972722835457`, league_id
`1389376972722835456`, roster_id 5, slot 8) live via `draft board --notify-my-turn`, watched
through `Monitor`. Final roster (keepers + 13 live picks): QB Daniel Jones/Sam Darnold, RB
Quinshon Judkins (keeper)/D'Andre Swift/Jaylen Warren/Tyrone Tracy Jr., WR Stefon Diggs
(keeper)/Jaxon Smith-Njigba/Michael Pittman/Keenan Allen/Denzel Boston (rookie), TE Trey
McBride/Kyle Pitts/Juwan Johnson, DEF none (deliberate — streaming plan, see below).

## Reasoning

Pick-by-pick logic and live corrections, in order:

- **R1 (JSN), R2 (McBride), R3 (Swift):** straight top-NEED-row picks off the bigboard, no
  deviation.
- **R4: user override, no QB.** Board's top-NEED row was Matthew Stafford (vorp 30.2) with our QB
  slot empty, but user called it too early. Cross-checked against `data/adp/2026-08-28.parquet`
  after the fact: Stafford's real ADP was pick 96, Trevor Lawrence's 100 — we were only at pick
  41, a ~55-pick reach. Took Jaylen Warren (RB, top overall non-QB value) instead. **Lesson
  confirmed for `draft.md`:** the tool's top-NEED-row rule doesn't check real market ADP before
  recommending a position fill; a live ADP cross-check caught what the static bigboard tier gap
  alone didn't flag as clearly. Worth considering an ADP-vs-current-pick gap check as a
  supplementary signal on the QB (and generally any single-starter-slot) NEED row, not just relying
  on tier breaks.
- **R5-R6 (Henderson, Pitts):** value/ADP-informed picks, no incidents.
- **R7-R8:** keepers (Diggs, Judkins) — no live pick, per snake math the tool predicted correctly
  (picks 80/89).
- **R9 (pick 104): QB revisited, correctly this time.** Stafford was still on the board at pick
  104 — right in his real ADP window by then, no longer a reach. Took him over a WR (Michael
  Pittman, also still available) per discussion, then user overrode again mid-turn to prioritize
  WR instead: at that point RB/WR/TE were all past hard_min (roster fully flexed), but WR carried
  zero bench cushion (2/2 exactly) vs. QB, which still had next-tier fallback options (Bo
  Nix/Goff) if Stafford were gone. Took Michael Pittman. **Lesson:** "starter slot empty" (QB) and
  "starter slot technically filled but zero depth" (WR) are both real gaps the current NEED/SURPLUS
  tag doesn't distinguish — NEED only fires on the former. A thin-bench flag (hard_min met but
  zero surplus at the position) might be worth surfacing explicitly alongside NEED/SURPLUS.
- **R10 (Daniel Jones):** Stafford was gone by our next pick; took the board's top NEED row
  (Daniel Jones, hand-curated injury-recovery placement, real vorp -19.4) per the standing rule —
  this is exactly the kind of speculative QB pick `draft.md` already documents extensively.
- **R11: DEF override — declined twice.** Tool recommended overriding to DEF twice (once
  reflexively when the skill board converged, once again after being told to hold) — user held off
  both times ("no DEF yet"), then confirmed explicitly the plan was to stream defenses in-season
  rather than draft one at all, since Sleeper allows starting Week 1 with an empty required slot
  and defenses remain abundant on waivers (only 4-8 of 32 were off the board at any point we
  checked). **Correction landed:** dropped the "DEF must be filled before the draft ends" framing
  entirely — this league's rules don't require it, and the position's own research
  (`wiki/team/draft-strategy.md`'s DEF section) already argues for streaming over rostering.
  `draft.md`'s existing DEF section should probably say this more explicitly: drafting zero
  defenses is a legitimate outcome, not just "defer the pick."
- **R11-R13 (Juwan Johnson → reconsidered instead of Charbonnet → Baker Mayfield → Sam Darnold):**
  two roster-construction corrections in a row, both the same shape: raw top-of-board vorp
  (Zach Charbonnet, PUP-flagged RB) lost to "does this pick have any real path to relevance,"
  given RB was already past FLEX capacity with no bench outlet, while QB had a single, speculative
  starter and zero backup. Same logic then applied to a straight TE-vs.-alternatives question
  (Dalton Schultz, an actual real-life NFL starter, vs. Tracy Jr.) — confirmed the existing TE-cap
  rule holds even when the extra TE is a legitimate starter for his own team: the constraint is
  roster-slot redundancy on *our* team, not the player's real-world role, and vorp already prices
  the real-world role in.
- **R14 (Tracy Jr.):** clean value pick, no incident.
- **R15 (final pick): rookie keeper-flier logic.** With DEF ruled out and Troy Franklin (proven,
  capped-upside WR) as the "safe" value pick, considered the keeper-cost math explicitly
  (`wiki/team/keeper-strategy.md`: keeper cost = last round − 1, so a final-pick rookie becomes an
  R14 keeper next year if he hits) and took a true unproven rookie instead. Cross-checked real
  NFL draft capital via `data/nfl/draft_picks.parquet` for the finalists: Kenyon Sadiq (TE, real
  pick 16 overall, NYJ) ranked ahead of Omar Cooper (WR, real pick 30, also NYJ) on rarity of
  position capital alone, despite the "Jets suck" concern raised live. Sadiq was gone by our
  actual turn; took Denzel Boston (WR, real R1 pick, CLE) instead — his original scouting knock
  (target-competition with teammate KC Concepcion) was moot since Concepcion had already left the
  pool to another team by then.

## Data

- `GET /v1/draft/1389376972722835457` and `/picks`, polled live throughout via `draft board
  --league-id 1389376972722835456 --roster-id 5 --notify-my-turn`.
- `data/adp/2026-08-28.parquet` — used live, twice, to cross-check QB reach concerns (R4, R9)
  against real market ADP rather than just the internal bigboard.
- `data/nfl/draft_picks.parquet` — used live to compare Sadiq vs. Cooper's actual NFL draft
  capital for the R15 keeper-flier call.
- `data/bigboard/2025.csv` — the ranking source throughout; its rookie/hand-curated rows (Daniel
  Jones, Sadiq, Boston, Cooper) held up under live scrutiny without needing in-draft correction.

## Outcome

Draft completed, 15 rounds, no missed picks (`cpu_autopick: 0` never triggered). Three real
process gaps surfaced for future drafts, captured above for `draft.md`/`draft-strategy.md`
follow-up: (1) the top-NEED-row rule has no live ADP-reach check built in — caught by hand twice
this draft; (2) NEED/SURPLUS doesn't distinguish an empty slot from a full-but-zero-depth slot,
which is a real and different kind of gap; (3) the DEF section's guidance should state "zero
drafted defenses" as a legitimate, not just deferred, outcome. No bigboard ranking itself needed
live correction — the pre-draft judgment calls (Jones, Sadiq, Boston/Cooper ordering) all held.
