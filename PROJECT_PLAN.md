# sleeper-agent — Project Plan / Living Spec

Status: **draft v1** — written from an initial architecture interview (2026-07-25). This
document is meant to evolve as decisions get revisited during implementation. When something
here turns out to be wrong once we start building, update this file in the same PR/commit that
proves it wrong — don't let it drift out of sync with reality.

## 1. Vision

Run an autonomously-managed Sleeper fantasy football team, where:

- A **Python CLI** handles the outside-world calls that need to be structured and reproducible
  (Sleeper's API, stats providers). It fetches data, computes analyses, and (once write access
  exists) will execute actions. It is deterministic, testable, versioned code. News/context
  research is the one exception — see §5.4 — and is done by the LLM directly, not the CLI.
- An **LLM wiki** (markdown, git-tracked) is the team's long-term memory: player notes,
  team-building philosophy, past decisions and their reasoning, league dynamics, injury/news
  context. It's what the LLM reads before making a judgment call the CLI can't make on its own
  (the CLI can tell you a player's VORP; only the LLM+wiki can tell you "this GM overpays for
  RBs after their starter got hurt last year").
- **Claude Code**, running as scheduled/triggered sessions, is the agent. It uses the CLI (via
  Bash) as its hands, the wiki as its memory, and a set of **skills** as its playbooks for
  recurring judgment calls (drafting, trades, waivers, free agency).
- Every decision the agent makes is written to a **decision log** in the repo and pushed —
  the git history of that log is the audit trail, in lieu of a notification system (deferred,
  see §9).

## 2. Scope & phasing

Sleeper's official API is **read-only** — there is no documented (or, as far as public projects
show, reliably-supported undocumented) way to submit trades, waiver claims, roster moves, or
draft picks through it. Every automation project that does this reverse-engineers Sleeper's
internal web/app API from a logged-in session, or drives the UI with browser automation. Both
carry real risk (ToS, breakage on any Sleeper internal change, account flags).

**Decision:** ship this as a phased project.

