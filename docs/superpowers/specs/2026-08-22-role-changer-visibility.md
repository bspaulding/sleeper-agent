---
date: '2026-08-22'
status: proposed
related_decisions: []
related_wiki:
  - wiki/team/role-changers.md
  - wiki/team/rookie-evaluation.md
  - wiki/team/draft-strategy.md
  - wiki/team/roster-philosophy.md
---

# Role-changer (FA/trade) visibility for `draft board`/`value`

## Motivation

Sibling spec to `docs/superpowers/specs/2026-08-22-rookie-and-new-outlook-player-visibility.md`,
covering the other half of `todo.md`'s "Rookie / new-outlook player research strategy" item:
players who changed team or offensive role via free agency or trade with a materially different
outlook than their prior-season stats reflect.

The failure mode here is different from the rookie half, not just a smaller version of it. A
rookie is *missing* from `stats vorp` — no row exists. A role-changer has a **full, correctly
computed VORP row** — `compute_vorp` did its job, the number accurately reflects what that player
scored last season. The gap is that the number silently assumes the context that produced it
(team, scheme, target competition) still holds, and nothing in the pipeline flags when that
assumption has broken. `draft board`/`value rank` will confidently rank a player by a number that
may no longer describe their situation, with no signal that anything changed.

`wiki/team/role-changers.md` (written alongside this spec) holds the evaluation framework this
spec's UI decisions are built on: vacated-opportunity reasoning, the 2026-specific note that 21 of
32 teams changed offensive coordinators, and the "landing spot alone doesn't guarantee production"
skepticism from the buy-low literature. This spec is the "detect and flag it" half.

## 1. Detection: no new data source needed

Unlike the rookie spec (required pulling `nflreadpy.load_draft_picks`), this population is fully
detectable from data **already synced**:

- `data/stats/weekly/{season}.parquet` carries a per-player-week `team` column — the last row per
  player (sorted by week) gives their most recent prior-season team.
- `data/sleeper/players.parquet`'s `team` field reflects the current team, per the normal
  `sleeper players sync` cadence.
- Join both to `sleeper_id` via the existing `gsis_id` crosswalk (`data/stats/ids.parquet`, the
  same join `compute_vorp` and `gsis_id_for_sleeper_id` already use).

**Team-code normalization, confirmed by diffing every code on both sides live:** nflverse codes
the Rams `LA`; Sleeper codes them `LAR`. This is the *only* mismatch across all 32 teams — every
other code matches exactly. A single alias map, `{"LA": "LAR"}`, is sufficient; this is not a
general fuzzy-matching problem and shouldn't be built as one.

New helper, e.g. `detect_team_changes(weekly_stats_df, players_df, id_crosswalk) ->
list[TeamChange]` in `value/` (alongside `scoring.py`, since this is a value-layer concern like
`filter_rostered`, not a draft-specific one) — returns each changed player's old team, new team,
and prior-season opportunity totals (see §2). Confirmed live against the 2025→2026 data: **132
raw team changes** at QB/RB/WR/TE after normalization.

## 2. Triage: prior-season opportunity as the filter

No draft-capital equivalent exists for veterans, but an analogous already-unused signal does:
`target_share`, `air_yards_share`, and `wopr` are present on every row of
`data/stats/weekly/*.parquet` today and consumed by nothing in the codebase (`compute_vorp` only
uses raw counting stats for its fantasy-points formula).

Filter `detect_team_changes`'s output to players with **≥50 total prior-season touches/targets**
(`carries + targets`, summed across the season) — a "had a real role somewhere" floor, not a
quality signal, mirroring the rookie spec's draft-capital cutoff in spirit (excluding the
long tail nobody should spend research time on) even though the underlying signal is different.
Confirmed live: this narrows 132 → **36**. Extend `TeamChange` (or wrap it) with this total so the
threshold is a simple, testable comparison, not a re-derivation.

`50` is a starting constant, not a derived value — flag it the same way `draft_tools/board.py`'s
existing `_is_tier_break`'s 20% threshold is flagged: simple and testable now, tune later against
real results per the `.claude/skills/` self-revision process.

## 3. Wiki wiring

Unlike rookies, most role-changers are veterans who **already have a wiki page** from a prior
season — `scaffold_players` (`wiki_tools/scaffold.py`) still applies for the rare case a page is
missing (e.g. a practice-squad call-up who never got scaffolded), but the primary action here is
triggering `.claude/skills/news-research.md`'s existing targeted-lookup mode against the triaged
list each offseason — landing spot, scheme fit, camp-report role signal — filed the normal way, no
new filing convention needed. This mirrors §3 of the rookie spec exactly, just without the
scaffolding step being the common case.

## 4. `draft board`/`value` surfacing

Unlike rookies, these players are **already correctly ranked** in the existing VORP-sorted
board/list — the fix isn't visibility, it's context. Recommendation: an inline annotation on the
existing row, not a separate section (contrast with the rookie spec's segregated "Rookie watch"
block, which was necessary there because those players have no VORP number to sort by at all).
Something like a `[MOVED: CAR→PIT]` tag appended to a `render_board`/`value rank` row when the
player is in the triage list — no reordering, no synthetic score adjustment, purely informational,
same non-reordering discipline the positional-need spec established for the main board. `value
player` should surface the same tag plus a pointer to the `recent_news_excerpt` context, since
that's exactly the qualitative-judgment handoff `PROJECT_PLAN.md` §6.3 already designs for.

## 5. Tests

Following `cli/tests/test_draft_tools.py`/`test_vorp.py`'s fixture style:

- `detect_team_changes`: correct diff against a weekly-stats + players fixture, including the
  `LA`/`LAR` normalization case (must **not** flag a Rams player who didn't actually move) and a
  genuine cross-team move.
- Opportunity-floor boundary: exactly 50 touches/targets included, 49 excluded.
- Board/value tag rendering: `[MOVED: ...]` appears only for triaged players, existing sort order
  and VORP values completely unchanged.

## 6. Rollout

Same validation pattern as the rookie spec: confirm against the next mock draft that the `MOVED`
tag actually reads as useful signal at the moment of a pick, not noise — the concrete risk here is
tagging too liberally (132 raw matches is a lot of rows) if the opportunity floor turns out too
low in practice.

## Out of scope / follow-up

- **Team-level vacated-opportunity aggregate** (sum of a team's departed players' `target_share`/
  `air_yards_share`) — computable from the same already-synced columns, and would let
  `role-changers.md`'s "what did this team lose" framing be answered mechanically rather than by
  hand, but it's a second join (matching departures *to* their former team, not just tracking
  individual arrivals) and isn't required to ship the core flag. Worth a follow-up once this spec's
  basic detection proves useful.
- **Offensive-coordinator/scheme-change detection** — no field for this exists in any currently
  synced data source; `role-changers.md` notes 21 of 32 teams changed OCs for 2026 as pulled from
  general web research, not anything queryable. This stays LLM/news-research territory
  indefinitely unless a structured coaching-staff data source turns up later.
- Re-triaging in-season (a role-changer whose new-team role becomes clear only after Week 1-2) is
  not handled here — like the rookie spec, this is a preseason snapshot, not a living
  recalculation.
