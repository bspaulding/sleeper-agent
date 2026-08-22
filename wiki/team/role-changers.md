---
last_updated: '2026-08-22'
source: research pass following up on todo.md's "Rookie / new-outlook player research strategy"
---

# Role changers (free agency & trade)

Standing reference for evaluating veterans whose team or offensive role changed enough via free
agency or trade that last season's stats no longer describe their outlook. Sibling gap to
`wiki/team/rookie-evaluation.md`, but a different failure mode: a rookie is *missing* from
`stats vorp` entirely; a role-changer has a full VORP row, computed correctly from last season's
stats — the row just silently assumes team/role continuity that no longer holds, and nothing in
the pipeline flags when that assumption breaks. Distinct from `wiki/team/draft-strategy.md`
(general VBD theory) and `roster-philosophy.md` (this team's own retrospectives).

## The detection mechanism, confirmed against live data

Unlike rookies (needed a new `nflreadpy.load_draft_picks` pull), this population is detectable
from data **already synced and on disk** — no new data source required:

- `data/stats/weekly/2025.parquet` carries a per-player-week `team` column; the last row per
  player gives their most recent 2025 team.
- `data/sleeper/players.parquet`'s `team` field reflects the current (post-2026-offseason) team.
- Diffing the two, joined via the existing `gsis_id`↔`sleeper_id` crosswalk (`stats/ids.parquet`,
  the same join `compute_vorp` already does), surfaces every team change directly.

**One real gotcha, confirmed by checking every team code on both sides:** nflverse codes the Rams
as `LA`; Sleeper codes them `LAR`. That single mismatch alone produces roughly 150 false
positives in a naive diff — every other team code matches exactly between the two sources, so a
one-entry alias map (`{"LA": "LAR"}`) is sufficient normalization, not a general fuzzy-match
problem.

**Raw count, checked live for the 2026 offseason:** 132 genuine team changes at QB/RB/WR/TE after
normalization. Most of that is roster churn (a fourth-string RB or camp-arm QB bouncing between
practice squads) with no more fantasy relevance than the sub-round-4 rookies `rookie-evaluation.md`
filters out — the same volume problem, needing the same kind of triage.

## Triage: prior-season opportunity as the filter

There's no draft-capital equivalent for this population (nobody re-drafts a veteran), but there is
a comparable proxy already sitting unused in `data/stats/weekly/*.parquet`: **`target_share`,
`air_yards_share`, and `wopr`** columns, present on every row today and currently read by nothing
in the codebase (`compute_vorp` only consumes raw counting stats for the fantasy-points formula).

Filtering the 132 team-changers to those with **≥50 total 2025 touches/targets** (carries +
targets combined — a "had a real role somewhere" floor, not a quality bar) narrows the list to
**36** — Kenneth Walker (SEA→KC), Travis Etienne (JAX→NO), Rico Dowdle (CAR→PIT), David
Montgomery (DET→HOU), and similar, down to fringe cases like John Metchie (NYJ→CAR) at the
threshold's edge. That's roughly the same survival rate as the rookie triage (212→14 there;
132→36 here), just gated on realized opportunity instead of draft investment.

## Evaluating the ones that survive triage

No decade-of-hit-rates table exists for this half of the gap the way it does for rookies — the
frameworks here are qualitative and example-driven:

- **Vacated opportunity** is the core question: what target share, touch share, or red-zone role
  did a departed player leave behind (on the team they left, or that a new signee is stepping
  into), and does the player in question profile to inherit it? 2026 examples confirm this works
  in both directions — Javonte Williams signed to fill Rico Dowdle's vacated Dallas role and
  finished as RB12 on 287 touches; Mike Evans's move to San Francisco was framed around clear
  volume/TD opportunity in a new offense. Since `target_share`/`air_yards_share` are already
  present in synced weekly stats, a **team-level vacated-opportunity aggregate** (sum of departed
  players' shares per team) is computable directly from existing data — a natural v2 enrichment,
  not required for a first pass at just flagging who moved.
- **Scheme continuity matters as much as the raw opportunity math, and specifically this year**:
  21 of 32 NFL teams hired a new offensive coordinator for 2026 — described in coverage as "one of
  the most underpriced edges" in fantasy drafts, because usage patterns anchor to last year's
  play-caller by default and the person calling plays decides who gets schemed open, who eats
  garbage-time volume, and who gets goal-line work. There's no clean data field for "OC changed"
  in anything already synced — this stays a qualitative research note (LLM/news-research territory),
  not something the diff mechanism above can detect on its own.
- **Landing spot alone doesn't guarantee production carries over** — the "buy low" literature is
  explicit that a plausible opportunity has to actually materialize into confirmed volume/role,
  not just look good on paper (Isaiah Likely's move to a more defined role is cited as a clean
  case; other cited moves are explicitly flagged as not working out as hoped). Practically:
  **schedule, and the health/quality of the teammates around the player** (offensive line, the
  starting QB situation) are the standard modifiers layered on top of the opportunity read — a
  clean vacancy can still be a bad bet behind a shaky supporting cast.

## Why this matters for this league specifically

Same best-ball framing as `rookie-evaluation.md`: no in-season lineup management means a
misjudged role-changer costs a full season of a bench/FLEX slot rather than a bad single week, so
getting the "did the opportunity actually materialize" read right before the Aug 29 draft matters
more than it would in an actively-managed league where a bad bet can be cut after a few weeks.

## Sources

- [ESPN: Six Players Who Benefit Most from Vacated Targets and Touches](https://www.espn.com/fantasy/football/story/_/id/49401787/espn-nfl-fantasy-football-advice-players-benefit-vacated-targets)
- [ESPN: Fantasy Guide to Offseason Signings — 2026 Free Agency/Trade Impact](https://www.espn.com/fantasy/football/story/_/id/47899702/nfl-free-agency-2026-fantasy-football-impact-signings-trades-grades)
- [Yahoo Sports: Using Vacated Targets to Identify 2026 WR/TE Value Changes](https://sports.yahoo.com/fantasy/article/fantasy-football-using-vacated-targets-to-identify-wrs-and-tes-who-should-see-an-increase-or-decrease-in-value-for-2026-144632341.html)
- [RotoBaller: Fantasy Football WR Sleepers — Vacated Air Yards and Targets (2026)](https://www.rotoballer.com/fantasy-football-wide-receiver-sleepers-vacated-air-yards-and-targets-2026/1892757)
- [FantasyLife: Offensive Coordinator and Scheme Changes for Fantasy Football 2026](https://www.fantasylife.com/articles/fantasy/offensive-coordinator-and-scheme-changes-for-fantasy-football)
- [RotoWire: 2026 AFC West Coaching/Personnel Changes — Fantasy Impact](https://www.rotowire.com/football/article/afc-west-preview-2026-fantasy-impact-of-coaching-personnel-changes-124758)
- [RotoWire: Fantasy Football Trade Targets — Buy Low, Sell High](https://www.rotowire.com/football/article/fantasy-football-trade-targets-players-to-buy-low-sell-high-99003)
