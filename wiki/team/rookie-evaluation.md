---
last_updated: '2026-08-22'
source: research pass following up on todo.md's "Rookie / new-outlook player research strategy"
---

# Rookie & new-situation player evaluation

Standing reference for evaluating players `stats vorp`/`draft board` structurally can't rank:
rookies with no prior-NFL-season stats, and players whose team/role changed enough via free
agency or trade that last season's stats no longer describe their outlook. Distinct from
`wiki/team/draft-strategy.md` (general VBD/positional-allocation theory for players the tool
*can* rank) and `roster-philosophy.md` (this team's own retrospectives) — this file is the
qualitative-signal counterpart for the players those two are silent on.

## The structural gap, in numbers

`compute_vorp` (`cli/src/sleeper_agent/stats/vorp.py`) only produces a row for a player who
appears in the prior season's nflverse weekly-stats table — there's no explicit exclusion logic
to point at, it's a join that silently omits anyone it has no rows for. Checked directly against
`data/vorp/2025.parquet` and `data/sleeper/players.parquet`: **212 players leaguewide with zero
NFL experience (`years_exp == 0`) and a current NFL roster spot have zero 2025 VORP rows** — 192
of them at QB/RB/WR/TE. This isn't a data-lag problem that resolves itself in a season or two:
next year's incoming rookie class will always be invisible the same way, regardless of how fresh
the stats sync is. (Colston Loveland, the case that originally flagged this gap, has since
resolved himself — he has a full 2025 stat line now that he's a season into the league — but
that's just this year's crop of *last* year's rookies rotating into visibility; the front end of
the pipe is permanently empty.)

Most of those 212 are deep-roster/UDFA names with no realistic fantasy relevance — the practical
problem isn't "research 212 players," it's "have a way to tell which handful are worth the
effort" before spending research time. Draft capital (below) is that filter.

## Draft capital: the strongest single signal

Every position-specific study pulled for this pass agrees on the headline: **where a rookie was
drafted in the NFL draft predicts rookie-year fantasy relevance far better than any college
production metric does.** Footballguys' "Draft Capital Matters" series (141 TEs and comparable
samples at other positions, 2016–2025, 10 seasons) quantifies it by round:

| Position | Round 1 hit rate | Day 2 (rounds 2–3) | Day 3 (rounds 4–7) |
|---|---|---|---|
| **TE** | 81.8% top-24, 54.5% top-12 | 14% top-24, 2/43 top-12 | 4.6% top-24, 0% top-12 |
| **RB** | 71.4% top-24 | comparable to R1 at the **top-36** tier (not top-24) | 1.3% top-24 (of 160 sampled) |
| **QB** | 84% of *all* fantasy-relevant rookie QBs were 1st-rounders | — | 5 of 6 top-12 rookie QB seasons in a decade were 1st-round; Dak Prescott is the lone exception |
| **WR** | 59.4% of *identified breakouts* were 1st-round picks (84% combined with round 2); essentially zero breakouts after round 5 in 14 years (Puka Nacua the lone recent exception) | — | 15% of all rookie WRs (any round) hit top-48, 11.5% hit top-36 |

**Reading this for our purposes:** TE is nearly a hard first-round-or-skip filter — "if they
weren't a first-round pick, you're probably burning a roster spot" per Footballguys' own
conclusion. RB is the most forgiving position (round 2 keeps pace with round 1 at the top-36
tier, and RB rookie *usage* tends to arrive faster than WR/TE rookie usage generally). WR as a
position is more of a slow-burn than the hype around any given rookie WR class usually suggests —
most rookie-year fantasy value at WR still comes from the *first* round specifically. QB capital
matters even more starkly, though it's low-priority for this league specifically (single QB
slot, no superflex — see "Best-ball framing" below).

## Position-specific secondary signals (once draft capital clears the bar)

### WR — Dominator Rating & Breakout Age

- **Dominator Rating** — the percentage of their college team's total yards + TDs a player
  accounted for. Prefer the *career* (multi-season) figure over a single best season — it
  filters out one-year, stacked-supporting-cast flukes.