- **Phase 1 (this spec's primary target): read + analyze + recommend + log.** The CLI only
  reads from Sleeper and other sources. The agent produces recommendations (draft picks, trade
  offers to make/accept/reject, waiver bids, add/drop moves) and writes them, with full
  reasoning, to the decision log and wiki. A human (Brad) reads the log and executes the action
  manually in the Sleeper app.
- **Phase 2 (future, explicitly out of scope for now): write access.** Once we're comfortable
  with the mechanism (reverse-engineered internal API vs. browser automation) and the risk,
  wire up real execution so recommendations marked "auto-executable" by policy run without a
  human in the loop. The acceptance criteria below that imply live writes ("place waiver bids",
  "add/drop players", "make draft picks", "respond to trade offers") are Phase 1 in
  *recommendation* form and Phase 2 in *execution* form. Don't build Phase 2 speculatively —
  design the recommendation objects (§6) so that "execute this" is a thin adapter later, not a
  rewrite.
- **Notifications are deferred.** No email/Signal/push integration for now. The decision log
  (§7) is the interface — Brad checks it, or a future phase adds notifications on top without
  changing how decisions are produced.

## 3. League context (grounding, not hypothetical)

Our user is Sleeper user **`yellldarb`** (`user_id: 469022928223072256`), roster_id `5` in the
league below. All Sleeper reads/writes are scoped to this user's team.

Pulled directly from Sleeper for league `1180391690551980032` ("Only Gold"), the 2025-season
instance of `yellldarb`'s keeper league:

- **12-team keeper league**, `max_keepers: 2`. League IDs change every season in Sleeper
  (`previous_league_id` chains them together) — **never hardcode a league ID**; resolve the
  current season's league ID at runtime via `/user/<user_id>/leagues/nfl/<season>` (see §6.1).
  As of 2026-07-25 the 2025 league is `status: complete` and **no 2026 league exists yet** —
  the commissioner hasn't rolled it over. Resolution logic needs to handle "current season's
  league doesn't exist yet" as a real, expected state (fall back to the most recent prior
  season's league until the new one appears), not an error.
- **`best_ball: 1` is set** — this is *not* Sleeper's standalone draft-only Best Ball format.
  It's a regular league (waivers, trades, keepers, in-season transactions all enabled) where
  Sleeper auto-selects the highest-scoring legal lineup from the roster each week instead of
  requiring manual start/sit. **Practical effect on this project: we do not need to build
  weekly start/sit optimization** — Sleeper already does it. Our value-add is entirely in
  *roster construction*: who's on the 15-man roster at all (draft, trade, waiver, free agency),
  not who starts each week. Any "best ball scoring" language in analysis should mean "assume
  the optimal lineup is auto-selected" when projecting a roster's weekly output.
- **FAAB waivers** (`waiver_type: 2`), budget 100/season, waivers process on a 2-day clear
  cycle, weekly waiver day is Tuesday (`waiver_day_of_week: 2`).
- **Trades**: enabled, trade deadline week 11, 2-day review period, 6 veto votes needed to
  overturn, draft pick trading enabled.
- **Draft**: a full 15-round snake draft every season (confirmed from the actual 2025 draft
  object: `type: snake`, `rounds: 15`, 180 total picks = 12 teams × 15 rounds — the league
  setting `draft_rounds: 3` seen in `/league/<id>` does **not** reflect what actually runs and
  should be ignored/treated as stale). Up to 2 keepers per team are auto-inserted into the draft
  as picks flagged `is_keeper: true` at a pre-computed round (17 such picks in the 2025 draft);
  every other roster spot is drafted live in the normal snake order. **Keeper cost rule**
  (confirmed with Brad, not in Sleeper's API): a kept player costs one round earlier than the
  round they were last drafted or kept at (`cost = last_round - 1`). **Round 1 is a valid
  keeper cost** — e.g. drafted round 2 last year → keeper cost round 1 this year is fine. Only
  `cost = 0` (i.e. the player was drafted *or* kept at round 1 last year) is invalid: that player
  is **not keeper-eligible** at all this year (must be drafted normally by whoever wants them,
  including their current owner). Separately, a player can be kept this way for **at most 2
  consecutive seasons**, after which they lose keeper eligibility and return to the open draft
  pool. Computing this requires walking the draft history across seasons via `previous_league_id`
  (see §6.5).
- **Roster** (15 total): `QB, RB, RB, WR, WR, TE, FLEX, FLEX, DEF, BN×6`. No kicker in the
  starting lineup at all — don't spend analysis effort on kickers.
- **Scoring**: full PPR (`rec: 1.0`), standard yardage/TD rates (pass 0.04/yd + 4/TD, rush &
  rec 0.1/yd + 6/TD), 2PT variants all count, and a fairly complete IDP-style team defense
  scoring table (points-allowed tiers, sacks, INTs, fumble recoveries, safeties, blocked kicks,
  special-teams TDs). No bonus thresholds are enabled (all `bonus_*` fields are 0).

This means the actual Sleeper scoring settings for the *current* league instance must always be
pulled live and fed into the fantasy-points calculation — never assume standard/half-PPR
defaults, since this league's settings are already known to matter (full PPR, no K, no bonus
thresholds).

## 4. Architecture overview

```
sleeper-agent/
├── cli/                  # Python CLI — all external I/O and computation lives here
├── data/                 # Parquet data store (git-tracked or git-ignored, see §5.2)
├── wiki/                 # Markdown wiki — narrative knowledge, LLM-editable
├── decisions/            # Decision log — append-only record of agent decisions
├── .claude/skills/       # Claude Code skills — draft/trade/waiver/free-agent playbooks
└── PROJECT_PLAN.md       # this file
```

- The **CLI** is the only code that calls Sleeper, nflverse, or news sources, and the only code
  that does numeric analysis (VORP, projections, trade value). It's a normal Python package:
  testable, typed, and the thing Claude Code is expected to read and modify when a capability
  needs fixing or extending ("the LLM agent is allowed to edit that code as needed").
- The **agent** is Claude Code itself — not a separate standalone process. Scheduled or
  triggered sessions (via Claude Code Routines, see §8) invoke CLI subcommands through Bash,
  read/write the wiki through normal file tools, and follow skills for judgment calls. This
  avoids building a second agent runtime (Claude Agent SDK / raw Anthropic API loop) — we get
  tool use, memory, and instruction-following from Claude Code directly, at the cost of being
  tied to Claude Code as the execution substrate. Revisit this only if Claude Code Routines
  prove insufficient for the scheduling/latency needs.
- **Custom tools** for the LLM = CLI subcommands, invoked as ordinary shell commands. No MCP
  server is needed for Phase 1 since Claude Code already has Bash; an MCP wrapper is only worth
  building if we later want a non-Claude-Code caller.

## 5. Data layer

### 5.1 Sources

| Source | What | Access |
|---|---|---|
| Sleeper API | league/user/roster/matchup/transaction/draft/player data | public, read-only, no auth, keep under 1000 req/min |
| [nflverse](https://github.com/nflverse) / `nfl_data_py` | play-by-play, weekly stats, snap counts, next-gen stats, rosters, schedules, injuries | free, Python-native |
| News/context (injuries, beat reports, transactions) | narrative context for wiki player notes | **not a CLI scraper** — the LLM fetches this itself via WebSearch/WebFetch during normal runs, guided by a skill (see §5.4, §9) |

Use "any and all free metrics we can get" as the working principle — the CLI should be able to
absorb new free data sources over time without a redesign; each source gets its own fetch
module and lands in its own data table (§5.2), joined by a canonical player ID (Sleeper's
`player_id`, cross-walked to other sources' IDs where needed — nflverse ships crosswalk tables
for this).

### 5.2 Storage: Parquet

Raw and derived tabular data (stats, rosters, transactions, VORP outputs, projections) live as
**Parquet** files under `data/`, not the wiki. Suggested layout:

```
data/
├── sleeper/
│   ├── players.parquet            # full player dictionary, refreshed periodically
│   ├── rosters/<season>.parquet
│   ├── transactions/<season>.parquet
│   └── drafts/<season>.parquet
├── stats/
│   ├── weekly/<season>.parquet    # nflverse weekly stats
│   └── snaps/<season>.parquet
└── vorp/<season>.parquet          # computed VORP, see §6.2
```

News is not part of this store — see §5.4.

Read/write with `polars` or `pandas` (pick one and standardize — recommend `polars`, faster and
has first-class Parquet support). Decide at implementation time whether `data/` is git-tracked
(simplest, gives free history/diffing of stats over time, but repo grows) or git-ignored with a
separate sync step — leaning toward **git-tracked**, consistent with "commit the decision log
and push" as the project's general pattern of using git as the system of record.

### 5.3 Wiki

Markdown under `wiki/`, with YAML frontmatter for structured fields that are cheap to keep
inline (e.g. a player note's `sleeper_id`), but the wiki does **not** duplicate the parquet
tables — it holds reasoning, not raw numbers:

```
wiki/
├── players/<sleeper_id>-<slug>.md      # notes, injury history narrative, "how we value him and why"
├── nfl-teams/<team_code>.md            # NFL team pages: scheme/coaching, depth chart, the DEF unit itself
├── team/roster-philosophy.md           # our fantasy team's strategy (singular "team" = us)
├── team/keeper-strategy.md
├── league/opponents/<roster_id>.md     # scouting notes on other GMs' tendencies
├── decisions.md                        # index into decisions/, see §7
└── strategy/best-ball-scoring-notes.md # how auto-lineup-optimization changes value calculus
```

Note the naming split: `team/` (singular) is our own fantasy team; `nfl-teams/` (plural, one per
NFL team code) is real-world team context. `nfl-teams/` doubles as the "player page" for DEF —
Sleeper rosters defenses by team code (e.g. `BUF`), not by individual player, so a DEF slot's
notes/news live on its team page rather than a separate player page.

The LLM is expected to read and update these files as part of its normal reasoning loop (this
is the "living memory" the acceptance criteria calls for), not just the CLI.

### 5.4 News research (LLM-driven, not scraped)

Building and maintaining a scraper per news source is real ongoing maintenance for a
low-structure payload (a paragraph of context, not a row of numbers). Instead: the LLM
researches news itself, live, using WebSearch/WebFetch during its normal skill-driven runs, and
writes what it finds directly into the relevant `wiki/players/*.md` and/or `wiki/nfl-teams/*.md`
pages (e.g. an injury update goes on the player page; a coaching/scheme change goes on the team
page and is worth a note on that team's key players too). No `data/news/` table, no scraper code
to maintain, no dedicated CLI command.

The risk this gives up is structure — a scraper pipeline guarantees consistent coverage,
cadence, and a queryable table; ad hoc LLM research doesn't, by default. That gap gets closed
by a **skill** (`.claude/skills/news-research.md`, see §9), not code, covering things like:

- which kinds of sources to prioritize (team injury reports, beat reporters, official
  transaction wires) over low-quality aggregators;
- a consistent filing convention — append a dated, tagged entry to a "News" section on the
  relevant page(s), and **always include a link to the source article**, not just a paraphrase:
  `- YYYY-MM-DD [injury|depth-chart|trade|transaction] <note> ([source](<url>))`. Frontmatter
  should record `last_researched: <date>` so a run can tell whether a page's news is stale;
- linking, not duplicating, across pages — if one article is relevant to a player and their
  team (or multiple players), link it from each relevant page rather than copying the summary
  around; the article itself is the source of truth, wiki entries are pointers plus a one-line
  takeaway;
- a check-before-you-write step — skim the page's existing News section (including already-
  linked article URLs) first so repeat runs don't re-research or duplicate what's already there;
- when to bother at all — two modes: a **targeted lookup** always for rostered/targeted players
  and their teams ahead of a lineup-affecting decision, and a **full sweep** (periodic, or on
  request) that is scoped by *time* rather than by player — tracked via a `last_swept` checkpoint
  in `wiki/news-sources.md` — so it catches news about anyone newsworthy since the last scan, not
  just players who already have a wiki page. (Changed 2026-08-15: full sweeps were originally
  meant to iterate `wiki stale`-flagged pages, i.e. player-scoped; that missed anyone without an
  existing page, so the checkpoint moved to source/time instead. See
  `.claude/skills/news-research.md` §1 for the mechanics.)

## 6. Analysis & CLI capabilities

All entry points live in the Python CLI (see §10.3 for the concrete stack: `argparse`,
`dataclasses`, `pytest`). Proposed command groups:

### 6.1 `sleeper` — league/team data

Underlying client functions (`fetch_league`, `fetch_rosters`, etc.) each take an explicit
`base_url: str = SLEEPER_BASE_URL` parameter — this is the test seam described in §10.4 (tests
point it at a local mock server instead of injecting a fake transport callable).

- `sleeper league resolve` — find the current season's league ID by walking forward/back the
  `previous_league_id` chain or querying `/user/<user_id>/leagues/nfl/<season>`; never hardcode.
- `sleeper league sync` — pull league settings, scoring settings, rosters, users, matchups,
  transactions, draft picks into `data/sleeper/*.parquet`.
- `sleeper players sync` — refresh the full player dictionary (large, Sleeper recommends
  caching this and only refreshing ~daily).

### 6.2 `stats` — external stats ingestion

- `stats sync --season <year>` — pull nflverse weekly stats, snaps, schedules into
  `data/stats/`.
- `stats vorp --season <year>` — port the VORP methodology from `bspaulding/nfl-vorp`:
  fantasy points computed from raw stats using **this league's live scoring settings** (not a
  hardcoded scoring table — the old project hardcoded scoring; this one must not, since we
  already know this league's settings are non-default), replacement level derived from
  `roster_positions` (2 RB + 2 WR + 2 FLEX split, no K, single DEF) and league size (12), VORP =
  player points − replacement level, both season-total and per-game.

### 6.3 `value` — player valuation

- Combine VORP with trend signals (recent usage, snap share trajectory, injury status, news
  sentiment/context from the wiki) into a player value score. This is the "combination of
  metrics" acceptance criterion — start with VORP as the quantitative backbone and let the LLM
  layer qualitative wiki context on top rather than trying to encode everything numerically.

### 6.4 `trade` — trade tooling

- `trade evaluate --offer <...>` — given a specific offer (players/picks each side gives),
  return a structured value comparison (VORP delta, positional need delta for both rosters).
  Consumed by the LLM to decide accept/reject/counter; the LLM's reasoning + final call goes to
  the decision log, not just the raw numbers.
- `trade propose` — scan the league for value-imbalanced rosters (positional surplus/need
  mismatches) and generate candidate trade offers worth considering. Output is a ranked list of
  candidate offers with rationale, for the LLM/skill to filter down to what's actually worth
  sending.

### 6.5 `draft` — draft support

- Recommendation: adapt `bspaulding/nfl-vorp`'s `vorp-draft-cli.ts` approach (a live draft board
  that polls Sleeper's public draft-picks endpoint — no auth needed — and ranks available
  players by VORP) into this CLI. It's a full 15-round snake draft (see §3), so the board needs
  to track a whole roster build, not a short supplemental round.
- Also needs a `draft keepers` view: compute each rostered player's keeper eligibility and cost
  per the rule in §3 (`last_round - 1`, ineligible only if that computes to round 0, max 2 consecutive kept
  seasons), which requires walking draft history across seasons via `previous_league_id`.

### 6.6 `waiver` and `freeagent` — in-season roster management

- `waiver recommend` — given current roster needs, trending adds/drops, and FAAB budget
  remaining, produce ranked waiver targets with suggested bid amounts (this league uses FAAB,
  not priority waivers — bid sizing matters).
- `freeagent recommend` — non-FAAB add/drop suggestions (post-waivers, or in leagues without a
  claim period).

### 6.7 Execution adapters (Phase 2, not built now)

Design recommendation objects (`TradeRecommendation`, `WaiverRecommendation`, etc.) as data,
independent of how they get carried out, so a future `sleeper execute <recommendation>` command
can be added without reshaping the analysis code.

## 7. Decision log

Every recommendation the agent acts on (i.e., decides is worth surfacing/recommending) gets
appended to `decisions/`, one entry per decision, then committed and pushed. Suggested format:
one markdown file per decision, `decisions/<season>/<date>-<kind>-<slug>.md`, containing what
was decided, the data/reasoning behind it (linking into `wiki/` and `data/` as needed), and — in
Phase 1 — that it's a *recommendation pending manual execution*, not an action already taken.
`wiki/decisions.md` acts as a running index/summary.

## 8. Scheduling

Claude Code **Routines** (scheduled triggers) wake a session on a cadence or event to run the
relevant CLI commands and reasoning loop. Rough cadence to start from (tune once real usage
shows what's needed):

- Weekly stats/news sync + VORP recompute (e.g. Tuesday, after waivers clear).
- Waiver-window reminder run (before Tuesday waiver processing) — produce FAAB recommendations.
- Trade-deadline-aware trade scouting — more frequent as week 11 approaches, per league's actual
  deadline.
- Draft-day live session for the annual 15-round snake draft.

## 9. Skills

`.claude/skills/` holds the playbooks that inform judgment calls the CLI can't make by itself:

- `draft.md` — how to decide which 2 players to keep (and at what cost) vs. let go back into the
  pool, and full-roster snake-draft strategy for a keeper league where ~2 of 15 spots are
  pre-filled.
- `trades.md` — when to propose, how to evaluate incoming offers, how much to weight VORP vs.
  team-building narrative/roster fit.
- `waivers.md` — FAAB bidding strategy (budget pacing across the season, not just per-bid value).
- `free-agents.md` — add/drop heuristics between waiver periods.
- `news-research.md` — how to fetch and catalog news/injury/transaction context into the wiki
  without a scraper: source prioritization, the dated/linked filing convention onto player and
  NFL-team pages, frontmatter staleness checks, and when it's worth researching at all; see §5.4.
- `code-review.md` — reviews the LLM's own changes to `cli/` against the parts of §10.2 that
  ruff/`ty`/coverage can't mechanically check: functional style over classes/inheritance,
  tagged unions + `match` for state modeling, no dynamic magic, explicit parameter-threading.
  Run this before committing any change that touches `cli/`, not just periodically — see §10.2.
- A meta-loop: periodically (e.g. end of season, or after notably good/bad decisions), the LLM
  is allowed to revise these skill files based on what the decision log shows worked or didn't —
  this is the "skills that update themselves" requirement. Treat skill edits like any other
  change: committed, with a decision-log-style rationale for what changed and why.

## 10. Code quality: tooling & style

The CLI is meant to be edited by the LLM continuously, all season, without a human reviewing
every diff (§1, §4). That only works if the codebase stays genuinely easy to reason about —
these standards exist for that reason, not as style preference for its own sake. Split into
what's mechanically enforced (§10.1, CI fails the build) and what needs judgment (§10.2, the
`code-review.md` skill's job, since no linter can check "is this the right abstraction").

### 10.1 Tooling (CI-enforced, mechanical)

- **Dependency management: `uv`.** `uv.lock` is committed; CI checks the lockfile isn't stale
  (`uv sync --locked` or equivalent) so "works on my machine" drift can't creep in.
- **Type checking: [`ty`](https://github.com/astral-sh/ty).** All code must be fully typed; `ty
  check` runs in CI and must be clean (zero errors) for every change. No `# type: ignore` used to
  paper over a real type error — if `ty` can't be satisfied cleanly, the code is wrong or the
  types need to model reality better (see §10.2 on tagged unions), not suppressed.
- **Linting: `ruff check`, default rule set, unmodified.** No `[tool.ruff.lint]`
  `select`/`ignore` customization in `pyproject.toml` — whatever ruff enables out of the box is
  what we get. CI fails on any violation.
- **Formatting: `ruff format --check`, default settings, unmodified.** CI fails if any file
  isn't already formatted — formatting is never a manual step or a matter of taste here.
- **Coverage: `pytest` + `pytest-cov`, 100% coverage enforced in CI** — lines, branches, and
  functions (`[tool.coverage.run] branch = true` in `pyproject.toml`, `--cov-fail-under=100`).
  This is a hard gate, not a target. There are legitimate cases that can't or shouldn't be
  covered by the automated suite (a third-party call with no test seam, like the `nfl_data_py`
  line in §10.4's closing note; a `match` arm the type system proves exhaustive but Python can't
  express without one; a CLI entrypoint's `if __name__ == "__main__":` guard) — those are handled
  with a specific `# pragma: no cover` **at that exact call site**, never at file/module scope,
  and never as a way to skip testing logic that could reasonably be tested.
- **No monkeypatching/dynamic magic — backstopped by a CI grep-check, not just policy.** A
  small CI step scans `cli/` for `unittest.mock`, `monkeypatch`, `setattr(`, `getattr(` (beyond
  trivial safe uses), `exec(`, and `eval(`, and fails the build if any appear outside an
  explicitly documented, reviewed exception. This catches the literal cases; the subtler
  ones (see §10.2) are the `code-review.md` skill's job, because grep can't tell "clever
  metaprogramming" from "reasonable code" the way a reviewer can.

None of this is exotic — it's the same "make it safe for an LLM to keep editing this all season"
argument that was already the rationale for testing at all. `ty` and `ruff` are both from
Astral, same team as `uv`, so the toolchain stays small and consistent.

### 10.2 Code style (guidance — enforced by the `code-review.md` skill, not a linter)

These are things ruff's default rules and `ty` genuinely cannot check — they're about shape and
architecture, not syntax errors or type mismatches. `code-review.md` (§9) is the mechanism that
keeps them real instead of aspirational.

- **Functional style: prefer plain functions and dataclasses over classes.** A "service" or
  "client" isn't a class with methods and internal state — it's a module of functions that take
  their dependencies as explicit parameters. `@dataclass` (usually `frozen=True`, since
  immutable-by-default fits this style) is the standard way to define a data shape, and that's
  an explicit exception to "avoid classes" — `@dataclass` and `Enum` are the two class forms this
  project uses on purpose, everywhere else defaults to a plain function.
- **Avoid decorators — including in the CLI framework, data-validation choice, and tests.**
  **The only two decorators this project uses are `@dataclass` and `@contextmanager`** (stdlib
  `contextlib` — turns a generator into a context manager without a hand-written class; see
  §10.4's `mock_http_server` for the canonical example). Everything else, including two defaults
  from an earlier pass of this plan, was ruled out and replaced:
  - **CLI framework: stdlib `argparse`, not `typer`.** `typer` registers commands via decorators
    and infers the CLI from function-signature introspection; `argparse` is more boilerplate but
    fully explicit.
  - **Data models: stdlib `dataclasses` for domain types, `TypedDict` for raw external JSON
    shapes, and a hand-written `parse_*` function per external shape, not `pydantic`.** This is
    where "validate at the boundary" still happens (Sleeper/nflverse responses are the untrusted
    input) — it just happens as ordinary, readable, testable Python instead of a decorator/
    metaclass-driven validation library. More code than a `pydantic.BaseModel` would need; that's
    the accepted tradeoff (see "thread parameters..." below).
  - **Tests: plain `pytest` functions, no `@pytest.fixture`, no `@pytest.mark.parametrize`.**
    Shared setup is a plain helper function called explicitly at the top of each test (e.g.
    `make_league(**overrides) -> League`, called as `league = make_league(num_teams=10)`), not a
    fixture pytest injects by matching an argument name — that name-matching *is* the kind of
    dynamic magic this project avoids, not an exception to it. Repeated-case testing is a loop
    over cases inside one test function (calling a shared plain assertion-helper), or multiple
    explicitly-named `test_*` functions — not a `parametrize` decorator generating cases. (Note:
    "fixture" elsewhere in these docs — `tests/fixtures/`, "a fixture DataFrame" — means a static
    recorded test-data file/value, an unrelated, unproblematic use of the word; it's specifically
    pytest's `@fixture` *mechanism* that's avoided.)
  - Standard-library classes used *as libraries* (`argparse.ArgumentParser`, `polars.DataFrame`,
    `pathlib.Path`, and — per §10.4 — `http.server.BaseHTTPRequestHandler`/`HTTPServer`,
    `threading.Thread`) are fine to use — the constraint is on classes/inheritance/decorators we
    write ourselves, not on every class-shaped thing in the stdlib or a library we depend on.
- **Composition over inheritance.** No base classes, no mixins, no ABCs. If two things share
  behavior, extract a function both call, not a shared superclass.
- **Make impossible states impossible.** Prefer `Enum` and tagged unions (a `Union`/`|` of
  distinct `@dataclass` types, matched structurally) over a single type with optional fields and
  a runtime "well actually" invariant. Use `match`/`case` on these as the default control-flow
  tool, not `if`/`elif` chains on a `.kind` string or a bag of nullable fields. Concrete example
  already in this codebase's design — §6.5's keeper-cost result should be modeled as:
  ```python
  @dataclass(frozen=True)
  class KeeperEligible:
      cost_round: int

  @dataclass(frozen=True)
  class KeeperIneligibleMaxYearsReached: pass

  @dataclass(frozen=True)
  class KeeperIneligibleCostBelowRoundOne: pass

  KeeperStatus = KeeperEligible | KeeperIneligibleMaxYearsReached | KeeperIneligibleCostBelowRoundOne
  ```
  instead of `eligible: bool, cost: int | None, reason: str | None` — the tagged-union version
  makes "eligible but no cost" or "ineligible but a cost is present" unrepresentable, rather than
  a bug that has to be caught by convention. The same pattern applies to `Recommendation` (§6.7):
  a union of `TradeRecommendation | WaiverRecommendation | DraftRecommendation |
  FreeAgentRecommendation | KeeperRecommendation`, matched by `match`, not one flexible type with
  a `kind` field and a dozen optional attributes.
- **No monkeypatching, no dynamic magic — thread parameters through the call stack instead,
  even when that makes the diff bigger.** No `unittest.mock.patch`, no `monkeypatch` fixture, no
  reaching into another module's internals at runtime. For HTTP specifically, this means testing
  against a real local server (§10.4), not a faked-out request function — that exercises the
  actual `requests`/HTTP code path (real status codes, real headers, real connection behavior)
  instead of trusting that a hand-rolled fake behaves like the real thing. A bigger, fully-explicit
  diff that's easy to trace beats a smaller one that relies on patching something elsewhere to
  work correctly — this is a deliberate tradeoff, not an oversight, and `code-review.md` should
  push back on anything that takes a shortcut through implicit/global state instead.

### 10.3 Stack summary

- Dependency management: `uv`
- CLI framework: `argparse` (stdlib)
- Data models: `dataclasses` + `TypedDict` + hand-written boundary parsers (no `pydantic`)
- Tabular data: `polars` + Parquet
- Testing: `pytest` + `pytest-cov` (100% line+branch, enforced), plain `test_*` functions with
  no `@pytest.fixture`/`@pytest.mark.parametrize` (plain helper functions instead), a local mock
  HTTP server for external-API tests (§10.4) — no mocking libraries, no faked-out request
  functions
- Type checking: `ty`
- Linting: `ruff check` (default rules)
- Formatting: `ruff format` (default settings)

### 10.4 HTTP testing utility: a real local mock server, not a fake

Sleeper's API is the only external HTTP boundary this project controls the calling code for
(nflverse/`nfl_data_py` is a separate case — see the note at the end of this section). Rather
than inject a fake `get`-like callable to stand in for `requests` (which only tests that our code
calls *something* correctly, not that it behaves correctly against real HTTP), tests spin up a
small, real local HTTP server with a scripted response, and point the client code at it via an
explicit `base_url` parameter — no patching, and the real `requests` code path runs end-to-end.

`cli/tests/support/mock_http.py` — a single reusable utility, function-based, `Request`/
`Response` as plain frozen dataclasses operating on raw `bytes` (callers encode/decode UTF-8
explicitly at the point they build a `Response` or read a `Request` body — the dataclasses stay
pure data with no behavior of their own, consistent with §10.2):

```python
from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


Handler = Callable[[Request], Response]


def _handler_class(handler: Handler) -> type[BaseHTTPRequestHandler]:
    class _Adapter(BaseHTTPRequestHandler):
        def _dispatch(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length else b""
            request = Request(
                method=self.command,
                path=self.path,
                headers={key: value for key, value in self.headers.items()},
                body=body,
            )
            response = handler(request)
            self.send_response(response.status)
            for key, value in response.headers.items():
                self.send_header(key, value)
            if "Content-Length" not in response.headers:
                self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def do_GET(self) -> None:
            self._dispatch()

        def do_POST(self) -> None:
            self._dispatch()

        def do_PUT(self) -> None:
            self._dispatch()

        def do_PATCH(self) -> None:
            self._dispatch()

        def do_DELETE(self) -> None:
            self._dispatch()

        def log_message(self, format: str, *args: object) -> None:
            pass  # silence default request logging to stderr during tests

    return _Adapter


@contextmanager
def mock_http_server(handler: Handler) -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _handler_class(handler))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
```

Notes on why this is still consistent with §10.2 despite using classes and a decorator:

- `BaseHTTPRequestHandler`/`HTTPServer`/`threading.Thread` are stdlib classes used *as a
  library* — `http.server`'s API requires a handler *class* (it instantiates one per request
  internally), so `_handler_class` is a small factory that closes over the plain-function
  `handler` and satisfies that contract. This isn't "our" class hierarchy or business logic in
  class form; it's the minimum adapter needed to bridge a class-shaped stdlib API to a
  function-shaped one.
- `@contextmanager` (stdlib `contextlib`) turns a generator function into a context manager
  without writing a class with `__enter__`/`__exit__` — it's the *more* functional-style option
  here, not a violation, and is one of the two decorators this project uses on purpose (§10.2,
  alongside `@dataclass`).

Usage from a `sleeper_client` test:

```python
def test_fetch_league() -> None:
    def handler(request: Request) -> Response:
        assert request.path == "/league/1180391690551980032"
        body = b'{"league_id": "1180391690551980032", "name": "Only Gold"}'
        return Response(status=200, headers={"Content-Type": "application/json"}, body=body)

    with mock_http_server(handler) as base_url:
        league = fetch_league("1180391690551980032", base_url=base_url)

    assert league.name == "Only Gold"
```

This is why `sleeper_client` functions take an explicit `base_url: str = SLEEPER_BASE_URL`
parameter (§6.1) rather than an injected request-making callable — the test seam is the URL, not
the transport, which is simpler and exercises real HTTP.

**nflverse/`nfl_data_py` is a different case**, worth flagging now rather than discovering it
during Phase B: it makes its own HTTP calls to hardcoded GitHub release URLs with no base-URL
parameter to redirect, so this mock-server pattern doesn't apply to it directly. The plan there:
keep each `nfl_data_py` call to a single, thin line in `stats/nflverse.py` (e.g. `def
_import_weekly(seasons: list[int]) -> pd.DataFrame: return nfl_data_py.import_weekly_data(seasons)`),
test everything downstream of it with a fixture DataFrame passed in directly, and mark that one
call site `# pragma: no cover` as a second, explicit, narrow exception to §10.1's coverage rule
(the first being genuinely-unreachable code) — validated instead by an occasional manual run
against the real library, not by the automated 100%-enforced suite.

## 11. Open questions / explicitly deferred

- **Write-access mechanism** (reverse-engineered internal Sleeper API vs. browser automation)
  — deferred until Phase 2. Revisit once Phase 1's recommendation quality is trusted.
- **Notifications** — deferred; decision log + git history is the interface for now.
- **News-research skill details** (source prioritization, exact filing/frontmatter convention)
  — sketched in §5.4, to be written as `.claude/skills/news-research.md` and refined once we see
  what the LLM actually produces in practice.
- **Parquet git-tracking vs. git-ignoring `data/`** — leaning tracked, not finalized.

## 12. Suggested milestones

1. CLI skeleton + `sleeper league sync` / `sleeper players sync`, league-ID resolution (§6.1).
2. Stats ingestion (`stats sync`) + ported VORP calculation (`stats vorp`) against the real
   league scoring settings, validated against known 2025 outcomes for sanity-checking.
3. Wiki + decision log scaffolding, with one manually-triggered end-to-end run: sync → analyze →
   write a recommendation to `decisions/` → commit/push.
4. `news-research.md` skill v1 + one manual run researching a handful of rostered players,
   to validate the filing convention before leaning on it for real decisions.
5. `waiver recommend` and `freeagent recommend`, since those recur most often in-season.
6. `trade evaluate` / `trade propose`.
7. `draft` tooling, timed for next draft window.
8. First Claude Code Routine for a real recurring task (start with the weekly stats sync,
   lowest risk).
9. Skills v1 for the remaining domains, then the self-revision loop once there's decision-log
   history to learn from.
