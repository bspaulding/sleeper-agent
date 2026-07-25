# sleeper-agent — Implementation Plan

Status: **draft v1** (2026-07-25). This is the execution breakdown for `PROJECT_PLAN.md`'s
Phase 1, sequenced to be ready before the 2026 season. It is a planning document only — nothing
in here has been built yet; we execute against this later. Update it as reality corrects it.

"Ready for season" here means: **full Phase 1 scope from `PROJECT_PLAN.md`** is live before
week 1 — draft/keeper support, waiver and trade recommenders, news-research, and at least the
core scheduled Routines all working — with the sole exception of the skill self-revision loop,
which structurally can't run until there's a season of decision-log history to learn from.

## 0. Assumptions made while writing this plan

These weren't re-confirmed with Brad before writing; flagged here instead of blocking on them.
Cheap to correct if wrong — say so and this doc updates.

1. **Dates are placeholders.** No real 2026 dates for keeper deadline / draft / week 1 are
   known yet (see `PROJECT_PLAN.md` §3 — the 2026 league doesn't even exist yet). This plan
   uses a generic NFL calendar shape (keeper deadline a couple weeks before the draft, draft in
   late August, week 1 the Thursday after Labor Day) purely to sequence work by dependency, not
   by hard date. **Swap in real dates as soon as the commissioner sets them** — that's what
   actually determines how much slack Phases E/F/G below have.
2. **Keeper cost rule is unknown and isn't in Sleeper's API.** The league setting only exposes
   `max_keepers: 2`; *how much a keeper costs* (a lost draft pick? straight keep, no cost?
   auction value carryover?) is a league house rule Sleeper doesn't model. `draft keepers`
   (Phase E) can rank keeper candidates by value/VORP without this, but can't compute true
   cost/benefit until Brad supplies the actual rule text. **Action needed from Brad before Phase
   E is finished, not before it starts.**
3. **Full automated test coverage**, including fixture-recorded Sleeper/nflverse responses, not
   just tests for pure computation. Rationale: this codebase is explicitly meant to be edited by
   the LLM all season (`PROJECT_PLAN.md` §4); tests are what make that safe to do without a human
   reviewing every diff.
4. **Draft-day tooling supports both interactive and semi-autonomous use** rather than picking
   one: `draft board` is usable on-demand (Brad asks live during the draft) and also takes a
   `--watch` flag that polls and updates a decision-log entry unattended. Building both is
   barely more work than building one, so there's no reason to force the choice now.
5. **`data/` is git-tracked**, per the lean already stated in `PROJECT_PLAN.md` §5.2. If the
   repo grows uncomfortably large this gets revisited, but there's no reason to decide that
   preemptively.
6. **No credentials are needed for any of Phase 1.** Sleeper's read API and nflverse/`nfl_data_py`
   are both public, unauthenticated data sources. This whole phase should need zero secrets —
   worth calling out because it simplifies Phase A a lot, and because Phase 2 (write access)
   will be the first time credential handling is a real concern.

## 1. Repo layout (target state)

```
sleeper-agent/
├── PROJECT_PLAN.md
├── IMPLEMENTATION_PLAN.md
├── cli/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/sleeper_agent/
│   │   ├── __init__.py
│   │   ├── main.py                # typer app, registers all subcommand groups
│   │   ├── config.py              # repo-root discovery, path constants, no env-based secrets needed
│   │   ├── models/
│   │   │   ├── sleeper.py         # League, Roster, User, Player, Transaction, Draft, DraftPick
│   │   │   ├── stats.py           # weekly stat row, snap row, injury row
│   │   │   ├── vorp.py            # per-player VORP result
│   │   │   └── recommendation.py  # TradeRecommendation, WaiverRecommendation, DraftRecommendation, FreeAgentRecommendation, KeeperRecommendation
│   │   ├── sleeper_client/
│   │   │   ├── http.py            # thin requests wrapper, retry/backoff on 429/5xx
│   │   │   ├── league.py          # resolve + sync
│   │   │   ├── players.py         # player dictionary sync w/ 24h cache
│   │   │   ├── draft.py           # draft object + picks (public, no auth)
│   │   │   └── trending.py        # trending adds/drops endpoint
│   │   ├── stats/
│   │   │   ├── nflverse.py        # wraps nfl_data_py calls
│   │   │   ├── sync.py            # orchestrates a full stats sync for a season
│   │   │   └── vorp.py            # ported + generalized VORP methodology
│   │   ├── value/
│   │   │   └── scoring.py         # VORP + trend + injury + wiki-news signal -> value score
│   │   ├── trade/
│   │   │   ├── evaluate.py
│   │   │   └── propose.py
│   │   ├── draft_tools/           # ("draft" is a stdlib-adjacent name collision risk; module named draft_tools, CLI command stays `draft`
│   │   │   ├── board.py
│   │   │   └── keepers.py
│   │   ├── waiver/
│   │   │   └── recommend.py
│   │   ├── freeagent/
│   │   │   └── recommend.py
│   │   ├── decisions/
│   │   │   ├── scaffold.py        # `decisions new`
│   │   │   └── index.py           # `decisions index` regenerates wiki/decisions.md
│   │   ├── wiki_tools/
│   │   │   ├── frontmatter.py     # parse/write YAML frontmatter + News section helpers
│   │   │   ├── scaffold.py        # `wiki scaffold players|teams`
│   │   │   └── staleness.py       # `wiki stale`
│   │   └── storage/
│   │       └── parquet_store.py   # read/write helpers, schema versioning
│   └── tests/
│       ├── fixtures/              # recorded Sleeper + nflverse responses (JSON/parquet snippets)
│       ├── test_sleeper_client.py
│       ├── test_players_cache.py
│       ├── test_stats_sync.py
│       ├── test_vorp.py
│       ├── test_value.py
│       ├── test_trade.py
│       ├── test_draft_tools.py
│       ├── test_waiver.py
│       ├── test_freeagent.py
│       ├── test_decisions.py
│       └── test_wiki_tools.py
├── data/                          # parquet store, see PROJECT_PLAN.md §5.2
├── wiki/                          # markdown wiki, see PROJECT_PLAN.md §5.3
├── decisions/                     # decision log, see PROJECT_PLAN.md §7
└── .claude/skills/                # see §6 below
```

## 2. Phase A — Foundations

Nothing else can be built until this exists. No CLI features yet — just the scaffolding that
every later phase depends on.

**Tasks**

- Initialize `uv` project under `cli/`: `pyproject.toml` (Python 3.12+, deps: `typer`,
  `pydantic`, `polars`, `requests`, `nfl_data_py`, `pyyaml` for frontmatter; dev deps: `pytest`,
  `ruff`, `respx` or `responses` for HTTP mocking).
- `config.py`: repo-root discovery (walk up from cwd looking for a marker like `.git` or
  `PROJECT_PLAN.md`), and path constants for `data/`, `wiki/`, `decisions/`. No secrets/env vars
  needed per assumption §0.6 — keep this file boring on purpose.
- `sleeper_client/http.py`: a thin wrapper around `requests` with a base URL
  (`https://api.sleeper.app/v1`), retry-with-backoff on 429/5xx (our call volume is low enough
  that Sleeper's 1000 req/min ceiling is very unlikely to matter — this is a correctness/
  robustness measure, not real rate limiting).
- `storage/parquet_store.py`: `read(table_path) -> polars.DataFrame`, `write(df, table_path)`,
  each table versioned with a `schema_version` column or sidecar so a future schema change
  doesn't silently corrupt old data — reader should fail loudly on an unexpected schema rather
  than guess.
- `wiki_tools/frontmatter.py`: parse/write YAML frontmatter + body for a markdown wiki page;
  helper to append a dated entry to a page's "News" section (used by both the news-research
  skill's instructions and — if useful — a small CLI assist, see Phase C).
- CI: a GitHub Actions workflow (`.github/workflows/ci.yml`) running `ruff check` and
  `pytest` on push/PR to the working branch. Cheap, keeps the "safe for the LLM to keep editing"
  property real instead of aspirational.
- `tests/fixtures/`: record a handful of real Sleeper responses (league object, rosters, players
  dictionary excerpt, a draft's picks) and a small nflverse weekly-stats slice, checked in as
  static fixtures so tests don't hit the network.

**Definition of done:** `uv run sleeper-agent --help` shows an empty-but-structured CLI;
`uv run pytest` passes (even if trivially, on a smoke test); CI is green on a throwaway PR.

## 3. Phase B — League & stats data

Implements `PROJECT_PLAN.md` §6.1 and §6.2's `sync`/`vorp` commands. This is the data backbone
everything else reads from.

### `sleeper` command group

| Command | Behavior | Notes |
|---|---|---|
| `sleeper league resolve [--season YYYY] [--user yellldarb]` | Prints the resolved league_id for the given season. Tries `/user/<user_id>/leagues/nfl/<season>` first; if empty (season's league not created yet), falls back to the newest prior season found by walking `previous_league_id`, and says explicitly that it fell back. | Must treat "not created yet" as a normal, logged outcome — not an exception. |
| `sleeper league sync [--league-id ID] [--season YYYY]` | Pulls league object (incl. `scoring_settings`, `roster_positions`), all rosters, all users, transactions (trade/waiver/free_agent — Sleeper's transactions endpoint is paginated by round; pull all rounds), draft object + picks, traded picks. Writes `data/sleeper/{league,rosters,users,transactions,drafts}/<season>.parquet`. | `--league-id` overrides `resolve` for pointing at a specific (e.g. historical) league explicitly — needed right now since 2026 doesn't exist yet and 2025 is what we validate against. |
| `sleeper players sync [--force]` | Pulls the full `/players/nfl` dictionary (~5k rows). Sidecar `data/sleeper/players.meta.json` records `fetched_at`; skip re-fetch within 24h unless `--force`. | Sleeper explicitly asks callers not to hit this more than once/day. |
| `sleeper roster show [--roster-id N | --me]` | Human-readable current roster (player names joined in, not raw IDs) for quick inspection/debugging. `--me` resolves to roster_id 5 (yellldarb) via config. | Convenience wrapper, not a new data source. |
| `sleeper trending [--type add\|drop] [--hours 24]` | Pulls Sleeper's trending-players endpoint. Feeds waiver/free-agent recommend (Phase F). | Not persisted to parquet — cheap enough to fetch live each time it's needed. |

**Tests:** fixture-driven — given a recorded league/roster/players JSON payload, assert the
parquet output has the right shape and the right rows; `resolve`'s fallback path tested with a
fixture where the target season's league list is empty.

### `stats` command group

| Command | Behavior | Notes |
|---|---|---|
| `stats sync --season YYYY` | Pulls nflverse weekly stats, snap counts, schedules, injuries, and the player-ID crosswalk (`nfl_data_py.import_ids()`, which includes a `sleeper_id` column — this is the join key back to Sleeper data) into `data/stats/`. | |
| `stats vorp --season YYYY [--league-id ID]` | Computes fantasy points per player (season total + per-game) using the **live scoring_settings** from `data/sleeper/league/<season>.parquet` (fails clearly if that hasn't been synced yet — explicit dependency, not a silent default). Replacement level is derived from `roster_positions`, generalized (see below), not hardcoded. Writes `data/vorp/<season>.parquet`. | Port of `bspaulding/nfl-vorp`'s `vorp.ts` methodology (see `PROJECT_PLAN.md` §6.2), generalized in two ways described next. |

**VORP generalization details (this needs actual design, not just "port it"):**

1. **Scoring must be data-driven.** `nfl-vorp`'s `vorp.ts` hardcoded a scoring table. This
   version builds the fantasy-points formula from the league's actual `scoring_settings` dict at
   runtime (iterate the known stat-key → scoring-key mapping between nflverse columns and
   Sleeper's scoring settings fields, e.g. `rec_yd` × receiving yards). Needs an explicit mapping
   table (nflverse column name → Sleeper scoring_settings key) as a first-class, tested piece of
   code, since it's the thing most likely to have a subtle bug that skews every downstream value.
2. **FLEX-slot replacement level must be derived from `roster_positions`, not assumed.** The old
   project hardcoded "RB 2.5 / WR 2.5" for one FLEX slot. This league has 2 generic `FLEX` slots
   (RB/WR/TE eligible). Approach: count each literal starter slot from `roster_positions`
   (QB, RB, WR, TE, DEF counts), then distribute each `FLEX`-family slot (`FLEX`, and — if ever
   used elsewhere — `WRRB_FLEX`, `SUPER_FLEX`, etc.) across its eligible positions using a
   configurable weight (default: RB 0.45 / WR 0.45 / TE 0.10, tunable constant, not derived from
   anything fancier for v1). Document the default weights in code with a comment pointing at this
   plan, and **validate the whole VORP output against known 2025 end-of-season fantasy point
   totals/rankings** (milestone-2-style sanity check) before trusting it for real decisions.

**Tests:** the scoring-mapping table gets its own unit tests (a handful of known stat lines →
known point totals, checked by hand against Sleeper's own displayed scoring for a couple of real
2025 games); the FLEX-distribution logic tested against this league's actual `roster_positions`
and at least one synthetic alternate roster shape (e.g. no FLEX, or a SUPER_FLEX) to make sure it
isn't accidentally special-cased to this one league.

**Definition of done (Phase B):** `sleeper league sync`, `sleeper players sync`, and
`stats sync --season 2025` run clean against the real (completed) 2025 league; `stats vorp
--season 2025` produces a ranked player list that passes a manual sanity check against known
real-world 2025 fantasy performance (top players are recognizable as top players).

## 4. Phase C — Wiki, decision log, and news-research skill v1

Implements `PROJECT_PLAN.md` §5.3, §5.4, §7, plus the `news-research.md` skill. This phase is
mostly about making the *format* reliable before the LLM leans on it all season.

### `wiki` command group (new — supporting infra, not in `PROJECT_PLAN.md` originally, added
here because letting page format drift is worse than a small CLI investment to prevent it)

| Command | Behavior |
|---|---|
| `wiki scaffold players [--roster-id N \| --all-rostered]` | Ensures a `wiki/players/<sleeper_id>-<slug>.md` file exists (frontmatter: `sleeper_id`, `name`, `position`, `nfl_team`, `last_researched: null`) for every player on the given roster, or league-wide. Idempotent — never overwrites an existing page's body. |
| `wiki scaffold teams` | Ensures all 32 `wiki/nfl-teams/<code>.md` stubs exist with the same idempotency guarantee. |
| `wiki stale [--days N] [--roster-id N \| --me]` | Lists pages among the given scope whose `last_researched` is missing or older than N days — this is what the news-research skill queries instead of guessing what needs attention. |

### `decisions` command group

| Command | Behavior |
|---|---|
| `decisions new --kind {draft,keeper,trade,waiver,freeagent} --slug <slug> [--season YYYY]` | Scaffolds `decisions/<season>/<date>-<kind>-<slug>.md` with the agreed frontmatter (`date`, `kind`, `season`, `week`, `status: recommended`, `players_involved: []`, `related_wiki: []`) and section headers (Summary / Reasoning / Data / Outcome). The LLM fills in content; the tool just prevents format drift. |
| `decisions index` | Regenerates `wiki/decisions.md` by scanning `decisions/**/*.md` frontmatter — mechanically derived, never hand-edited, so it can't go stale. |

**Skill: `.claude/skills/news-research.md`** — content outline to write in this phase (full text
TBD when we execute, but the plan needs to say what sections it must cover so nothing gets
missed):

1. **Trigger conditions** — when to research at all (always: rostered/targeted players and their
   NFL teams ahead of a lineup-affecting decision; opportunistically: anyone `wiki stale` flags).
2. **Source prioritization** — team injury reports and beat reporters over aggregators; how to
   judge source quality on the fly since there's no fixed source list.
3. **Filing convention** — the dated/tagged/linked entry format from `PROJECT_PLAN.md` §5.4,
   written out as copy-pasteable format, plus which page(s) (player vs. team vs. both) a given
   story belongs on.
4. **Check-before-you-write step** — read the page's News section (and `last_researched`) before
   researching, to avoid duplicate work and duplicate entries.
5. **Frontmatter maintenance** — always bump `last_researched` after a pass, even if nothing new
   was found (a confirmed "nothing new" is still information — it means don't re-check tomorrow).

**Tests:** `wiki scaffold` idempotency (running twice doesn't clobber a page with real content);
`decisions new` produces valid frontmatter parseable by `wiki_tools/frontmatter.py`;
`decisions index` output matches a hand-built expected index for a small fixture set of decision
files.

**Definition of done (Phase C):** `wiki scaffold players --all-rostered` and `wiki scaffold
teams` run once to populate real stub pages for the current roster; one real, manually-run
news-research pass (following the v1 skill) produces at least one correctly-formatted, linked
News entry; `decisions new` + a hand-written decision + `decisions index` round-trips correctly
and gets committed/pushed as a real test of the git-as-audit-trail flow from `PROJECT_PLAN.md`
§1.

## 5. Phase D — Player valuation

Implements `PROJECT_PLAN.md` §6.3.

| Command | Behavior |
|---|---|
| `value player <sleeper_id> [--season YYYY] [--week N]` | Prints VORP (season total + per-game), a trend signal (last-4-games snap share/target share/usage rate vs. season average, from `data/stats/`), current injury status (from nflverse injury data), and the most recent News entries pulled straight from that player's (and, if relevant, their team's) wiki page. This is the "combination of metrics" the acceptance criteria asks for — VORP is the quantitative backbone; trend + injury are additional CLI-computed signals; the wiki News excerpt is where qualitative/LLM judgment plugs in. |
| `value rank [--position POS] [--top N]` | Same scoring, ranked list, filterable — used for browsing during trade/waiver/draft work rather than one player at a time. |
| `value roster [--roster-id N \| --me]` | Aggregates `value player` across a roster, broken down by position, to answer "where is this team strong/thin" for trade-target scanning (Phase G) and waiver need-finding (Phase F). |

**Tests:** trend computation against a fixture with known week-by-week usage numbers (assert the
last-4-vs-season delta is computed correctly, including edge cases like a player with under 4
games played); `value roster`'s positional breakdown checked against a small fixture roster with
a hand-computed expected breakdown.

**Definition of done:** `value rank --position RB --top 20` output is manually sanity-checked
against real 2025 RB performance; `value roster --me` correctly reflects yellldarb's actual
roster composition and surfaces at least one plausible positional need or surplus.

## 6. Phase E — Keepers & draft

Implements `PROJECT_PLAN.md` §6.5, plus `draft.md` skill. **Blocked on Brad supplying the real
keeper-cost rule (see §0.2) before this phase can be called done**, though the value-ranking
half doesn't need to wait on that.

| Command | Behavior |
|---|---|
| `draft keepers [--roster-id N \| --me]` | Lists the roster's players ranked by value/VORP as keeper candidates. Cost/benefit modeling is a stub until the real keeper-cost rule is known (§0.2) — ship the ranking now, add cost math as a small follow-up once Brad provides the rule, don't block the whole command on it. |
| `draft board [--league-id ID] [--rounds N] [--watch]` | On-demand best-available-by-value view: cross-references `data/vorp` + `value rank` against already-drafted/kept players (via the draft's public picks endpoint, no auth needed, same approach as `bspaulding/nfl-vorp`'s `vorp-draft-cli.ts`). `--watch` polls every ~30s and re-renders, and (if run as part of a Routine rather than interactively) writes/updates a running `decisions/.../<date>-draft-live.md` entry each time the board changes meaningfully — this is what makes both draft-day operating modes (interactive or semi-autonomous, see §0.4) work off the same command. |

**Tests:** `draft board` filtering-out-drafted-players logic tested against a fixture draft with
a partial set of picks made; keeper ranking tested against a fixture roster with known relative
values.

**Skill: `.claude/skills/draft.md`** — outline: positional strategy for a 3-round supplemental
draft on top of a mostly-fixed keeper roster (this is not a full startup draft — most value
decisions already happened via keepers); how to weigh keeper candidates once cost math exists;
what "good value" means with only 3 rounds to work with (likely: fill the thinnest starting
position and/or best-player-available for a bench flier, not deep positional runs).

**Definition of done:** `draft board` correctly tracks a real completed draft when pointed at
the 2025 draft_id as a replay test; keeper ranking runs against yellldarb's real current roster;
`draft.md` v1 is written; real keeper-cost rule has been obtained from Brad and wired in (or
this is explicitly and visibly still open going into the actual keeper deadline).

## 7. Phase F — Waivers & free agents

Implements `PROJECT_PLAN.md` §6.6, plus `waivers.md` and `free-agents.md` skills.

| Command | Behavior |
|---|---|
| `waiver recommend [--budget-remaining N]` | Combines: current FAAB budget remaining (from synced roster settings — `waiver_budget_used`), positional needs (from `value roster`), and trending adds (`sleeper trending --type add`) filtered to actually-available players. Outputs ranked targets with a suggested bid **range**, not a single number — final bid sizing (budget pacing across the remaining season, how much to protect against a coming bigger need) is a judgment call that belongs in the `waivers.md` skill, not hardcoded in the CLI. |
| `freeagent recommend [--roster-id N \| --me]` | Same idea without FAAB math — ranks available upgrades over the roster's weakest bench-eligible player per position. |

**Tests:** bid-range calculation tested against fixtures with known budget-remaining and
weeks-remaining inputs; recommendation filtering tested to correctly exclude already-rostered
players.

**Skills:**
- `waivers.md` — FAAB budget pacing across ~17 weeks (not spending everything on early-season
  overreactions), how to weigh a suggested bid range down to one number, when a 0 bid ("just
  claim it, nobody else will") is correct.
- `free-agents.md` — add/drop heuristics for the gap between waiver periods; when dropping a
  bench keeper-eligible player is/isn't acceptable.

**Definition of done:** `waiver recommend` run against the real current (2025, since 2026 isn't
live yet) roster/budget state produces a plausible ranked list; both skills v1 written.

## 8. Phase G — Trades

Implements `PROJECT_PLAN.md` §6.4, plus `trades.md` skill.

| Command | Behavior |
|---|---|
| `trade evaluate --give <ids/picks> --get <ids/picks> [--other-roster-id N]` | Parses a specific offer (comma-separated Sleeper player IDs and/or pick references like `2026-R2`), computes VORP/value delta for both sides and positional-need delta for both rosters post-trade. Supports a `--json` flag for structured output the LLM can quote directly into a decision log entry. |
| `trade propose [--target-roster-id N \| --all] [--top N]` | Finds value-balanced candidate packages between our roster and a target (or scans all 11 opponents): match our surplus positions against their needs and vice versa, generate candidate 1-for-1 / 2-for-1 packages within a value-delta tolerance (default ±10%), and rank by a plausibility heuristic (extremely lopsided-but-technically-fair offers are unlikely to be accepted even if the math works). |

**Tests:** offer-parsing (player IDs + pick refs) tested including malformed input; value-delta
tolerance filtering and the plausibility heuristic tested against fixture rosters with known
surpluses/needs.

**Skill: `.claude/skills/trades.md`** — when to propose vs. wait; how to weigh `trade
evaluate`'s numbers against team-building narrative/roster fit from the wiki (e.g., a
value-neutral trade that fixes a bye-week/injury-depth problem might be worth it even at a
slight value discount); what to do with an incoming offer that's a marginal loss but improves
positional balance.

**Definition of done:** `trade evaluate` correctly re-evaluates at least one real historical
2025 trade from this league (sanity check against an actual past decision); `trade propose
--all` produces plausible candidate offers against the real league; `trades.md` v1 written.

## 9. Phase H — Scheduling (Claude Code Routines)

Implements `PROJECT_PLAN.md` §8. This is where the CLI/skills work above actually starts running
without Brad manually invoking it.

**Tasks**

- Set up the Routines themselves (via `create_trigger`) once the commands they call exist:
  1. Weekly stats + VORP recompute (Tuesday, after waivers clear): `stats sync` → `stats vorp`
     → `wiki stale` → opportunistic news-research pass.
  2. Waiver-window reminder (Monday, ahead of Tuesday processing): `waiver recommend` →
     `decisions new --kind waiver` with the LLM's final call written in.
  3. Trade-deadline-aware scouting: starts light, ramps up in frequency approaching week 11
     (`trade_deadline` from league settings) — `trade propose --all` → decision log entry for
     anything worth surfacing.
  4. Draft-day: not a recurring cron, a one-shot Routine scheduled for the actual draft window
     once it's known, running `draft board --watch`.
- Each Routine's prompt should be self-contained (per Routine tooling's own guidance) — it needs
  to say which CLI commands to run and where to look (this plan + `PROJECT_PLAN.md`), since it's
  waking a fresh reasoning pass each time, not continuing a live conversation.

**Definition of done:** at least the weekly stats/VORP Routine and the waiver-window Routine are
created and have fired at least once successfully before week 1; the trade-scouting Routine is
created (can start at low frequency, doesn't need to have fired yet); the draft-day Routine is
scheduled once the real draft date is known.

## 10. Phase I — Skill self-revision (groundwork only)

Per `PROJECT_PLAN.md` §9's meta-loop. This phase's deliverable before the season is **process,
not execution** — there's no decision-log history to learn from yet.

**Tasks**

- Write a short `meta` note (could live as a section in each skill file, or a shared
  `.claude/skills/README.md`) describing the review cadence (end of season, or after a
  notably good/bad decision) and the expectation that a skill edit is committed with a
  decision-log-style rationale, per `PROJECT_PLAN.md` §9.
- No actual skill revisions happen in this phase — there's nothing to learn from yet. This is
  intentionally the lightest phase before the season; it becomes real work once games start.

**Definition of done:** the review process is documented; first real revision is explicitly
scheduled for after enough decision-log history exists (e.g., first bye week, or end of season).

## 11. Cross-cutting: what "ready for season" actually checks

Pull this list out and literally check it off once Phases A–H are done:

- [ ] `uv run pytest` and `ruff check` both pass in CI on the working branch.
- [ ] `sleeper league resolve` correctly finds/falls back for the current season, tested against
      the real "2026 doesn't exist yet" state.
- [ ] `stats vorp` output has been sanity-checked against known real 2025 results.
- [ ] Every rostered player and all 32 NFL teams have a scaffolded wiki page (`wiki scaffold`).
- [ ] At least one full sync → analyze → `decisions new` → commit/push cycle has been run
      end-to-end, for real, not just in tests.
- [ ] All five skills (`draft.md`, `trades.md`, `waivers.md`, `free-agents.md`,
      `news-research.md`) exist in v1 form.
- [ ] Keeper-cost rule has been obtained from Brad and wired into `draft keepers` (§0.2) — or,
      failing that, this is a known, visible gap going into the keeper deadline, not a silent one.
- [ ] Weekly stats/VORP Routine and waiver-window Routine are live and have fired successfully
      at least once.
- [ ] Draft-day Routine is scheduled once the real draft date is known.
- [ ] Real 2026 keeper deadline / draft date / week-1 date have replaced the placeholders in §0.1
      everywhere they matter (Routine schedules especially).
