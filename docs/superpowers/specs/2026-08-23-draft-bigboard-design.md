---
date: '2026-08-23'
status: proposed
related_decisions:
  - decisions/2026/2026-08-23-draft-mock-draft-wargame-slot8-run16.md
  - decisions/2026/2026-08-23-draft-mock-draft-wargame-slot8-run15.md
  - decisions/2026/2026-08-23-mock-draft-wargame-slot8.md
related_wiki:
  - wiki/team/rookie-evaluation.md
  - wiki/team/draft-strategy.md
  - wiki/team/roster-philosophy.md
---

# Pre-draft big board: a materialized, reviewed ranking for live drafting

## Motivation

Two problems, traced to the same root cause during wargame rehearsals of `draft.md`'s live
snake-draft flow:

1. **No wargame run has ever drafted a rookie**, and structurally couldn't. `draft board`/
   `watch-picks` rank players by VORP, which is only computable for a player with a prior NFL
   season of stats (`docs/superpowers/specs/2026-08-22-rookie-and-new-outlook-player-
   visibility.md`) — true rookies are invisible to the ranked list by construction and only
   ever appear in a separate, unranked "Rookie watch" section. Weighing a Rookie watch entry
   against the main board is real judgment work (`draft.md`'s step 3), and it has never
   actually been exercised end to end because the mock server's fixed player board
   (`wargame_seed.json`) has no VORP-less rookie entries to draft in the first place.
2. **Run #16 voided on a decision with no signal, not too little time.** Six live picks landed
   cleanly (each with an obvious top-VORP NEED match), then the 7th turn hit four bench players
   tied at exactly 0.0 VORP with no roster pressure left to break the tie. The Drafter spent
   ~57 of the ~60s clock re-querying and constructing a tiebreak narrative for options it had
   already established were equivalent, and its (correct) rec landed only 3.6s before expiry.
   See `decisions/2026/2026-08-23-draft-mock-draft-wargame-slot8-run16.md`.

Both trace to the same design gap: **the live board asks the Drafter to make judgment calls
(rookie-vs-veteran weighing, tie-breaking) under a 60-second clock that would be trivial to make
calmly, once, ahead of time.** VORP itself is already a pre-computed, once-per-season artifact —
only the drafted-player filtering and roster-need annotation are genuinely live. This spec
extends that same "compute once, filter live" shape to cover the parts that currently aren't:
rookie placement and tie resolution.

The fix: a **big board** — one strictly-ordinal, hand-reviewed ranking merging VORP-ranked
veterans with triaged rookies, built and maintained *before* the draft via a dedicated skill,
and required (no fallback) by `draft board`/`watch-picks` at draft time. This directly targets
both problems above: rookies get an ordinal slot instead of a separate unranked list, and
because the ranking is strictly ordinal, ties are pre-broken before the clock ever starts.

## 1. Data artifact: `data/bigboard/<season>.csv`

Deliberately **not parquet**, unlike the rest of `data/` (VORP, rosters, stats) — this file is
meant to be reviewed and hand-edited by an LLM (with human sign-off) between builds, so it needs
to be plain-text and git-diffable. It's still tabular derived data consumed by code, just not
machine-synced-only the way the rest of `data/` is.

Schema (one row per ranked player, `rank` strictly ordinal 1..N, no ties):

| Column | Type | Notes |
|---|---|---|
| `rank` | int | Strict ordinal position. No duplicate ranks. |
| `player_id` | str | Sleeper id. |
| `name` | str | |
| `position` | str | |
| `source` | `"vorp"` \| `"rookie"` | Which population this row came from. |
| `vorp` | float, nullable | Populated for `source="vorp"` rows; null for `"rookie"` rows — no synthetic VORP is ever invented, preserving `PROJECT_PLAN.md` §6.3's "VORP stays purely quantitative" constraint. |
| `draft_round` | int, nullable | NFL draft round, populated for `source="rookie"` rows (from `triage_rookies`). |
| `rationale` | str | One-line note. Required for any non-default placement (rookie insertion, tie resolution, manual reorder). Carries review-state markers — see §2. |
| `log_ref` | str, nullable | Slug/date of the most recent `--kind bigboard` decision-log entry that touched this row. |

## 2. The `bigboard build` command (mechanical half)

`sleeper-agent value bigboard build --season <year>`. One command serves both the first-ever
build and every later refresh — a fresh file is just the empty starting state of the same
operation ("create and update" are the same recurring job, not two tools).

Behavior, every run:

1. Load `data/bigboard/<season>.csv` if it exists (else start empty).
2. Load `data/vorp/<season>.parquet` — hard-stop (`VorpNotComputedError`-style) if missing.
3. Load triaged rookies via the existing `triage_rookies` (`data/nfl/draft_picks.parquet` +
   `data/sleeper/players.parquet`) — hard-stop with an analogous message pointing at
   `stats draft-picks sync --season <year>` if the draft-picks table is missing.
4. **Never touch an existing row's `rank`, `rationale`, or `log_ref`.** This command only adds
   and flags — it must be safe to run repeatedly without discarding prior human/LLM judgment.
5. For a VORP-ranked player not yet in the file: insert by value order relative to existing
   neighbors (purely mechanical — an ordinary quantitative veteran needs no judgment call to
   place).
6. For a triaged rookie not yet in the file: insert at an approximate slot derived from
   `wiki/team/rookie-evaluation.md`'s round/position hit-rate table (a reasonable starting
   point, not a judgment call), and mark `rationale = "[NEEDS REVIEW: new rookie placement]"`.
