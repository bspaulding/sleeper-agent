---
last_updated: '2026-08-27'
source: decisions/2026/2026-08-27-bigboard-season-type-postseason-fix.md
---

# Bigboard vs. external consensus rankings

Answers the todo item "Compare our bigboard/VORP ranking against Sleeper's own rankings and
analyze." Sleeper doesn't actually expose a usable ranking via its public API (see below), so this
compares `data/bigboard/2025.csv` (our current pre-draft board) against two published external
rankings instead. Full raw data and reasoning: the source decision entry above.

## Sleeper's `search_rank` is not a fantasy ranking — don't use it

The `/players/nfl` payload (already synced into `data/sleeper/players.parquet`) has a
`search_rank` field. It looks tempting — the current top ~40 tracks 2026 fantasy consensus closely
— but it's Sleeper's in-app search/autocomplete relevance ordering, contaminated by real-world
name recognition rather than fantasy value. Confirmed two ways: our own pull has Todd Gurley
(retired, `team: None`) ranked 27th, and Tom Brady (retired years ago) is documented at
`search_rank` 24. It only looks like a fantasy ranking at the very top because current elite
players are usually also currently famous.

## Sources used instead

Most public ranking sites are JS-rendered and unreadable to a plain fetch (FantasyPros, ESPN's
overview page, Yahoo, DraftSharks, RotoBaller all returned nav/shell only, not table data). Two
static, byline-authored lists worked, pulled 2026-08-27:

- [Bleacher Report — Top 100 Fantasy Football Rankings for PPR Leagues in 2026](https://bleacherreport.com/articles/25458550-top-100-fantasy-football-rankings-ppr-leagues-2026)
- [ESPN — Field Yates' PPR rankings, Top 160 for 2026](https://www.espn.com/fantasy/football/story/_/id/48711830/2026-fantasy-football-rankings-ppr-field-yates)

This is two independent experts, not a 100+-expert aggregate like FantasyPros' ECR — treat the
averaged rank below as a rough external proxy, not a rigorous consensus number. Full top-60 lists
from both are archived in the source decision entry if this needs re-checking later; re-pull fresh
before relying on it again, these decay fast in-season.

## Finding 1 — the RB-heavy top-of-board complaint, quantified

| | RB | WR | TE | QB |
|---|---|---|---|---|
| Our bigboard, top 12 | 8 | 3 | 1 | 0 |
| Bleacher Report, top 12 | 5 | 7 | 0 | 0 |
| ESPN (Field Yates), top 12 | 7 | 5 | 0 | 0 |

Real, but moderate — ESPN's own top 12 is itself RB-majority (7). This confirms the mock-draft
feedback triage item ("Too many RBs, still!" — a ranking issue, not a tagging issue, per
`todo.md`) with actual numbers, but doesn't support that the board is drastically broken on this
axis. Points toward a moderate rebalance of the replacement baseline
(`stats/vorp.py::compute_replacement_ranks`/`DEFAULT_FLEX_WEIGHTS`), not a rewrite.

## Finding 2 — concrete evidence for the "VORP has no projected-output signal" gap

Our VORP is purely retrospective (realized 2025 stats only, per `stats/vorp.py::compute_vorp`).
Comparing against forward-looking published rankings surfaces the gap in named, specific players
rather than the abstract case already on `todo.md`:

**We rank meaningfully *behind* consensus** (their outlook is better than last season's realized
stats suggest):
- **Ja'Marr Chase** — us #16, consensus avg #3.5. 2025 counting stats were suppressed by Joe
  Burrow's injury absence; consensus prices in a healthy Burrow for 2026.
- **A.J. Brown** (#44 vs. avg #19.5) and **DeVonta Smith** (#54 vs. avg #32.5) — down 2025 season
  in Philadelphia's target split; consensus expects a bounce-back.
- **Nico Collins** (#40 vs. avg #25.5) — missed games in 2025 score as zero in a realized-stats
  VORP, not as "missed time."
- **Colston Loveland** (#55 vs. avg #34.0) — thin rookie-year 2025 sample, consensus more bullish
  on his 2026 role.

**We rank meaningfully *ahead* of consensus** (last season's realized stats look better than the
forward outlook):
- **Christian McCaffrey** — us #1, consensus avg #13.5. Elite when healthy, but retrospective VORP
  rewards the peak season more than consensus risk-adjusts for his injury history.
- **Kyren Williams** (#9 vs. avg #34) and **Travis Etienne** (#17 vs. avg #45) — big realized 2025
  seasons; consensus is skeptical of a repeat (workload/committee risk).
- **D'Andre Swift** (#20 vs. avg #45) — realized-stat VORP doesn't see the team/scheme change
  since last season.
- **Kyle Pitts** (#41 vs. avg #58) — big realized target-share season consensus doubts repeats.
- **The QB group** — Josh Allen (#15 vs. #26.5), Drake Maye (#14 vs. #43.5), and Caleb Williams
  (#35 vs. #59) all rank meaningfully ahead of consensus. This holds across the whole rostered QB
  group, not one player — worth checking against the replacement-baseline investigation already on
  `todo.md` before assuming it's the same retrospective-vs-forward gap as everything else (could
  instead be the QB replacement level being set too low for a single-QB league).

Most of this doesn't get fixed here — it's evidence for the existing `todo.md` item calling for a
real `vorp_projected` metric, not a substitute for building one. **Exception: the whole
"heavy" list above turned out to share one concrete, fixable root cause, not the retrospective
gap** — see `decisions/2026/2026-08-27-bigboard-season-type-postseason-fix.md`. `stats/vorp.py`
was silently summing postseason games into "season" totals (the weekly-stats cache mixes `REG`
and `POST` rows with no filter). Every player in the "heavy" list above played on a playoff team
and had 1–4 illegitimate extra games inflating their total — Drake Maye's #14 overall slot was
almost entirely 4 games of playoff stats that shouldn't have counted. Fixed
(`season_type == "REG"` filter), `data/vorp/2025.parquet` and `data/bigboard/2025.csv`
regenerated, 370 tests passing. The RB-heavy top-12 mix and the "light" list (Chase, A.J. Brown,
etc.) are unaffected by this fix and remain open — see that decision entry's Data section for the
full before/after numbers.

## Caveats

- Two sources only, generic PPR (not this league's exact best-ball/12-team settings).
- Name-matched by normalized string; ~20 of our top 60 (mostly committee/deep-bench RBs and older
  veterans) don't appear in either external top 60 — expected at that range, not a data-quality
  signal.
- These snapshots are a point-in-time pull (2026-08-27) and go stale fast during the season —
  don't reuse the cached lists past the pre-draft window without re-pulling.
