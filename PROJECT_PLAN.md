# sleeper-agent — Project Plan / Living Spec

Status: **draft v1** — written from an initial architecture interview (2026-07-25). This
document is meant to evolve as decisions get revisited during implementation. When something
here turns out to be wrong once we start building, update this file in the same PR/commit that
proves it wrong — don't let it drift out of sync with reality.

## 1. Vision

Run an autonomously-managed Sleeper fantasy football team, where:

- A **Python CLI** is the only thing that touches the outside world (Sleeper's API, stats
  providers, news sources). It fetches data, computes analyses, and (once write access exists)
  will execute actions. It is deterministic, testable, versioned code.
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

Pulled directly from Sleeper for league `1180391690551980032` ("Only Gold"):

- **12-team keeper league**, `max_keepers: 2`. League IDs change every season in Sleeper
  (`previous_league_id` chains them together) — **never hardcode a league ID**; resolve the
  current season's league ID at runtime (see §6.1).
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
- **Draft**: only 3 rounds/season (rookie/incoming-pick draft on top of keepers), consistent
  with a long-running keeper league where most of the roster persists year to year.
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
| Free news sources (TBD list) | injury updates, beat-reporter/transaction news for wiki context | scraping/RSS; identify concrete sources during implementation (team injury report pages, RSS feeds, etc.); keep a scraper-per-source design so one breaking doesn't take down the rest |

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
├── vorp/<season>.parquet          # computed VORP, see §6.2
└── news/<season>.parquet          # scraped news items, timestamped
```

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
├── team/roster-philosophy.md
├── team/keeper-strategy.md
├── league/opponents/<roster_id>.md     # scouting notes on other GMs' tendencies
├── decisions.md                        # index into decisions/, see §7
└── strategy/best-ball-scoring-notes.md # how auto-lineup-optimization changes value calculus
```

The LLM is expected to read and update these files as part of its normal reasoning loop (this
is the "living memory" the acceptance criteria calls for), not just the CLI.

## 6. Analysis & CLI capabilities

All entry points live in the Python CLI (`typer` recommended for the CLI framework, `pydantic`
for data models, `pytest` for tests). Proposed command groups:

### 6.1 `sleeper` — league/team data

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
- `stats news sync` — scrape configured free news sources, dedupe, append to `data/news/`, and
  surface anything injury/trade-relevant into the wiki (`wiki/players/*.md`) for the LLM to pick
  up during reasoning.

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
  players by VORP) into this CLI. Since this league's draft is only 3 rounds on top of keepers,
  also needs a `draft keepers` view of who's kept vs. who's actually in the pool.

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
- Draft-day live session for the annual 3-round draft.

## 9. Skills

`.claude/skills/` holds the playbooks that inform judgment calls the CLI can't make by itself:

- `draft.md` — how to value picks vs. keepers, positional strategy for a 3-round supplemental
  draft in a keeper league.
- `trades.md` — when to propose, how to evaluate incoming offers, how much to weight VORP vs.
  team-building narrative/roster fit.
- `waivers.md` — FAAB bidding strategy (budget pacing across the season, not just per-bid value).
- `free-agents.md` — add/drop heuristics between waiver periods.
- A meta-loop: periodically (e.g. end of season, or after notably good/bad decisions), the LLM
  is allowed to revise these skill files based on what the decision log shows worked or didn't —
  this is the "skills that update themselves" requirement. Treat skill edits like any other
  change: committed, with a decision-log-style rationale for what changed and why.

## 10. Tech stack (defaults — adjust freely during implementation)

- Python package/dependency management: `uv`
- CLI framework: `typer`
- Data models/validation: `pydantic`
- Tabular data: `polars` + Parquet
- Testing: `pytest`
- Linting/formatting: `ruff`

## 11. Open questions / explicitly deferred

- **Write-access mechanism** (reverse-engineered internal Sleeper API vs. browser automation)
  — deferred until Phase 2. Revisit once Phase 1's recommendation quality is trusted.
- **Notifications** — deferred; decision log + git history is the interface for now.
- **Concrete free news sources** — to be identified during implementation rather than locked in
  here.
- **Parquet git-tracking vs. git-ignoring `data/`** — leaning tracked, not finalized.

## 12. Suggested milestones

1. CLI skeleton + `sleeper league sync` / `sleeper players sync`, league-ID resolution (§6.1).
2. Stats ingestion (`stats sync`) + ported VORP calculation (`stats vorp`) against the real
   league scoring settings, validated against known 2025 outcomes for sanity-checking.
3. Wiki + decision log scaffolding, with one manually-triggered end-to-end run: sync → analyze →
   write a recommendation to `decisions/` → commit/push.
4. `waiver recommend` and `freeagent recommend`, since those recur most often in-season.
5. `trade evaluate` / `trade propose`.
6. `draft` tooling, timed for next draft window.
7. First Claude Code Routine for a real recurring task (start with the weekly stats/news sync,
   lowest risk).
8. Skills v1 for each domain, then the self-revision loop once there's decision-log history to
   learn from.