- **Breakout Age** — the age at which a player first posted a 20%+ single-season dominator
  rating. Younger is the historically stronger signal; a 2025 top-20 fantasy WR retrospective
  found **50% of that top-20 had an elite breakout age of 19 or under** (PFF/Yahoo), and a
  broader breakout-profile study of confirmed rookie/sophomore WR breakouts over 14 years found
  the average successful breakout profile sits at **~22.1 years old, ~pick 39 overall, ~204 lbs,
  peak dominator ~33.9%, breakout age ~19.8**, with **56.3%** of breakouts having broken out in
  college before age 20 and **78%** clearing a 30%+ peak dominator rating (Apex Fantasy Leagues).
- **PFF college receiving grade** — a volume-independent efficiency signal, useful specifically
  as a check against a Dominator Rating inflated by a weak supporting cast ("more mouths to
  feed" elsewhere on the team lowers everyone's dominator share even for a genuinely good
  player).
- No single one of these is a reliable standalone predictor — the consistent advice across
  sources is to triangulate draft capital + dominator/breakout-age + grade, not lean on any one.

### RB — Opportunity Share & receiving role

- **Opportunity Share** — (carries + targets) ÷ team's total offensive touches. Identifies the
  "featured back" independent of efficiency; a rookie with a low opportunity share is a
  committee/handcuff bet regardless of talent.
- **Weighted Opportunity** (Scott Barrett) — discounts carries and upweights targets by each
  touch type's average fantasy-points value; cited as one of the more stable, predictive RB
  metrics precisely because it separates volume from luck-driven efficiency.
- **College target share / receiving involvement** — a back who caught passes in college
  projects more reliably into an NFL passing-down role, which is where standalone weekly fantasy
  value concentrates once early-down work gets shared in a committee.
- Real-world modifiers that matter as much as any single stat: **offensive line quality**
  (Ashton Jeanty's underwhelming 2025 rookie season is attributed largely to poor O-line play
  putting him behind schedule) and **backfield competition** (a rookie walking into a crowded
  committee, e.g. Jonah Coleman behind an established RB1 in Denver, carries a much lower
  opportunity ceiling than the same prospect on a clean depth chart).

### TE — volume thresholds within the round-1 filter

Once the round-1 filter (above) is applied, the studies that separate TE "hits" from "picked but
irrelevant" point at usage thresholds, not efficiency: **100+ targets and 70%+ offensive snap
share** define the handful of genuinely elite rookie TE seasons in the last decade (only ~14
notably productive rookie TEs total, ~5 true difference-makers). Touchdown scoring specifically
lags even for hits — only 5 of those 14 scored 6+ TDs, roughly the threshold for meaningfully
contributing to weekly fantasy points at the position. Two recent exceptions (Sam LaPorta 2023,
Brock Bowers 2024, both round-1 picks who immediately led the position) suggest the position's
historic "always takes a year" reputation may be softening for the very top of the round-1 tier
specifically — not evidence the round-1 filter itself is loosening.

### QB — lowest priority for this league

Rookie QB fantasy relevance is driven almost entirely by rushing floor (a passing-only rookie QB
rarely has standalone value in year one) and, per the table above, is even more concentrated in
round 1 than any other position. Low-priority for this league specifically: a single required QB
slot with no superflex means a QB2 speculative stash competes for a bench spot against RB/WR/TE
depth that has a much higher chance of mattering in-season in a *best-ball* format where there's
no way to actively stream a hot waiver-wire QB into the lineup (see below).

## Best-ball framing for this league

This league is `best_ball: true` (`wiki/team/roster-philosophy.md`'s roster grid) with no
in-season lineup management modeled by this codebase — the same fact `draft-strategy.md` uses to
lean the RB strategy spectrum toward Hero-RB rather than Zero-RB applies here too:

- Best-ball-specific guidance frames rookies as **situational-upside plays**: "opportunity is
  king" for a single redraft season, versus dynasty formats where raw talent has years to pay off
  regardless of Year 1 role. That favors weighting *landing spot / projected role* over a purely
  talent-graded rookie ranking — though the two aren't independent, since draft capital itself is
  partly a bet by the drafting NFL team on that player's role.
- Best-ball's scoring format (every week counts toward the season total, nothing needs to be
  actively started to matter) is specifically forgiving of a rookie's typical slow start — you
  can roster a rookie WR through a quiet first half and still cash the spike weeks once the role
  expands, an asymmetric-upside bet an active-lineup manager can't make as cheaply.