7. For an existing row whose underlying VORP changed materially since last build: leave its
   `rank` untouched, but append `"[VORP CHANGED: <old> -> <new>]"` to its `rationale` so it
   surfaces for review without silently reordering anything.
8. Write the updated CSV. Print a short summary of what was added/flagged.

This command never resolves a flag and never breaks a tie — that's the LLM half.

## 3. The `bigboard` skill (judgment half)

New skill, `.claude/skills/bigboard.md`, separate from `draft.md` — this runs on its own
schedule (before a draft, or any time news/injury/depth-chart signal changes enough to warrant
a re-sweep), not only during draft prep, the same way `wargame.md` is separate from `draft.md`
despite validating it.

Process:

1. Run `value bigboard build --season <year>` (§2) to mechanically merge in anything new and
   flag anything reviewable.
2. Read the **most recent `--kind bigboard` decision-log entries** for this season (continuity:
   what was already decided and why, so a re-sweep doesn't re-litigate a settled call) plus
   current news/injury/wiki context for anything flagged.
3. For every row still carrying a `[NEEDS REVIEW...]` or `[VORP CHANGED...]` marker: make the
   judgment call (rookie insertion point using `draft.md`'s existing rookie-weighing reasoning
   chain — tier cliffs, round hit-rate, NEED-agnostic since this is pre-draft; tie resolution
   for any cluster of near-equal rows), edit the row directly (`rank`, `rationale`), and clear
   the marker.
4. Any row the LLM reconsidered but chose to leave as-is also gets its `rationale` updated to
   say so explicitly (e.g. `"reconsidered 2026-09-01, no change: ..."`) — the distinction
   between "never revisited" and "revisited and kept" must survive, not just changes.
5. Run `sleeper-agent decisions new --kind bigboard --slug <slug> --season <year>` and fill in
   Summary/Reasoning/Data: what changed, why, and what was explicitly reconsidered-and-kept.
6. Update every touched row's `log_ref` to point at this entry.

`decisions new`'s `--kind` choices gain `bigboard` alongside the existing
`{draft,keeper,trade,waiver,freeagent}`.

## 4. Live consumption: `draft board` / `watch-picks`

- **Hard requirement, no fallback.** Missing `data/bigboard/<season>.csv` is a hard stop
  (same shape as the existing VORP-missing error), not a silent drop back to raw VORP sort.
  Same for any row still carrying an unresolved `[NEEDS REVIEW...]`/`[VORP CHANGED...]` marker
  anywhere in the file — drafting off an unreviewed judgment gap is exactly the failure class
  this spec exists to remove. Deliberately whole-file, not just the top of the board: a flag
  buried at rank 200 is still an unreviewed judgment call, and the cost of finishing the review
  is trivial next to the cost of a bad live pick. In the normal case this never fires: the
  bigboard skill (§3) is a required pre-draft step, so by the time a live draft starts there's
  nothing left unresolved.
- **Ranking source**: the bigboard's `rank` column order, not a live VORP sort.
- **Filtering**: same drafted/kept-player exclusion logic as today, now applied against
  bigboard rows instead of the raw VORP table.
- **Annotation**: the existing live NEED/FLEX/SURPLUS/tier logic is unchanged and still
  computed fresh every turn against the current roster — this is the hybrid layer that keeps
  the positional-imbalance guard (the 8-RB/0-DEF bug) working. Tier-cliff detection still
  applies to `source="vorp"` rows (uses their `vorp` value); `source="rookie"` rows get a
  `[ROOKIE]` tag instead of a numeric tier, same display convention as today's Rookie watch —
  no synthetic VORP is invented to force them into the tier math.
- **"Rookie watch" section is removed**, not kept alongside the main list. Its entire purpose —
  surfacing a VORP-invisible player — is now handled structurally by rookies appearing inline
  in the ranked board. Keeping a redundant second mechanism for the same population would just
  reintroduce two sources of truth.

## 5. `draft.md` changes

- **Step 1 (pre-draft prep)**: add "run the `bigboard` skill to build/refresh
  `data/bigboard/<season>.csv`" alongside the existing VORP-sync/wiki-scaffold prerequisites.
  Replace the old "review `value rank --top 50`... to build a **mental** tier list" language —
  the tier list is now a materialized, reviewed artifact, not something reconstructed in your
  head each time.
- **Step 2 (during the draft)**: update the description of `draft board`'s "best available by
  value" list to note it's sourced from the big board's pre-resolved order (rookies inline,
  ties pre-broken), with NEED/FLEX/SURPLUS/tier annotation still computed live on top. Remove
  the Rookie watch bullet (superseded per §4).
