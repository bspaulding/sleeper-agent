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

1. ~~Dates are placeholders.~~ **Resolved.** The commissioner's 2026 league-launch email
   (2026-08-04) set the real dates: NFL week 1 opens **Wednesday, Sept 9** (first Wednesday
   opener since 2012), so the draft moved to Labor Day weekend — proposed **Saturday, Sept 5**
   (afternoon, time TBD), backup **Monday, Sept 7** if enough owners object to Saturday. Keeper
   deadline is the night before the draft, **Friday, Sept 4**, Sleeper-enforced. Keeper rules are
   unchanged from prior seasons (matches the already-implemented `last_round - 1` cost rule, max
   2 consecutive kept seasons, round-0 cost ineligible — see `PROJECT_PLAN.md` §3), and there are
   no other rule/league changes for 2026. Draft order is Sleeper-randomized in-app. See
   `decisions/2026/2026-08-04-draft-2026-league-launch-dates.md` for the full write-up and
   `wiki/league/season-2026.md` for the quick-reference version. This gives Phases E/F below a firm
   window: mock-draft/research prep has roughly four weeks (now → Sept 4-5), and the live-draft
   Routine (Phase H) needs to be ready for a Saturday-afternoon session, not a weekday one.
   **Update 2026-08-08:** the whole schedule moved up one week — draft is now **Saturday, Aug 29**
   (backup Monday, Aug 31), keeper deadline **Friday, Aug 28**. Week 1 opener (Sept 9) is
   unchanged. See `decisions/2026/2026-08-08-draft-draft-2026-schedule-moved-up-week.md` and the
   refreshed `wiki/league/season-2026.md`.
2. ~~Keeper cost rule is unknown~~ **Resolved.** Confirmed with Brad and verified against the
   real 2025 draft data: a kept player costs `last_round - 1` (the round they were last drafted
   or kept at, minus one). Round 1 is a valid keeper cost; only a computed cost of round 0 is
   invalid (i.e. the player was drafted or kept at round 1 last year — that player can't be kept
   this year at all). A player can be kept for at most 2 consecutive seasons before returning to
   the open pool.
   Also corrected while checking this: the draft itself is a **full 15-round snake draft**, not
   the 3-round supplemental draft assumed in the first pass of `PROJECT_PLAN.md` — confirmed from
   the real 2025 draft object (`type: snake`, `rounds: 15`, 180 picks, 17 of them flagged
   `is_keeper: true` at their computed round). See `PROJECT_PLAN.md` §3 for the full writeup.
   Phase E below reflects this correction.
3. **100% test coverage, enforced in CI — not an assumption anymore, an explicit requirement**
   (see item 7). Includes fixture-recorded Sleeper/nflverse responses for I/O-heavy commands, not
   just pure computation. Rationale unchanged: this codebase is meant to be edited by the LLM all
   season (`PROJECT_PLAN.md` §4); tests are what make that safe without a human reviewing every
   diff.
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
7. **Code quality standards adopted wholesale, not an assumption:** `uv`, `ty` (type checking),
   `ruff check` + `ruff format --check` (both default rule sets, unmodified) all enforced in CI;
   100% test coverage (lines + branches) enforced in CI, narrow `# pragma: no cover` at specific
   call sites for the legitimate can't/shouldn't-cover cases; functional style (plain functions +
   `@dataclass`/`Enum`, no other custom classes, no inheritance); tagged unions + `match` for
   state modeling instead of optional-field bags; **the only two decorators used anywhere in this
   codebase are `@dataclass` and `@contextmanager`** — notably no `@pytest.fixture`/
   `@pytest.mark.parametrize`, tests are plain functions with plain helper functions for shared
   setup; no monkeypatching or other dynamic magic anywhere — a real local mock HTTP server
   (§10.4) instead of a faked-out transport for HTTP tests, dependency injection (explicit
   parameters) elsewhere. Full detail in `PROJECT_PLAN.md` §10. This changed two defaults from
   the first pass of this plan: `typer` → stdlib `argparse` (decorator/introspection-based CLI
   registration is exactly the magic being avoided), and `pydantic` → `dataclasses` + `TypedDict`
   + hand-written boundary parsers (same reasoning).
   Every phase below (repo layout, command tables, module names) has been updated to match —
   noting it here once instead of re-deriving the rationale in each phase.

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
│   │   ├── main.py                # builds the argparse.ArgumentParser tree, dispatches to plain functions
│   │   ├── config.py              # repo-root discovery, path constants, no env-based secrets needed
│   │   ├── models/                # frozen @dataclass domain types + TypedDicts for raw external JSON
│   │   │   ├── sleeper.py         # League, Roster, User, Player, Transaction, Draft, DraftPick (+ *Raw TypedDicts, parse_* functions)
│   │   │   ├── stats.py           # weekly stat row, snap row, injury row
│   │   │   ├── vorp.py            # per-player VORP result
│   │   │   └── recommendation.py  # Recommendation = TradeRecommendation | WaiverRecommendation | DraftRecommendation | FreeAgentRecommendation | KeeperRecommendation (tagged union, see PROJECT_PLAN.md §10.2)
│   │   ├── sleeper_client/
│   │   │   ├── http.py            # get_json(url) -> dict; SLEEPER_BASE_URL constant; each resource function below takes base_url: str = SLEEPER_BASE_URL as its test seam (see tests/support/mock_http.py)
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
│       ├── support/
│       │   └── mock_http.py       # Request/Response dataclasses + mock_http_server() context manager, see PROJECT_PLAN.md §10.4
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
└── .claude/skills/                # draft.md, trades.md, waivers.md, free-agents.md, news-research.md
                                    # (authored in Phases E/F/G/C respectively) + code-review.md (Phase A)
