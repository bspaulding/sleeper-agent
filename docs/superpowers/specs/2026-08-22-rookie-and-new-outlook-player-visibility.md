---
date: '2026-08-22'
status: proposed
related_decisions: []
related_wiki:
  - wiki/team/rookie-evaluation.md
  - wiki/team/draft-strategy.md
  - wiki/team/roster-philosophy.md
---

# Rookie & new-outlook player visibility for `draft board`/`value`

## Motivation

`todo.md`'s "Rookie / new-outlook player research strategy" item, flagged 2026-08-16 while scoping
the positional-need-aware `draft board` work (`docs/superpowers/specs/2026-08-16-draft-strategy-
research-and-positional-need.md`, explicitly out of scope there), root-caused as: `compute_vorp`
(`cli/src/sleeper_agent/stats/vorp.py`) only produces a row for a player present in the prior
season's nflverse weekly-stats table. There's no exclusion logic to point at — it's a join that
silently omits anyone it has no rows for — so every player with no prior-NFL-season stats is
structurally invisible to `stats vorp`, `draft board`, and `value rank`/`value roster` alike, not
just stale until the next sync.

Checked directly against `data/vorp/2025.parquet` and `data/sleeper/players.parquet` during this
research pass: **212 players leaguewide with zero NFL experience (`years_exp == 0`) and a current
NFL roster spot have zero 2025 VORP rows** (192 at QB/RB/WR/TE). This reproduces every season —
next year's incoming rookie class will always be invisible the same way regardless of stats-sync
freshness. (Colston Loveland, the case that originally surfaced this gap, has since resolved
himself now that a full 2025 stat line exists for him — but that's just last year's rookie class
rotating into visibility; the front end of the pipeline is permanently empty.)

A second, related population — players who changed team/role via free agency or trade with a
materially different offensive outlook than their prior-season stats reflect — has the same
downstream symptom (a stale or misleading VORP number, rather than a missing one) but a different
detection mechanism and no draft-capital-style signal to triage by. This spec covers the rookie
half, which has a concrete, quantifiable signal to build on; the FA/trade half is scoped out below
as a smaller follow-up.

`wiki/team/rookie-evaluation.md` (written alongside this spec) holds the research backing every
threshold used below: draft-capital hit-rate tables by position, secondary college-production
signals, and a best-ball-specific framing tied to this league's roster grid. This spec is the
"make the tool use that research" half; the wiki page is the "what the research says" half —
same split as `wiki/team/draft-strategy.md` vs. the positional-need spec.

## 1. New data: NFL draft capital

`nflreadpy` — already a project dependency, used today only via `stats/nflverse.py`'s
`fetch_weekly_stats`/`fetch_snap_counts`/`fetch_schedules`/`fetch_injuries`/`fetch_id_crosswalk`
— also exposes `load_draft_picks(seasons=[...])`, confirmed live during this research pass to
return 257 rows for the 2026 draft with `round`, `pick`, `position`, `college`, `age`, `team`, and
`gsis_id`. This closes the "draft capital" half of the todo's "draft capital, college production"
signal list without a new data source or scraper, consistent with `PROJECT_PLAN.md` §5.4's
scraper-aversion stance.

Add to `stats/nflverse.py`:

```python
def fetch_draft_picks(seasons: list[int]) -> pl.DataFrame:
    return nfl.load_draft_picks(seasons=seasons)  # pragma: no cover - live nflverse call
```

New sync command `stats draft-picks sync --season <year>` in `stats_cmd.py`, mirroring `stats
sync`'s existing shape, writing `data/nfl/draft_picks.parquet`.

**Crosswalk deviation, confirmed live against the 2026 class during the pre-draft sweep this spec
was validated against:** `load_draft_picks`'s `gsis_id` column is **not** a real nflverse GSIS ID
for the current draft class — it's some other PFR-derived scheme (e.g. `MEN516487` vs. the real
`00-0041562` format), so joining it against `load_ff_playerids()`'s `gsis_id` column the way
`compute_vorp`/`gsis_id_for_sleeper_id` do produces **zero matches**, not partial ones. This only
shows up for players who haven't accumulated real NFL stats yet (i.e. exactly the rookie
population this spec targets), which is presumably why the existing crosswalk usage never hit it.
The working fallback, confirmed to resolve 14/14 test cases: join on normalized
`(name, position)` against `load_ff_playerids()` filtered to `draft_year == <season>` instead of
`gsis_id`. Implement the new join this way, not by reusing `gsis_id_for_sleeper_id` as-is.

## 2. Triage: which rookies are worth surfacing at all

`wiki/team/rookie-evaluation.md`'s draft-capital table gives position-specific hit rates that
make "research/surface every rookie" the wrong default — most of the 192 skill-position rookies
in the league's player pool have single-digit-percent historical fantasy relevance. Triage cutoff,
directly from that table:

