---
date: '2026-08-29'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Breece Hall
  - RJ Harvey
  - Woody Marks
  - Kyle Monangai
  - Tyrone Tracy Jr.
  - Chuba Hubbard
  - Zach Charbonnet
  - Aaron Jones
  - Tyjae Spears
  - Devin Singletary
  - Tucker Kraft
  - Bryce Young
  - Sam LaPorta
  - Xavier Worthy
related_wiki:
  - wiki/team/draft-strategy.md
  - wiki/players/8155-breece-hall.md
  - wiki/players/12489-rj-harvey.md
  - wiki/players/9508-tyjae-spears.md
---

## Summary

Follow-up to [[2026-08-29-bigboard-legal-availability-risk-demotions]]: that entry closed the
gap on the two specific players already flagged in the mock-draft-8 retro, but left "systematic
re-scan of the other researched players for missed downside signals" as an open item. This
entry closes that: a read-only re-audit of all 175 remaining researched players (top-250 sweep
minus the 10 already actioned) for downside signal not yet reflected in rank, followed by a
targeted demotion pass on the highest-impact findings.

## Reasoning

The re-audit surfaced 35 flags total across the 175 players scanned. Most were "mild" (a
minor/resolved injury, a role note already implied by the existing rank, contract uncertainty
years out) and don't warrant a rank change — moving a player for noise would be as much a mistake
as ignoring a real signal. Applied demotions only to the ones with concrete, material, and
currently-unreflected downside:

- **Zach Charbonnet** (was 107, vorp 30.6 → 138): the clearest miss in the whole scan — vorp
  showed a healthy committee-lead RB despite a torn ACL, PUP placement, and Week 1 availability
  explicitly "in doubt."
- **Breece Hall** (25→34) and **Kyle Monangai** (85→107): both real, dated, multi-week injury
  timelines (groin / hyperextended knee) close enough to the season to matter.
- **RJ Harvey** (26→40) and **Woody Marks** (90→105): both currently listed behind another back
  on their team's actual depth chart (J.K. Dobbins; David Montgomery via trade) — rank had them
  priced closer to a lead role than the depth chart supports.
- **Tyrone Tracy Jr.** (69→109): real roster-spot jeopardy (preseason miscues, Najee Harris
  signed, passed by Singletary) — independently corroborates the same finding from our own
  mock-draft-8 retro ([[2026-08-29-draft-mock-draft-8-slot8]]).
- **Chuba Hubbard** (119→136), **Aaron Jones** (125→142), **Tyjae Spears** (139→151), **Devin
  Singletary** (142→160): each has either an explicit "losing the job" statement from reporting
  or a specific missed-time injury window.
- **Tucker Kraft** (148→162) and **Sam LaPorta** (161→174): both ACL/back-surgery recoveries
  with real, dated availability uncertainty behind a TE1-level vorp.
- **Bryce Young** (149→164): speculative but from a named, checkable source ("among QBs most
  likely to lose their starting job in 2026") — kept modest given QB's already-low reliability
  discount per `wiki/team/draft-strategy.md`.
- **Xavier Worthy** (198→214): real injury history plus outside analyst skepticism, kept small
  since he was already fairly low-ranked.

**Deliberately not actioned**, despite a real flag, because the draft-relevance is too low for a
few ranks either way to matter: Bam Knight, Samaje Perine, Elic Ayomanor, Marvin Mims Jr.,
Ollie Gordon II, Devin Neal, Darius Slayton, Mike Gesicki, Tommy Tremble, KaVontae Turpin,
Ja'Tavion Sanders, Audric Estimé (all 160+ and mostly 190+) — noted here for completeness rather
than moved.

**Deliberately not actioned as too mild/already-priced-in**: Jaylen Warren, Lamar Jackson
(team-context only), Rhamondre Stevenson, Juwan Johnson, Jayden Daniels (Daniels himself is
healthy — the flag was about his LT), Justin Jefferson, Emeka Egbuka, Jalen Hurts, Brock Purdy,
Troy Franklin, Khalil Shakir, Oronde Gadsden II, Josh Downs, Kimani Vidal, Evan Engram, Jerry
Jeudy, David Njoku, Mack Hollins, Brashard Smith, J.J. McCarthy (already appropriately low).

## Data

- Full flag list: see the 5 read-only audit agent reports from this session (batches covering
  ranks 1-33, 53-107, 109-163, 164-208, 209-251 of the top-250 sweep).
- `data/bigboard/2025.csv`: 14 rows removed from their old position and reinserted at the ranks
  above, all rows shifted accordingly, renumbered strictly 1..622 (verified via read-only
  `csv.DictReader` check).
- `log_ref` set to this entry's slug on all 14 rows.

## Outcome

14 demotions applied, board still 622 rows / strict 1..622. The other 21 flagged players were
deliberately left alone (see Reasoning) — this is not a claim that every flagged player was
acted on, just that the ones moved are the ones where it plausibly changes a real draft
decision.