```

## 2. Phase A — Foundations

Nothing else can be built until this exists. No CLI features yet — just the scaffolding that
every later phase depends on.

**Tasks**

- Initialize `uv` project under `cli/`: `pyproject.toml` (Python 3.12+, runtime deps: `polars`,
  `requests`, `nfl_data_py`, `pyyaml`; dev deps: `pytest`, `pytest-cov`, `ruff`, `ty`). No
  `typer`, no `pydantic`, and deliberately no HTTP-mocking library (`respx`/`responses`/etc.) —
  those work by intercepting `requests` under the hood, which is exactly the kind of
  monkeypatching this project bans; see `tests/support/mock_http.py` below instead.
- No `[tool.ruff]` section in `pyproject.toml` beyond what's needed to point ruff at `src/`/
  `tests/` — no `select`/`ignore` customization, per `PROJECT_PLAN.md` §10.1.
- `config.py`: repo-root discovery (walk up from cwd looking for a marker like `.git` or
  `PROJECT_PLAN.md`), and path constants for `data/`, `wiki/`, `decisions/`. No secrets/env vars
  needed per assumption §0.6 — keep this file boring on purpose. Plain functions, no config
  class/singleton — callers that need paths take them as explicit parameters (or call the
  discovery function directly), per §10.2's "thread parameters through the call stack" rule.
- **`tests/support/mock_http.py`**: the `Request`/`Response` dataclasses + `mock_http_server()`
  context manager specified in full in `PROJECT_PLAN.md` §10.4 — build this early in Phase A,
  before `sleeper_client`, since every HTTP-touching test from here on depends on it. Takes a
  single `Callable[[Request], Response]` handler, wraps stdlib `http.server`, yields the running
  server's base URL as a plain string.
- `sleeper_client/http.py`: `get_json(url: str) -> dict` — a plain function calling `requests.get`
  directly (no injected transport parameter needed; the test seam is the URL, not the transport
  — see below). Retry-with-backoff on 429/5xx lives here too (our call volume is low enough that
  Sleeper's 1000 req/min ceiling is very unlikely to matter — this is a correctness/robustness
  measure, not real rate limiting); the backoff's `sleep` is itself an explicit injectable
  parameter (`sleep: Callable[[float], None] = time.sleep`) purely so retry tests don't have to
  wait through real delays — this is normal parameter-threading, not the same thing as the
  banned transport-mocking pattern, since it's not standing in for the thing being tested.
  `SLEEPER_BASE_URL = "https://api.sleeper.app/v1"` lives here too; every resource-specific
  function in `league.py`/`players.py`/`draft.py`/`trending.py` takes `base_url: str =
  SLEEPER_BASE_URL`, which tests override to a `mock_http_server(...)`-provided URL.
- `storage/parquet_store.py`: `read_table(path) -> polars.DataFrame`, `write_table(df, path)`,
  each table versioned with a `schema_version` column or sidecar so a future schema change
  doesn't silently corrupt old data — reader should fail loudly (a clear exception) on an
  unexpected schema rather than guess.
- `wiki_tools/frontmatter.py`: parse/write YAML frontmatter + body for a markdown wiki page as
  plain functions over `@dataclass` types; helper to append a dated entry to a page's "News"
  section (used by both the news-research skill's instructions and — if useful — a small CLI
  assist, see Phase C).
- **CI** (`.github/workflows/ci.yml`), every step a hard gate on push/PR to the working branch:
  1. `uv sync --locked` (fails if `uv.lock` is stale relative to `pyproject.toml`).
  2. `ruff check` (default rules, unmodified).
  3. `ruff format --check` (default settings, unmodified).
  4. `ty check` (zero errors).
  5. `pytest --cov=sleeper_agent --cov-report=term-missing --cov-fail-under=100`, with
     `[tool.coverage.run] branch = true` set in `pyproject.toml` so the 100% threshold covers
     branches (and, implicitly, functions — an uncalled function's lines show as uncovered) as
     well as lines, per `PROJECT_PLAN.md` §10.1.
  6. A small custom script (e.g. `scripts/check_no_magic.py`, plain Python, no new dependency)
     that greps `cli/src` and `cli/tests` for `unittest.mock`, `monkeypatch`, `setattr(`,
     `getattr(` (beyond a short allow-list of genuinely safe uses, e.g. `getattr(x, name,
     default)` on a known-safe object), `exec(`, `eval(` — fails the build if any appear outside
     a documented exception. Backstops §10.1/§10.2's "no dynamic magic" rule mechanically for the
     literal cases; doesn't replace `code-review.md` for the subtler ones.
- `tests/fixtures/`: record a handful of real Sleeper responses (league object, rosters, players
  dictionary excerpt, a draft's picks) and a small nflverse weekly-stats slice, checked in as
  static JSON/parquet files. For Sleeper fixtures, tests load the JSON and have their
  `mock_http_server` handler return it as a `Response` body for the expected path — the fixture
  data flows through a real HTTP round-trip, never patched into `requests` at runtime. For
  nflverse, since there's no mock-server seam available (§10.4's closing note), fixtures are
  loaded directly as the input to the transformation logic under test, bypassing the one
  `# pragma: no cover`-marked `nfl_data_py` call site entirely.
- **Author `.claude/skills/code-review.md` now**, before any real feature code exists, so it's
  available to review Phase B's code from the start rather than being bolted on later. Content
  outline: restate the mechanically-uncheckable parts of `PROJECT_PLAN.md` §10.2 (functional
  style over classes/inheritance, tagged unions + `match`, no dynamic magic, explicit parameter
  threading) as a concrete review checklist, and instruct that it runs before committing any
  change touching `cli/` — not just periodically.

**Definition of done:** `uv run sleeper-agent --help` shows an empty-but-structured CLI;
`mock_http_server` has at least one real test proving it round-trips a scripted response
correctly (server starts, serves the handler's response, shuts down cleanly); `uv run pytest
--cov-fail-under=100` passes (even if trivially, on a smoke test — coverage of an almost-empty
codebase is not a meaningful signal yet, but the gate itself must already be wired and green);
`ruff check`, `ruff format --check`, and `ty check` are all clean; CI is green on a throwaway PR;
`code-review.md` v1 exists.

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

Implements `PROJECT_PLAN.md` §6.5, plus `draft.md` skill. The keeper-cost rule is resolved (see
§0.2) — this phase is no longer blocked on outside input, just on building the (nontrivial)
multi-season history walk the cost formula needs.

### Keeper eligibility & cost algorithm

For each player on the roster in question:

1. Find their most recent draft pick record. This requires walking the league's season chain
   backward via `previous_league_id` (already synced per-season under `data/sleeper/drafts/`)
   until the player's most recent `draft_id`/`round`/`is_keeper` is found — a player who's been
   on the roster multiple years may not have been drafted *this* franchise's most recent draft at
   all if they were kept every year since acquisition, so this needs to walk back far enough to
   find the actual most recent pick record, not just check last season.
2. Count consecutive prior seasons where that same player was kept (`is_keeper: true`) for this
   roster, walking back until either a non-keeper (live) pick is hit or the chain ends.
3. Apply the rule:
   - If already kept for **2 consecutive seasons**, not eligible — returns to the open pool.
   - Else, `cost = last_round - 1`. **`cost == 0` is the only invalid case** (i.e. `last_round
     == 1`: drafted or kept at round 1 last year) — not `cost <= 1`. A player last drafted/kept
     at round 2 has `cost = 1` and **is** eligible, at a round-1 keeper cost.
   - Else, eligible to keep at `cost`.

This is genuinely the most involved piece of data-plumbing in Phase 1 (multi-season joins across
what Sleeper treats as entirely separate league objects) and deserves its own well-tested module
(`sleeper_client/draft.py` gains a `keeper_history(player_id, roster_id, as_of_season)` function)
rather than being inlined into the `draft keepers` command.

| Command | Behavior |
|---|---|
| `draft keepers [--roster-id N \| --me]` | For the given roster, lists each player with: keeper-eligible (y/n), cost if eligible, and value/VORP — so the recommendation is "keep these 2 (or fewer) at this cost" ranked by value-per-cost, not just raw value. Ineligible players are shown too (so it's visible *why* a good player isn't a keeper option) but excluded from the ranking. |
| `draft board [--league-id ID] [--rounds N] [--watch]` | On-demand best-available-by-value view across the full 15-round draft: cross-references `data/vorp` + `value rank` against already-drafted/kept players (via the draft's public picks endpoint, no auth needed, same approach as `bspaulding/nfl-vorp`'s `vorp-draft-cli.ts`), correctly treating pre-filled `is_keeper: true` picks as off the board from the start rather than waiting to see them "picked." `--watch` polls every ~30s and re-renders, and (if run as part of a Routine rather than interactively) writes/updates a running `decisions/.../<date>-draft-live.md` entry each time the board changes meaningfully — this is what makes both draft-day operating modes (interactive or semi-autonomous, see §0.4) work off the same command. |

**Tests:** `keeper_history` tested against a synthetic multi-season fixture chain covering all
outcomes: never kept before, kept 1 consecutive year (eligible again), kept 2 consecutive years
already (ineligible regardless of round), last_round == 2 (eligible, cost == 1), and last_round
== 1 (ineligible, cost would be 0) — the last two specifically to pin down that round 1 is a
valid keeper cost and only round 0 is not. `draft board` filtering-out-drafted-and-kept-players
logic tested against a fixture draft with a partial set of live picks plus pre-filled keeper
picks.

**Skill: `.claude/skills/draft.md`** — outline: how to choose which ≤2 keepers to lock in
(value-per-cost, not just raw value — a cheap round-9 keeper can beat an expensive round-2 one);
full-roster snake-draft strategy for the ~13 live-drafted spots once keepers are set (this *is*
close to a full startup draft each year, unlike the smaller supplemental-round assumption from
the first pass of this plan); how to handle a player who just became keeper-ineligible (2-year
cap hit) that Brad may still want to redraft normally.

**Definition of done:** `draft board` correctly tracks a real completed draft when pointed at
the 2025 draft_id as a replay test, including correctly excluding all 17 real `is_keeper` picks
from the "available" list from the start; `keeper_history`/`draft keepers` reproduces the real,
known 2025 keeper picks (round and eligibility) as a validation check before trusting it for a
real 2026 decision; `draft.md` v1 is written.

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

**Status (2026-07-26) — deviation note:** All three cadence Routines were created via
`create_trigger` with `create_new_session_on_fire=true`, each with a self-contained prompt that
pulls `main`, no-ops gracefully if the CLI isn't merged yet, and runs the relevant command
sequence:

1. `sleeper-agent: weekly stats/VORP sync` — Tuesdays 13:00 UTC — `stats sync` → `stats vorp` →
   `wiki stale` → light opportunistic news pass.
2. `sleeper-agent: waiver window reminder` — Mondays 13:00 UTC — `waiver recommend` →
   judgment-gated `decisions new --kind waiver`.
3. `sleeper-agent: trade scouting` — Wednesdays 13:00 UTC — `trade propose --all` →
   judgment-gated `decisions new --kind trade`; starts at weekly/low frequency per the plan,
   with the prompt itself instructing the fired session to ramp urgency as the real
   `trade_deadline` week approaches rather than hardcoding a second higher-frequency schedule.

Deviation from the DoD as written: **none of the three have fired successfully yet**, and can't
until this branch's work is merged to `main` — `create_new_session_on_fire=true` sessions check
out `main` fresh on each firing, which doesn't yet contain any of this implementation (it's all
on `claude/implementation-plan-execution-r9vrb1`, unmerged). Each Routine's prompt defensively
checks for the CLI's presence and no-ops with a clear message if it's missing, so firing before
merge is safe (no crash, no bad state) but not a genuine successful run. This DoD item is
explicitly a follow-up blocked on a human merging the PR this session opens — outside this
session's authorized scope (only "open a PR," never merge). Once merged, the next scheduled
firing of each Routine (or a manual `fire_trigger` for immediate verification) will be the real
first successful run.

The draft-day one-shot Routine remains **deferred** as the plan's own §0.1 anticipates — no real
2026 draft date has been announced by the commissioner yet. Create it (via `create_trigger` with
`run_once_at` set to the draft window) once that date is known.

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

- [x] All CI gates green on the working branch: `uv sync --locked`, `ruff check`,
      `ruff format --check`, `ty check`, `pytest --cov-fail-under=100`, and the no-dynamic-magic
      grep check (`PROJECT_PLAN.md` §10.1). Verified locally 2026-07-26: 198 tests, 100%
      line+branch coverage, all gates clean.
- [x] `code-review.md` exists and has actually been used to review at least one real change. Its
      checklist (functional style, tagged unions, no dynamic magic, dependency injection) was
      applied continuously while writing every phase's code, not run as a separate one-off pass —
      it's what caught things like the `dict`/`Mapping` invariance issue in draft.py and drove the
      match-statement exhaustiveness pattern used throughout.
- [x] `sleeper league resolve` correctly finds/falls back for the current season, tested against
      the real "2026 doesn't exist yet" state. Confirmed during Phase B: resolving season 2026
      against the real league returns `LeagueResolvedViaFallback`, walking back to the real 2025
      league.
- [x] `stats vorp` output has been sanity-checked against known real 2025 results. Substituted
      season 2024 for this check (see Phase E/§ deviation notes below) since nflverse hadn't
      published 2025 weekly stats yet as of this session (verified via direct 404 vs. 2024's
      normal redirect) — the code itself is fully season-parameterized, so this becomes a
      one-flag rerun once 2025 data is published.
- [x] Every rostered player and all 32 NFL teams have a scaffolded wiki page (`wiki scaffold`).
      169 real player pages + 32 NFL team pages exist under `wiki/`.
- [x] At least one full sync → analyze → `decisions new` → commit/push cycle has been run
      end-to-end, for real, not just in tests. See `decisions/2026/2026-07-26-freeagent-monitor-
      diggs-free-agency.md`, produced from a real `stats sync` → `value` → `freeagent recommend`
      pass against live data and committed/pushed.
- [x] All five skills (`draft.md`, `trades.md`, `waivers.md`, `free-agents.md`,
      `news-research.md`) exist in v1 form.
- [x] `draft keepers` reproduces the real, known 2025 keeper picks (round + eligibility) as a
      validation check before the keeper-cost algorithm (§6) is trusted for a real 2026 decision.
      All 17 real 2025 keeper picks matched exactly after the undrafted-default fix (Phase E).
- [ ] Weekly stats/VORP Routine and waiver-window Routine are live and have fired successfully
      at least once. **Blocked, not done:** both Routines (plus trade-scouting) are created
      (Phase H) but can't fire successfully until this PR merges to `main` — a human action
      outside this session's scope. First real firing happens on the next scheduled run after
      merge.
- [x] Draft-day Routine is scheduled once the real draft date is known. **Done 2026-08-04:** the
      commissioner's league-launch email set Saturday, Sept 5 (afternoon, time TBD) as the draft,
      backup Monday, Sept 7. One-shot Routine `sleeper-agent: draft day` created for Saturday
      Sept 5, 17:00 UTC (~1pm ET) as a placeholder time — **needs `update_trigger`'d to the real
      start time once Aaron confirms it** — running `draft board --watch` against the real
      league's draft. A second one-shot Routine, `sleeper-agent: pre-draft prep`, was also
      created for Wednesday Sept 2 to do a deeper research pass and refresh the value/tier list
      ahead of the keeper deadline. **Updated 2026-08-08:** schedule moved up a week — both
      Routines re-scheduled (`draft day` → Saturday Aug 29, 17:00 UTC placeholder;
      `pre-draft prep` → Wednesday Aug 26, 13:00 UTC) via `update_trigger`. Start time is still
      TBD, so both fire times remain placeholders pending confirmation.
- [x] Real 2026 keeper deadline / draft date / week-1 date have replaced the placeholders in §0.1
      everywhere they matter (Routine schedules especially). **Done 2026-08-04**, from the same
      email: keeper deadline Fri Sept 4, draft Sat Sept 5 (backup Mon Sept 7), week 1 opener Wed
      Sept 9. See `decisions/2026/2026-08-04-draft-2026-league-launch-dates.md` and
      `wiki/league/season-2026.md`. **Updated 2026-08-08:** schedule moved up one week — keeper
      deadline Fri Aug 28, draft Sat Aug 29 (backup Mon Aug 31), week 1 opener unchanged (Wed
      Sept 9). See `decisions/2026/2026-08-08-draft-draft-2026-schedule-moved-up-week.md`.
