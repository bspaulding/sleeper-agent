---
date: '2026-08-30'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - Jaxon Smith-Njigba
  - Trey McBride
  - D'Andre Swift
  - Jaylen Warren
  - TreVeyon Henderson
  - Kyle Pitts
  - Stefon Diggs
  - Quinshon Judkins
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
  - wiki/team/role-changers.md
---

## Summary

Ran a pick-by-pick comparative review of our full 2026 real-draft roster (13 live picks + 2
keepers) against external consensus ADP (`data/adp/2026-08-28.parquet`, draftsharks.com
ppr/sleeper/12), grounded in each player's real coach/scheme/depth-chart/injury context from
`wiki/players/` and `wiki/nfl-teams/` rather than just the raw pick-vs-rank gap. Goal: for every
pick where we drafted meaningfully ahead of the market, determine whether we were right to (real,
sourced information the market was underweighting) or whether the market's skepticism was
better-calibrated than our own read.

## Reasoning

Full pick-by-pick verdicts:

| Pick | Player (pos, team) | Us / Market rank | Gap | Verdict |
|---|---|---|---|---|
| R1 #8 | Jaxon Smith-Njigba (WR, SEA) | 6 / 6 | flat | Agreement — entrenched WR1, record extension, no flags |
| R2 #17 | Trey McBride (TE, ARI) | 21 / 21 | flat | Agreement — clear TE1, monster 2025 finish |
| R3 #32 | D'Andre Swift (RB, CHI) | 55 / 32 | -23 | Market likely right — real committee w/ Monangai, priced last year's box score not this year's shared role |
| R4 #41 | Jaylen Warren (RB, PIT) | 71 / 55 | -30 | Market likely right — new HC McCarthy running a real Dowdle competition, beat reporters calling it a timeshare |
| R5 #56 | TreVeyon Henderson (RB, NE) | 53 / 53 | flat | Agreement — correctly priced as a real committee w/ upside |
| R6 #65 | Kyle Pitts (TE, ATL) | 69 / 69 | flat | Agreement — extension + strong preseason form |
| R7 #80 | Stefon Diggs (WR, WAS)* | 110 / 110 | -30 | Real risk (slow camp return from a lost year), but a locked keeper cost, not a live judgment |
| R8 #89 | Quinshon Judkins (RB, CLE)* | 54 / 54 | +35 | **We're onto something** — cleared injury, real bell-cow role, validates the keeper-swap decision |
| R9 #104 | Michael Pittman (WR, PIT) | 102 / 102 | flat | Agreement — correctly discounted from Colts lead-target role to a 2-man tandem |
| R10 #113 | Daniel Jones (QB, IND) | 202 / 202 | -89 | **Market very likely right** — held out of all preseason action despite "looking sharp"; our own board even called the bump "modest, not elite" |
| R11 #128 | Juwan Johnson (TE, NO) | 186 / 186 | -58 | Market likely right — our own cited source warned of multi-TE volume dilution we didn't weight |
| R12 #137 | Keenan Allen (WR, IND) | 195 / 195 | -58 | **Market very likely right** — role is contingent on two other players staying hurt; our own tool said defer to ADP and we reached anyway |
| R13 #152 | Sam Darnold (QB, SEA) | 175 / 175 | -23 | Mild, defensible — paying a little for a proven, entrenched starter |
| R14 #161 | Tyrone Tracy Jr. (RB, NYG) | 163 / 163 | flat | Agreement — our own news-driven demotion (69→109) already caught the same roster-jeopardy signal |
| R15 #176 | Denzel Boston (WR, CLE) | 165 / 165 | +11 | Mild value — real current reporting (1st-team reps, coach discussing packages), not just draft-capital speculation |

*Keeper — cost locked from prior-season rules, not a live draft-day judgment call.

**Pattern that emerged:**

1. **Real edge shows up in keeper-cost math and news-driven re-scans, not live reach judgment.**
   Judkins (keeper swap) and Tracy (demoted ahead of the pick, not after) are the two clearest
   wins — both cases where the process caught something concrete and current before the market
   forced the issue.
2. **The three biggest reaches (Jones, Allen, Johnson) all share the same failure mode:** a single
   attractive storyline (injury-recovery ceiling, situational reunion, last year's role) was
   allowed to outrun a specific, already-sourced red flag sitting in our own research (held out of
   every preseason snap; a role contingent on two other players staying hurt; a coach's own
   comments about diluting volume with more 2-TE sets). Allen is the starkest case — the
   bigboard's own rationale said "defer fully to the ADP signal given the size of the gap," and we
   reached 58 spots past it anyway.
3. **Two RB picks (Swift, Warren) walked into real, already-reported committee backfields** at
   pricing that assumed a clean bell-cow role. Not disastrous, but a repeat of a shape flagged in
   the very first mock-draft-1 retro (`wiki/team/roster-philosophy.md`) — committee risk still
   isn't getting priced in live, even when the beat reporting is sitting right there in
   `wiki/players/`.

## Data

- `data/adp/2026-08-28.parquet` (draftsharks.com, ppr/sleeper/12) — external rank/gap per pick.
- `data/bigboard/2025.csv` — our own rank, vorp, and hand-written rationale per pick, including
  the role-change/injury-review annotations quoted above.
- `wiki/players/*.md` for all 15 rostered players — coach quotes, depth-chart state, and injury
  status, dated 2026-08-19 through 2026-08-29.
- `wiki/nfl-teams/{ARI,ATL,CHI,CLE,IND,NE,NO,NYG,PIT,SEA,WAS}.md` — coaching staff, scheme, and
  team-level context.

## Outcome

Recommending three follow-up items land in `todo.md` (see that file for the actual entries):
weight a "held out of preseason action" / similarly explicit precaution signal as a hard
downgrade flag in the `bigboard` skill's review pass; add a standing rule to check the bigboard's
own "defer to ADP" annotations before overriding them live at the table; and fold RB
committee-backfield risk (Swift/Warren shape) into `wiki/team/draft-strategy.md`'s RB-strategy
section as a named, recurring failure mode rather than a one-off.