- **Step 3 (draft-day judgment the tool can't automate)**: remove "Weighing a Rookie watch
  entry against the main board" as a *live* judgment call — that reasoning chain moves to the
  `bigboard` skill's pre-draft review (§3 point 3), with a pointer left in its place so the
  history of *why* rookies get weighed the way they do isn't lost, just relocated to where it's
  actually applied.

## 6. Wargame tie-in

Two separate changes, both enabled by (but not part of) this spec — scoped here, implemented as
a follow-up:

1. **Reuse, no wargame-specific bigboard.** `draft watch-picks --value-season 2025` should read
   the real `data/bigboard/2025.csv` the same way it already reuses real 2025 VORP data — no
   new wargame-only ranking artifact. This "just works" once a real 2025 bigboard exists, the
   same way wargame runs already depend on real VORP having been synced first.
2. **Mock server needs to accept rookie picks.** `wargame_seed.json`'s `board` array (currently
   `player_id`/`name`/`position`/`vorp`, every entry carrying a real VORP number) needs a
   handful of rookie entries added with no `vorp` field, and `wargame_server.py`/`state.py`'s
   pick validation and bot-autopick logic (`_bot_autopick`'s `max(..., key=vorp)`) need to
   treat a missing `vorp` as valid input — bots simply shouldn't rank a no-stats rookie highly,
   so a null-safe low-priority default is enough; no bot behavior change beyond not crashing.
   This is the concrete validation criterion for the whole spec (§8).
3. `wargame.md`'s "One-time / per-season setup" gains a third prerequisite alongside VORP sync:
   a real `data/bigboard/<value-season>.csv` must exist before a wargame run, same hard-stop
   reasoning as §4.

## 7. Tests

- `bigboard build`: new VORP player inserted by value order; new rookie inserted via the
  heuristic and flagged; idempotent re-run leaves existing `rank`/`rationale`/`log_ref`
  untouched; a VORP-changed row gets flagged without reordering; missing VORP/draft-picks data
  hard-stops with the right message.
- `decisions new --kind bigboard` scaffolds correctly.
- Live consumption: bigboard order preserved after drafted/kept filtering; NEED/FLEX/SURPLUS/
  tier annotation applied on top; missing bigboard file hard-stops; any unresolved
  `[NEEDS REVIEW...]`/`[VORP CHANGED...]` row anywhere in the file hard-stops; rookie rows
  render `[ROOKIE]` instead of a numeric tier.
- Wargame: seed + mock server accept a rookie `player_id` end to end — a wargame run actually
  drafting a rookie is the concrete pass/fail signal.

## 8. Rollout

Same DoD pattern as prior specs in this repo: validated against the next wargame run, not a
separate sign-off. Two concrete success signals:

1. A tie cluster (the run #16 failure shape) is pre-resolved — the live Drafter sees a single
   next-best option with no deliberation, no re-querying.
2. A rookie gets drafted end to end in a wargame run — closing the "have we ever drafted a
   rookie" question that started this design.

## Out of scope / follow-up

- **FA/trade role-changers** blending into the big board — already flagged as out of scope by
  the original rookie-visibility spec; unchanged by this one.
- **Automated re-sweep scheduling** (e.g. a reminder to re-run the `bigboard` skill on some
  cadence) — left manual for now, triggered by the human/LLM noticing relevant news, not a cron
  job.
- **Numeric tier-equivalent for rookie rows** — kept simple (`[ROOKIE]` tag, no number) for now;
  revisit only if that proves confusing in practice against real tier-annotated neighbors.