- ADP-timing caveat: rookies get "steamed" (ADP rises fast) once NFL-draft landing spots lock in
  each April — most relevant to *early* offseason best-ball drafts, not our Aug 29 redraft where
  landing spots, camp battles, and preseason usage are already mostly public. Worth remembering
  for next year's *early*-drafting window if this team ever drafts before landing spots are set.

## New-situation veterans (free agency / trade)

No standardized draft-capital-style table exists for this half of the gap — the frameworks here
are qualitative and example-driven rather than backed by a decade of round-by-round hit rates:

- **Vacated opportunity** is the core question: what target share, touch share, or red-zone role
  did a departed player leave behind on the new team (or the old team, for the player who left),
  and does the player in question profile to inherit it? Concrete 2026 examples confirm this
  works both directions — Javonte Williams signed to fill Rico Dowdle's vacated Dallas role and
  finished the season as RB12 on 287 touches; Mike Evans's move to San Francisco was framed
  around clear volume/TD opportunity in a new offense.
- **Scheme fit matters alongside the raw opportunity math** — a scheme change (new OC, new
  play-caller) can matter as much as the target evaluation, since a player inheriting "the WR2
  role" means less if the new offense's passing scheme doesn't feature that role the way the old
  one did.
- Practically: **schedule, and the health/quality of the teammates around the player**, are the
  standard modifiers layered on top of the opportunity read — a clean vacancy can still be a bad
  bet behind a shaky offensive line or an unresolved QB competition.

## Sources

- [Footballguys: Draft Capital Matters — Rookie Tight Ends (2026)](https://www.footballguys.com/article/2026-draft-capital-matters-rookie-tight-ends)
- [Footballguys: Draft Capital Matters — Rookie Wide Receivers (2026)](https://www.footballguys.com/article/2026-draft-capital-matters-rookie-wide-receivers)
- [Footballguys: Draft Capital Matters — Rookie Running Backs (2026)](https://www.footballguys.com/article/2026-draft-capital-matters-rookie-running-backs)
- [Footballguys: Draft Capital Matters — Rookie Quarterbacks (2026)](https://www.footballguys.com/article/2026-draft-capital-matters-quarterbacks)
- [PFF: Predicting Breakout Rookie Wide Receivers Using PFF Grades and Dominator Rating](https://www.pff.com/news/fantasy-football-predicting-breakout-rookie-wide-receivers-using-pff-grades-and-dominator-rating)
- [Apex Fantasy Leagues: What Does a Rookie Wide Receiver Breakout Look Like?](https://apexfantasyleagues.com/what-does-a-rookie-wide-receiver-breakout-look-like/)
- [Yahoo Sports: Using Adjusted Breakout Age to Evaluate 2026 Draft WRs](https://sports.yahoo.com/fantasy/article/using-adjusted-breakout-age-to-help-you-evaluate-wide-receivers-in-the-2026-nfl-draft-for-fantasy-football-150623093.html)
- [PlayerProfiler: Guide to Advanced Stats & Metrics Vol. 1 — Running Backs](https://www.playerprofiler.com/article/playerprofilers-guide-to-advanced-stats-metrics-vol-1-running-backs-draft/)
- [Fantasy Points: Statistically Significant — Weighted Opportunity](https://www.fantasypoints.com/nfl/articles/2024/statistically-significant-weighted-opportunity)
- [RotoWire: 2026 NFL Rookie Rankings — Snap Share & Role Growth Tracker](https://www.rotowire.com/football/article/nfl-rookie-impact-129165)
- [DraftSharks: Best Ball Draft Strategy 2026](https://www.draftsharks.com/kb/best-ball-draft-strategy)
- [FantasyLife: Underdog Best Ball Draft Strategy — Rookie ADPs to Draft or Fade](https://www.fantasylife.com/articles/best-ball/underdog-best-ball-draft-strategy-jordyn-tyson-and-rookie-adps)
- [ESPN: Six Players Who Benefit Most from Vacated Targets and Touches](https://www.espn.com/fantasy/football/story/_/id/49401787/espn-nfl-fantasy-football-advice-players-benefit-vacated-targets)
- [ESPN: Fantasy Guide to Offseason Signings — 2026 Free Agency/Trade Impact](https://www.espn.com/fantasy/football/story/_/id/47899702/nfl-free-agency-2026-fantasy-football-impact-signings-trades-grades)