| Position | Cutoff | Rationale (from `rookie-evaluation.md`) |
|---|---|---|
| TE | Round 1 only | 81.8%/54.5% top-24/top-12 hit rate round 1 vs. 4.6%/0% by day 3 |
| QB | Round 1 only | 84% of all fantasy-relevant rookie QBs in a decade were 1st-round; low league priority regardless (single QB slot, no superflex) |
| WR | Rounds 1–2 | 84% of identified rookie-WR breakouts came from rounds 1–2 combined |
| RB | Rounds 1–3 | Round 2 keeps pace with round 1 at the top-36 tier; day-3 RBs are a 1.3% hit rate |

New helper in `draft_tools/` or `value/`, e.g. `triage_rookies(draft_picks_df, players_df) ->
list[Player]`, applying this table. This is the mechanical piece of the manual pre-draft sweep
already run once by hand this session — codifying it turns a one-off LLM research pass into a
repeatable per-season step.

## 3. Wiki wiring

`wiki_tools/scaffold.py::scaffold_players` already works off `data/sleeper/players.parquet` (the
Sleeper player dictionary), not stats — it is **not** blocked by the VORP gap and needs no changes
to scaffold a triaged rookie's page. The existing `sleeper-agent wiki scaffold players` CLI
command *is* blocked, though: it's scoped to players already on a fantasy roster in the league
(`cmd_wiki_scaffold_players` reads `rosters/{season}.parquet`), which no pre-draft rookie is. Add
a scaffolding path that takes the triage list directly instead of a roster — either a new
`--triaged-rookies` flag on `wiki scaffold players`, or a dedicated `wiki scaffold rookies
--season <year>` subcommand calling `scaffold_players` on `triage_rookies`'s output. Either way,
`recent_news_excerpt` (`value/scoring.py`) already reads any wiki page's `## News` bullets
regardless of whether that player has a VORP row, so once a page exists and has been researched,
it's already pickup-ready for `value player`.

Research filing itself uses the existing `.claude/skills/news-research.md` targeted-lookup mode
unchanged — this spec adds a *trigger* (the triage list) for who to run it against each season,
not a new filing convention. No skill-file changes needed.

## 4. `draft board` surfacing

Triaged rookies still have no VORP number — inventing a synthetic one (e.g. replacement-level-
flat) would blend a qualitative judgment call into a number the rest of the board treats as
directly comparable, cutting against `PROJECT_PLAN.md` §6.3's explicit design choice to keep VORP
purely quantitative and let the LLM layer qualitative context on top rather than encoding
everything numerically. Recommendation: a separate **"Rookie watch" section**, rendered below the
existing ranked board in `render_board` (`draft_tools/board.py`), listing triaged-and-available
rookies (cross-referenced against drafted picks the same way `board_view` already excludes drafted
players from the main list) with draft round/position and a `recent_news_excerpt` pull — unranked
against VORP, explicitly separate from the sorted list. This preserves the non-reordering
guarantee the positional-need spec already established for the main board (§2d of that spec) by
not touching it at all; the addition is a second, clearly-labeled block.

## 5. Tests

Following `cli/tests/test_draft_tools.py`'s existing fixture style:

- `triage_rookies`: correct position/round filtering against a `draft_picks` fixture, including
  boundary cases (WR round 2 in, round 3 out; RB round 3 in, round 4 out).
- Crosswalk join: a draft pick with no matching `sleeper_id` is skipped, not errored on.
- Wiki scaffolding path: triaged rookies missing a page get one created; existing pages are
  untouched (matches `scaffold_players`'s existing idempotency contract).
- `render_board`'s Rookie watch section: present only when triaged rookies are supplied, drafted
  triaged rookies excluded the same way the main board excludes drafted players, no VORP/tier
  fields rendered for this section.

## 6. Rollout

Same DoD pattern as the positional-need spec: no separate sign-off beyond validating against the
next mock draft — specifically, confirming the Rookie watch section actually surfaces a player who
would otherwise have gone unmentioned (the concrete failure mode Loveland represented in mock
draft #1, before his stats caught up to him).

## Out of scope / follow-up

- **Free-agency/trade role-changers** (the second half of the original todo item). No draft-
  capital-style quantitative signal exists for this population — `wiki/team/rookie-evaluation.md`
  §"New-situation veterans" covers the qualitative framework (vacated opportunity, scheme fit) but
  the *detection* mechanism (who changed situations enough to matter) is still an open question —
  likely a team-diff each offseason (`players.parquet`'s `team` field vs. last season's roster/
  VORP snapshot) rather than anything nflverse exposes directly. Smaller population than the
  rookie class historically; worth its own pass once this spec ships rather than bundled in.
- Re-triaging as the season progresses (e.g. a day-3 rookie who wins a starting job in camp,
  contradicting the draft-capital prior) isn't handled here — the triage list is a preseason
  snapshot per this spec, not a living recalculation.
