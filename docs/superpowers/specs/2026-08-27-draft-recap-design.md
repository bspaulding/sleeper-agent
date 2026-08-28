---
date: '2026-08-27'
status: proposed
related_wiki:
  - wiki/team/draft-strategy.md
---

# Draft recap: a tongue-in-cheek, graded post-draft report card

## Motivation

`todo.md`'s "Easter Egg / Fun Draft reviewer" item: Yahoo Fantasy used to email a graded (A-F)
report card after every draft, roasting/praising each GM's picks. This spec builds the
sleeper-agent equivalent — run once after any draft (mock or real) completes, grading every
team in the league and handing out a few freeform superlative "trophies," published as a
shareable HTML report card.

This follows the same split as every other domain in this repo (`PROJECT_PLAN.md` §9): a new
CLI command computes the one deterministic number a grade should be anchored to (how good each
pick was relative to our own big board), and a new skill supplies the judgment — the actual
letter grades, the trophies, and the persona voice — that no amount of arithmetic can produce on
its own.

## 1. `sleeper-agent draft recap` (new subcommand, `draft_cmd.py`)

```
sleeper-agent draft recap --draft-id <id> [--value-season <year>] [--json]
```

- `--draft-id` (required) — same as `draft board`'s `--draft-id` mode.
- `--value-season` (optional) — same default as `draft board`/`draft keepers`: current year
  minus 1, printed as a notice when defaulted. Selects which `data/bigboard/<value-season>.csv`
  to grade against.
- `--json` — machine-readable output for the skill to consume. Default (no flag) is a
  human-readable per-team table, useful standalone and for manually sanity-checking a run.
- No `--league-id`, `--num-teams`, `--me`, `--roster-id`, or `--draft-slot`. Recap is inherently
  whole-league, and everything else it needs comes off the draft object itself:
  `fetch_draft(draft_id)` already returns `league_id` (empty string `""` for a mock — Sleeper's
  own signal, reused as-is, no separate flag) and `rounds`/`num_teams` for the completeness
  check below.

### Behavior

1. `draft = fetch_draft(draft_id)`, `picks = fetch_draft_picks(draft_id)`.
2. **Completeness check**: if `len(picks) < draft.rounds * draft.num_teams`, raise
   `DraftNotCompleteError(draft_id, picks_made=len(picks), picks_expected=draft.rounds *
   draft.num_teams)` — a recap only makes sense once every pick has landed. Same
   raise-and-print-and-exit-1 convention as `BigboardNotBuiltError` elsewhere in this file.
3. `bigboard_rows = load_bigboard(root, value_season)` — propagate
   `BigboardNotBuiltError`/`BigboardUnresolvedRowError`/`BigboardMalformedError` exactly as
   `_resolve_draft_context` does today (print and exit 1, no traceback). Build a
   `player_id -> BigboardRow` lookup dict.
4. **Team naming**: if `draft.league_id` is non-empty, `fetch_rosters(league_id)` +
   `fetch_users(league_id)` to build `roster_id -> User`; team name is `User.team_name` if set,
   else `User.display_name`. If `draft.league_id` is empty (mock), or a pick's `roster_id` isn't
   found in that map, team name falls back to `f"Slot {draft_slot}"`. Group every pick by
   `draft_slot` (always populated in both mock and league drafts, per the field's own docstring
   in `models/sleeper.py`) — `roster_id` is carried along per-team where available but is never
   the grouping key, so mock and real drafts share one code path.
5. **Per-pick join**: for each `DraftPick`, look up `bigboard_rows_by_id.get(pick.player_id)`.
   - Found: `board_rank = row.rank`, `vorp = row.vorp`,
     `value_delta = pick.pick_no - row.rank` (positive = got them later than their rank deserved,
     i.e. good value; negative = reached ahead of their rank).
   - Not found (DEF, or any player the big board has no row for): `board_rank = None`,
     `vorp = None`, `value_delta = None` — explicit "no data," never silently dropped or
     defaulted to 0. Same posture as `draft.md`'s existing DEF guidance.
   - Carry `pick.is_keeper` through unchanged — the skill needs it to avoid grading a
     roster-building decision made seasons ago as if it were this draft's judgment.
   - Name/position come straight off `DraftPick.player_name`/`player_position` (already embedded
     by Sleeper's picks payload) — no extra players.parquet read needed.
6. **Per-team summary**: `mean_value_delta` = mean of that team's non-null `value_delta`s (`None`
   if the team has zero resolvable picks — pathological, but explicit rather than a fake 0.0).
   This is the one number the CLI hands the skill as a grading anchor; nothing about how it maps
   to a letter grade lives in the CLI.
7. Teams sorted by `draft_slot` ascending (deterministic, not a "best team first" ranking — that
   judgment belongs to the skill/output, not the data command).

### Output

`--json`:

```json
{
  "draft_id": "1398935084572143616",
  "draft_season": "2026",
  "value_season": "2025",
  "num_teams": 12,
  "teams": [
    {
      "draft_slot": 8,
      "roster_id": 5,
      "team_name": "Slot 8",
      "mean_value_delta": 3.4,
      "picks": [
        {
          "round": 1,
          "pick_no": 8,
          "player_id": "9509",
          "name": "Bijan Robinson",
          "position": "RB",
          "is_keeper": false,
          "board_rank": 5,
          "vorp": 87.4,
          "value_delta": 3
        }
      ]
    }
  ]
}
```

Default (no `--json`): one block per team (`draft_slot`, `team_name`, `mean_value_delta`), each
followed by its picks as `round.pick_no  name (pos)  rank=N vorp=V.V  Δ=+3` /
`rank=-- (no board data)` for unresolved picks, `[KEEPER]` suffix where `is_keeper`.

