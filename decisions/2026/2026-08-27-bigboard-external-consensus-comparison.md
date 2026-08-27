---
date: '2026-08-27'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Christian McCaffrey
  - Kyren Williams
  - Travis Etienne
  - D'Andre Swift
  - Kyle Pitts
  - Josh Allen
  - Drake Maye
  - Caleb Williams
  - Ja'Marr Chase
  - A.J. Brown
  - DeVonta Smith
  - Nico Collins
  - Colston Loveland
related_wiki:
  - team/bigboard-external-comparison.md
  - team/roster-philosophy.md
---

## Summary

Todo item: "Compare our bigboard/VORP ranking against Sleeper's own rankings and analyze." Sleeper
turns out not to expose a real ranking via its public API — investigated and rejected, then
pivoted to published external consensus rankings instead (Bleacher Report's Top 100 PPR list and
ESPN's Field Yates Top 160 PPR list, both pulled 2026-08-27), compared against
`data/bigboard/2025.csv` (our current pre-draft board, `--value-season 2025`) top 60. Full
condensed writeup lives in `wiki/team/bigboard-external-comparison.md`; this entry is the process
record and the raw data.

## Reasoning

**Why not Sleeper's own ranking.** Sleeper's `/players/nfl` payload (already synced every 24h into
`data/sleeper/players.parquet`) has a `search_rank` field. Empirically pulled and inspected: the
top ~40 by `search_rank` tracks 2026 fantasy consensus closely (Bijan Robinson/Jahmyr Gibbs 1,
Josh Allen 3, etc.), which looked promising at first. But it's contaminated by real-world
name-recognition, not fantasy value — confirmed both by a stale/retired-player artifact in our own
pull (Todd Gurley, retired, `team: None`, `search_rank` 27) and independently via web search (Tom
Brady, retired years ago, has a documented `search_rank` of 24). It's Sleeper's in-app
search/autocomplete relevance ordering, not a fantasy ranking — it only *looks* like one at the
very top because current elite players are also currently famous. Not usable as "Sleeper's
rankings."

**Sources actually used.** Most ranking sites are JS-rendered React apps (FantasyPros, ESPN's
generic overview page, Yahoo, DraftSharks, RotoBaller) — `WebFetch` only sees the page shell/nav,
not the table data, for those. Two sources returned real static numbered lists:
- [Bleacher Report — Top 100 Fantasy Football Rankings for PPR Leagues in 2026](https://bleacherreport.com/articles/25458550-top-100-fantasy-football-rankings-ppr-leagues-2026)
- [ESPN — Field Yates' PPR rankings, Top 160 for 2026](https://www.espn.com/fantasy/football/story/_/id/48711830/2026-fantasy-football-rankings-ppr-field-yates)

Two independent expert sources, not a full "consensus of 100+ experts" aggregate like FantasyPros'
ECR — treat the averaged external rank below as a rough proxy, not a rigorous consensus number.

**Method.** Name-normalized match (lowercased, punctuation stripped, `Jr/Sr/II/III/IV` suffixes
dropped) between our bigboard's top 60 rows and each external list's top 60. Where a player
appears in both, averaged the two external ranks; where only one, used that one; ~20 of our top 60
(mostly committee/deep-bench RBs and older vets) appear in neither external top 60, which is
expected at that range and not itself a data quality signal.

## Data

### Position mix, top 12 (RB-heavy complaint, quantified)

| | RB | WR | TE | QB |
|---|---|---|---|---|
| Our bigboard | 8 | 3 | 1 | 0 |
| Bleacher Report | 5 | 7 | 0 | 0 |
| ESPN (Field Yates) | 7 | 5 | 0 | 0 |

Our board is more RB-heavy than either external list at the very top, but not a wild outlier —
ESPN's own top 12 is itself RB-majority (7). This is real, moderate confirmation of the mock-draft
feedback triage item ("Too many RBs, still!" — ranking issue, not a tagging issue), but the
external data doesn't support that our board is drastically broken on this axis; a moderate
rebalance, not a rewrite, looks like the right scope.

### Biggest mismatches vs. averaged external rank (our top 60)

Positive delta = we rank them lower (behind) than consensus. Negative = we rank them higher
(ahead) than consensus.

| Our rank | Player | Pos | BR | ESPN | Avg ext | Delta | Likely cause |
|---|---|---|---|---|---|---|---|
| 16 | Ja'Marr Chase | WR | 3 | 4 | 3.5 | +12.5 | 2025 counting stats (our VORP input) were suppressed by Joe Burrow's injury absence; consensus prices in a healthy Burrow for 2026 |
| 44 | A.J. Brown | WR | 13 | 26 | 19.5 | +24.5 | Down 2025 season (friction/role), consensus expects bounce-back with a new team situation |
| 54 | DeVonta Smith | WR | 22 | 43 | 32.5 | +21.5 | Same Eagles-offense-share dynamics as A.J. Brown, split differently by outlet |
| 55 | Colston Loveland | TE | 33 | 35 | 34.0 | +21.0 | Rookie-year 2025 sample was thin; consensus is more bullish on his 2026 role |
| 40 | Nico Collins | WR | 12 | 39 | 25.5 | +14.5 | Missed time in 2025 (our VORP is realized-only, so injury games count as zero, not "missed") |
| 1 | Christian McCaffrey | RB | 24 | 3 | 13.5 | -12.5 | Elite when healthy, but an injury-heavy recent track record; retrospective VORP rewards his peak season more than forward-looking risk-adjustment does |
| 9 | Kyren Williams | RB | 36 | 32 | 34.0 | -25.0 | Big realized 2025 season; consensus is skeptical of a repeat (workload/committee risk) |
| 17 | Travis Etienne | RB | 53 | 37 | 45.0 | -28.0 | Same pattern — strong realized 2025 VORP, weaker forward outlook |
| 20 | D'Andre Swift | RB | — | 45 | 45.0 | -25.0 | Realized-stat VORP doesn't see the team/scheme change since last season |
| 35 | Caleb Williams | QB | 59 | — | 59.0 | -24.0 | Same realized-vs-forward gap, QB version |
| 41 | Kyle Pitts | TE | — | 58 | 58.0 | -17.0 | Big realized target-share season; consensus doubts it repeats |
| 15 | Josh Allen | QB | 25 | 28 | 26.5 | -11.5 | See QB pattern below |
| 14 | Drake Maye | QB | 39 | 48 | 43.5 | -29.5 | See QB pattern below |

**QB pattern, called out separately:** every rostered-relevant QB on our board (Allen #15, Maye
#14, Caleb Williams #35) ranks meaningfully ahead of the averaged external rank. This is
consistent across the whole position, not one player — worth checking against the existing todo
item on `compute_replacement_ranks`/`DEFAULT_FLEX_WEIGHTS` (is the QB replacement baseline too low
for a single-QB league?) rather than writing off as noise. Not diagnosed here; flagged for that
investigation.

**Reading across the whole mismatch list:** almost every big divergence is explained by the same
mechanism — our VORP is purely retrospective (realized full-season 2025 stats only), while
published rankings are forward-looking (account for injury recoveries, situation/scheme changes,
QB health, rookie-year growth). This is direct, concrete supporting evidence for the existing todo
item "VORP has no projected-output signal" — it's not a hypothetical gap, these are real players
on our actual bigboard where the gap changes the *rank order that would get drafted*.

### Full raw external snapshots (2026-08-27, top 60 each)

**Bleacher Report (Top 100 PPR, 2026):**
```
1. Jahmyr Gibbs (RB, DET)              21. Saquon Barkley (RB, PHI)         41. Javonte Williams (RB, DAL)
2. Jaxon Smith-Njigba (WR, SEA)        22. DeVonta Smith (WR, PHI)          42. Ladd McConkey (WR, LAC)
3. Ja'Marr Chase (WR, CIN)             23. Brock Bowers (TE, LV)            43. Jeremiyah Love (RB, ARI)
4. Bijan Robinson (RB, ATL)            24. Christian McCaffrey (RB, SF)     44. Terry McLaurin (WR, WAS)
5. Puka Nacua (WR, LAR)                25. Josh Allen (QB, BUF)             45. Malik Nabers (WR, NYG)
6. Justin Jefferson (WR, MIN)          26. Garrett Wilson (WR, NYJ)         46. Davante Adams (WR, LAR)
7. Jonathan Taylor (RB, IND)           27. Chase Brown (RB, CIN)            47. Cam Skattebo (RB, NYG)
8. Amon-Ra St. Brown (WR, DET)         28. Zay Flowers (WR, BAL)            48. Mike Evans (WR, SF)
9. James Cook III (RB, BUF)            29. Rashee Rice (WR, KC)             49. Luther Burden III (WR, CHI)
10. CeeDee Lamb (WR, DAL)              30. Derrick Henry (RB, BAL)          50. Josh Jacobs (RB, GB)
11. De'Von Achane (RB, MIA)            31. Lamar Jackson (QB, BAL)          51. Jameson Williams (WR, DET)
12. Nico Collins (WR, HOU)             32. Joe Burrow (QB, CIN)             52. DJ Moore (WR, BUF)
13. A.J. Brown (WR, NE)                33. Colston Loveland (TE, CHI)       53. Travis Etienne Jr. (RB, NO)
14. Ashton Jeanty (RB, LV)             34. Breece Hall (RB, NYJ)            54. Jalen Hurts (QB, PHI)
15. George Pickens (WR, DAL)           35. Tetairoa McMillan (WR, CAR)      55. Marvin Harrison Jr. (WR, ARI)
16. Emeka Egbuka (WR, TB)              36. Kyren Williams (RB, LAR)         56. David Montgomery (RB, HOU)
17. Trey McBride (TE, ARI)             37. Jaylen Waddle (WR, DEN)          57. Tyler Warren (TE, IND)
18. Omarion Hampton (RB, LAC)          38. Kenneth Walker III (RB, KC)      58. Quinshon Judkins (RB, CLE)
19. Chris Olave (WR, NO)               39. Drake Maye (QB, NE)              59. Caleb Williams (QB, CHI)
20. Drake London (WR, ATL)             40. Tee Higgins (WR, CIN)            60. Carnell Tate (WR, TEN)
```

**ESPN — Field Yates (Top 160 PPR, 2026):**
```
1. Bijan Robinson (RB, ATL)            21. Saquon Barkley (RB, PHI)         41. Zay Flowers (WR, BAL)
2. Jahmyr Gibbs (RB, DET)              22. Josh Jacobs (RB, GB)             42. Tetairoa McMillan (WR, CAR)
3. Christian McCaffrey (RB, SF)        23. Omarion Hampton (RB, LAC)        43. DeVonta Smith (WR, PHI)
4. Ja'Marr Chase (WR, CIN)             24. Ashton Jeanty (RB, LV)           44. Jaylen Waddle (WR, DEN)
5. Puka Nacua (WR, LAR)                25. Malik Nabers (WR, NYG)           45. D'Andre Swift (RB, CHI)
6. Jaxon Smith-Njigba (WR, SEA)        26. A.J. Brown (WR, NE)              46. Tyler Warren (TE, IND)
7. Jonathan Taylor (RB, IND)           27. Chris Olave (WR, NO)             47. Cam Skattebo (RB, NYG)
8. De'Von Achane (RB, MIA)             28. Josh Allen (QB, BUF)             48. Drake Maye (QB, NE)
9. Amon-Ra St. Brown (WR, DET)         29. George Pickens (WR, DAL)         49. Bucky Irving (RB, TB)
10. James Cook III (RB, BUF)           30. Javonte Williams (RB, DAL)       50. Davante Adams (WR, LAR)
11. Derrick Henry (RB, BAL)            31. Breece Hall (RB, NYJ)            51. Ladd McConkey (WR, LAC)
12. Justin Jefferson (WR, MIN)         32. Kyren Williams (RB, LAR)         52. Jalen Hurts (QB, PHI)
13. CeeDee Lamb (WR, DAL)              33. Emeka Egbuka (WR, TB)            53. Harold Fannin Jr. (TE, CLE)
14. Chase Brown (RB, CIN)              34. Garrett Wilson (WR, NYJ)         54. Bhayshul Tuten (RB, JAX)
15. Kenneth Walker III (RB, KC)        35. Colston Loveland (TE, CHI)       55. Chuba Hubbard (RB, CAR)
16. Brock Bowers (TE, LV)              36. Lamar Jackson (QB, BAL)          56. Jadarian Price (RB, SEA)
17. Drake London (WR, ATL)             37. Travis Etienne Jr. (RB, NO)      57. Tee Higgins (WR, CIN)
18. Trey McBride (TE, ARI)             38. Quinshon Judkins (RB, CLE)       58. Kyle Pitts Sr. (TE, ATL)
19. Rashee Rice (WR, KC)               39. Nico Collins (WR, HOU)           59. Justin Herbert (QB, LAC)
20. Jeremiyah Love (RB, ARI)           40. Jayden Daniels (QB, WSH)         60. Terry McLaurin (WR, WSH)
```

## Outcome

No bigboard edits made here — this was scoped as analysis, not a re-ranking pass. Feeds two
existing open todo items rather than closing them:

1. **"Too many RBs, still!"** — quantified: our top 12 runs 8 RB vs. an external range of 5–7.
   Real but moderate; supports a rebalance, not a rewrite.
2. **"VORP has no projected-output signal"** — this comparison surfaced concrete named examples
   (Chase, A.J. Brown, DeVonta Smith, Nico Collins undervalued; McCaffrey, Kyren Williams,
   Etienne, Swift, Pitts, and the QB group overvalued) that make the abstract gap tangible. Still
   scoped as its own follow-up per that todo item, not fixed here.

Also flagged, not yet investigated: the QB-wide overvaluation pattern (Allen/Maye/Caleb Williams
all rank meaningfully ahead of consensus) — worth checking against the VORP replacement-baseline
work already on the todo list before assuming it's the same retrospective-vs-forward gap as
everything else.