### Errors

- `DraftNotCompleteError` — new, message includes `picks_made`/`picks_expected` and points at
  the draft-id.
- `BigboardNotBuiltError` / `BigboardUnresolvedRowError` / `BigboardMalformedError` — reused
  as-is from `draft_tools.bigboard`.

## 2. `.claude/skills/draft-recap.md` (new skill)

Added to the roster in `.claude/skills/README.md` alongside the existing eight files.

Frontmatter: `name: draft-recap`, description covering "generate a tongue-in-cheek graded draft
report card as a shareable HTML artifact, after any draft (mock or real) completes" and a
disambiguation line against `draft.md` (live-draft watching) and `bigboard.md` (pre-draft
ranking) — same pattern as `draft.md`'s own description.

Process:

1. **Prerequisites**: the draft is complete; that value-season's big board exists (recap will
   hard-stop with a clear message otherwise — nothing to work around).
2. **Run** `sleeper-agent draft recap --draft-id <id> [--value-season <year>] --json` and read
   the structured per-team data.
3. **Persona**: an over-the-top sports-radio hot-take host — bombastic, confident, quotable.
   Roast and praise equally hard, but good-natured: these are real league mates, not strangers,
   so the target is "ribbing," not "mean." Stay in character for every team's write-up, not just
   the extremes.
4. **Grading**: one A-F letter grade per team. Anchor loosely to that team's `mean_value_delta`
   (a real signal, not decoration) but don't linearly map it — weigh it against your own read of
   roster construction (positional balance, starter coverage, upside, bye-week/stacking risk)
   the same way a human draft analyst would. Note `is_keeper` picks separately in the commentary
   rather than grading them as this draft's judgment call. 2-4 sentences of in-character
   commentary per team explaining the grade, citing specific picks.
5. **Trophies**: 3-6 freeform superlative awards across the whole league, invented fresh each
   run (no fixed category list) — e.g. best value pick, biggest reach, most stacked at one
   position, boldest gamble. Every trophy must cite a specific pick or team from the data, never
   a vibe with nothing behind it.
6. **Build the HTML report card**: load `artifact-design` first (already a hard requirement of
   the `Artifact` tool for any new page) for the visual pass — this is a "fun, shareable" page,
   so it's worth actual design effort, not a plain table dump. Self-contained per the `Artifact`
   tool's rules (inline CSS/JS, no external assets besides Google Fonts).
7. **File location — commit, don't just publish**: write the HTML to a new top-level `reports/`
   directory (parallel to `decisions/`, `wiki/`, `data/`) as
   `reports/draft-recap-<draft_season>-<draft_id>.html`, publish it from that exact path via the
   `Artifact` tool, then commit the file to git with a short message (draft id, season, one-line
   summary). This is the recap's normal job every run, not a one-off request — stated here so it
   doesn't read as an unprompted commit each time the skill fires. Push per whatever the
   invoking context's git workflow already does (this skill doesn't invent its own push policy).
8. Report the Artifact URL and the committed file path back in chat.

## 3. New directory: `reports/`

Holds committed recap HTML files, one per draft run. Nothing else lives here yet; no index file
— `git log`/`ls` over a dozen-ish files a season is enough discoverability, consistent with this
repo's "don't build infrastructure ahead of need" posture elsewhere.

## 4. Tests (`cli/tests/test_draft_recap.py`)

- Join logic: a pick with a matching bigboard row gets the right `board_rank`/`vorp`/
  `value_delta` (both a positive-value and a negative-reach case); a pick with no bigboard row
  (DEF) gets explicit `None`s, not dropped or defaulted.
- Grouping: picks grouped by `draft_slot`; `mean_value_delta` computed only over non-null
  deltas; a team with zero resolvable picks gets `mean_value_delta: None`.
- Team naming: league draft (`league_id` set) resolves real team names via
  rosters+users; mock draft (`league_id == ""`) falls back to `"Slot N"`; a real draft with a
  `roster_id` missing from the users/rosters map also falls back to `"Slot N"`.
- `is_keeper` passed through unchanged.
- `DraftNotCompleteError` raised when `len(picks) < rounds * num_teams`; not raised when equal.
- `--json` output matches the schema above; default text output renders without error and
  includes the `[KEEPER]`/`(no board data)` markers where expected.
- Existing `BigboardNotBuiltError` etc. propagate (print-and-exit-1), reusing the same test
  pattern already used for `draft board`'s equivalent path.
- 100% branch/function coverage per `PROJECT_PLAN.md` §10.1, same CI gate as the rest of `cli/`.

No test touches the skill's LLM-authored grades/trophies/HTML — same boundary as every other
skill in this repo (`code-review.md`, `bigboard.md`, etc.): the CLI is tested, the judgment
isn't.

## Rollout

Validated by running it for real, not a separate sign-off: once built, run `draft recap`
against the most recent logged mock draft (`1398935084572143616`, slot 8, season 2026,
`--value-season` defaulting to 2025), produce the HTML report card, publish it, and commit it —
the concrete pass/fail signal is a real, readable, in-character report card landing in
`reports/` for a draft the repo already has full pick data for.

## Out of scope / follow-up

- **Automatic triggering** (a Routine that fires the moment a draft finishes) — this spec is
  manual-invocation only, same "no automated re-sweep" posture as the bigboard spec took for its
  own out-of-scope item. Nothing here blocks adding it later.
- **Cross-draft history/leaderboard** (e.g. tracking grades across mock draft #1-4 and the real
  draft) — each run is a standalone artifact; no aggregate view.
- **Emailing/notifying the league** — publishing produces a link; sending it to anyone is a
  human decision, not something this skill does on its own.
