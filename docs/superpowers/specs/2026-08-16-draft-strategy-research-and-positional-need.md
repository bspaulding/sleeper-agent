---
date: '2026-08-16'
status: approved
related_decisions:
  - decisions/2026/2026-08-09-draft-mock-draft-1-turn-by-turn.md
related_wiki:
  - wiki/team/roster-philosophy.md
---

# Draft strategy research + positional-need-aware `draft board`

## Motivation

The first 2026 mock draft (`decisions/2026/2026-08-09-draft-mock-draft-1-turn-by-turn.md`)
finished **2 QB, 8 RB, 2 WR, 3 TE, 0 DEF** against a grid that requires `QB≥1, RB≥2, WR≥2,
TE≥1, DEF≥1`. The retrospective in `wiki/team/roster-philosophy.md` already root-caused this:
every recommendation was "take the board's #1 VORP player, full stop," and RB's steeper
replacement-level drop-off (~2x WR's VORP at ranks 12 and 24) means a pure-VORP policy will
mechanically over-draft RB, not by chance. `.claude/skills/draft.md` explicitly calls
positional-run judgment "draft-day judgment the tool can't automate," but the tool doesn't even
surface the facts needed to make that judgment — it has no concept of "my roster so far" during
a live/mock draft at all.

Two related but separable deliverables:

1. Research how real drafters balance pure value against roster construction, and write the
   findings into the wiki as a standing reference (not just for this fix — general drafting
   literacy for future seasons).
2. Make `draft board` roster-aware: annotate its output with my-team position counts against
   the roster grid, and value-gap tier breaks within each position — mechanical, judgment-free
   facts that were previously only reconstructable by hand after the draft.

## 1. Wiki: `wiki/team/draft-strategy.md` (new file)

Standing reference, separate from `roster-philosophy.md` (which stays scoped to *this team's*
retrospectives and standing rules, not general theory). Sections:

- **VBD baselines** — VORP (value over waiver-wire replacement, what `stats vorp` already
  computes), VOLS (value over the last player who'll start somewhere in the league —
  roster-requirement-aware by construction), VONA (value over what's likely available at your
  next pick). Explain why pure VORP mechanically favors RB, tying directly to the percentile
  table already in `roster-philosophy.md` §"Why so many RBs, so few WRs."
- **RB strategy spectrum** — Zero-RB, Hero-RB, Robust-RB: what each bets on (RB injury/variance
  vs. WR's flatter replacement curve), and a note on which end fits a best-ball,
  no-in-season-lineup-management league (this one) vs. a redraft league.
- **Tiered drafting** — value-gap-cliff reasoning as the answer to "reach or wait," including for
  positional runs (the mainstream answer: read the tier, not the raw position count; don't chase
  a run just because it started).
- **Best-ball positional allocation anchors** (~2-3 QB, 5-7 RB, 6-9 WR, 2-4 TE per Establish The
  Run-style large-pool guidance) — explicitly caveated as tuned for large multi-entry pools, then
  re-derived for this league's actual `QB,RB,RB,WR,WR,TE,FLEX,FLEX,DEF,BN×6` grid rather than
  copied verbatim.
- Sources section citing FantasyPros (VBD/VOLS/VONA), Athlon (positional runs), and the
  Establish-the-Run-style best-ball allocation piece consulted during this spec's research.

`roster-philosophy.md`'s "Standing rules" section gets one new numbered rule pointing at this
file, so `draft.md` step 1 ("check `wiki/team/roster-philosophy.md`... for standing strategy
notes") picks it up transitively without needing its own edit beyond what's in §3 below.

## 2. `draft board`: roster-aware annotation

### 2a. Identifying "my" picks live

`DraftPick` (`cli/src/sleeper_agent/models/sleeper.py`) already carries both `roster_id` and
`draft_slot`, consistently 1:1 mapped per team across all rounds of a draft (confirmed against
`cli/tests/fixtures/sleeper/draft_picks.json`). Add two new mutually-relevant CLI args to
`draft board` in `cli/src/sleeper_agent/commands/draft_cmd.py`:

- `--my-roster-id` (int, optional) — for `--league-id` mode. Defaults to the existing
  `ME_ROSTER_ID = 5` convention already duplicated across every other command module
  (`value_cmd.py`, `waiver_cmd.py`, `trade_cmd.py`, etc.) — reuse that same constant/value here,
  don't invent a new one.
- `--my-draft-slot` (int, optional) — for `--draft-id` (mock) mode, since a mock draft has no
  real roster IDs. This is the slot number chosen when starting the mock (matches what
  `draft.md` already tells you to note, e.g. "drafting from slot 8").

If neither is given, the board renders exactly as it does today (no annotation) — this keeps
the change backward compatible and the annotation opt-in rather than mandatory, since not every
`draft board` call is a live-draft turn (e.g. ad-hoc value checks).

Resolve "my roster_id" once per call: in league mode it's `--my-roster-id` directly; in
draft-id mode, find any pick with `draft_slot == args.my_draft_slot` and take its `roster_id`
(falls back to "no picks yet for that slot" → treat as 0 drafted so far, not an error, since the
board is legitimately usable before your first pick).

### 2b. Position-count annotation

New helper in `draft_tools/board.py`, e.g. `my_roster_positions(picks, my_roster_id) ->
dict[str, int]` — count drafted-by-me picks by `player_position` (already on `DraftPick`, no
VORP lookup needed so it works even for players with no VORP row, e.g. off-roster or
future-season rookies).

Parse `roster_positions` (already modeled as `League.roster_positions` in league mode; a mock
draft has no `League` object at all, so mock mode needs its own source — accept an explicit
`--roster-positions` override, defaulting to this league's known grid
(`QB,RB,RB,WR,WR,TE,FLEX,FLEX,DEF,BN×6`) when omitted, matching `--num-teams`'s existing
default-for-mock-mode pattern) into:

- hard minimums per position: `QB≥1, RB≥2, WR≥2, TE≥1, DEF≥1` (derived by counting literal
  position tokens in `roster_positions`, same source `roster-philosophy.md` hand-derived this
  from)
- shared FLEX capacity: count of `FLEX` tokens (2 in this league), poolable across
  RB/WR/TE

Render a one-line summary above the board:

```
My roster so far: QB 1/1  RB 5/2 (+2 FLEX)  WR 1/2  TE 1/1  DEF 0/1
```

and tag each board row for `NEED` (my count < hard min for that row's position), `FLEX` (at/above
hard min, below hard-min + FLEX capacity), or `SURPLUS` (at/above hard-min + FLEX capacity) —
purely informational tags, no reordering or filtering of the existing VORP-sorted list.

### 2c. Tier-break annotation

`render_board` is a single flat list sorted by VORP across *all* positions (the existing
cross-position "best available" view) — positions are interleaved by rank, not grouped. A
full-width separator line between two adjacent-by-rank-but-different-position rows wouldn't mean
anything, so tiers are computed **within each position independently** but rendered as an
**inline per-row tag**, not a separator, so the flat cross-position ranking stays intact:

Within each position (grouping the *available* board rows, not the full VORP table, by
`position`), sort by `vorp_season` descending and assign a `tier` number starting at 1,
incrementing every time the drop to the next player is large relative to the higher-ranked
player:

```
tier_break = (prev.vorp_season - next.vorp_season) / prev.vorp_season >= 0.20
```

(20% threshold — simple, deterministic, and directly testable against fixture VORP values;
tune later if a real draft shows it's too sensitive/insensitive, per the `.claude/skills/`
self-revision process). Guard against division weirdness for `vorp_season <= 0` (already
possible per the existing percentile table showing negative VORP at deep ranks) — treat a
negative-to-negative or zero-crossing transition as always a tier break rather than computing a
percentage.

Render each row with its position-local tier number appended, e.g.:

```
 1. Saquon Barkley       RB  vorp=322.7  tier=1
 2. Jahmyr Gibbs         RB  vorp=257.4  tier=1
 3. Ja'Marr Chase        WR  vorp=245.0  tier=1
 4. Bijan Robinson       RB  vorp=210.3  tier=2
 5. Josh Jacobs          RB  vorp=195.1  tier=2
 6. Justin Jefferson     WR  vorp=180.0  tier=1
```

Scanning down, a jump in a *given position's* tier number (RB 1→2 between rows 2 and 4, despite
row 3 being a different position in between) signals a real cliff for that position, without
requiring the board to be grouped/re-sorted by position.

### 2d. What does *not* change

Sort order and `vorp_season` values are untouched — this is annotation, not re-ranking or
filtering, per the explicit design decision made during brainstorming (see conversation this
spec was written from). The LLM/skill still makes the reach/wait call; the tool now surfaces the
position-count and tier-cliff facts that call requires instead of leaving them to be
reconstructed by hand (as the mock-draft-1 retrospective had to do after the fact).

## 3. Wiring into skills/wiki

- **`.claude/skills/draft.md`**: step 2 (`draft board --league-id <id> --rounds 15 [--watch]`)
  gets `--my-roster-id`/`--my-draft-slot` added to both the league and mock-draft invocation
  examples. Step 3's "Draft-day judgment the tool can't automate" bullet on positional runs gets
  reworded: the position-count and tier-break facts are now shown by the tool; weighing them
  (reach vs. wait, which position to prioritize) is still the judgment call.
- **`wiki/team/roster-philosophy.md`**: standing rule 1 ("check `value roster --me`... before
  taking the board's #1 suggestion") gets corrected — `value roster` reads
  `data/sleeper/rosters/{season}.parquet`, which doesn't exist until *after* a draft completes,
  so it was never actually usable mid-draft. Point instead at `draft board`'s new annotation as
  the live source of truth for "my roster so far." Add the new standing-rules pointer to
  `wiki/team/draft-strategy.md` from §1 above.

## 4. Tests

`cli/tests/test_draft_tools.py`, following the existing `make_pick`-fixture style (no live
network calls):

- `my_roster_positions`: counts picks correctly filtered to one `roster_id`, ignoring others.
- Roster-grid parsing: hard-min + FLEX-capacity computed correctly from a known
  `roster_positions` list, including this league's actual grid as one fixture case.
- Tag thresholds: a position exactly at hard-min tags `FLEX` not `NEED`; exactly at
  hard-min+FLEX-capacity tags `SURPLUS` not `FLEX` (boundary cases, off-by-one is the likely bug
  class here).
- Tier-break: a fixture VORP list (grouped by position) with one deliberate ≥20% gap and one
  <20% gap, asserting the tier number increments only at the real gap; a zero/negative-VORP
  boundary case.
- `render_board` output format: summary line + position tags + per-row tier numbers all present
  in one rendered string for a small fixture board with interleaved positions.

## 5. Rollout

No separate DoD beyond running a second mock draft with this built, per how Phase E validated
`draft keepers` against real data before trusting it live (`IMPLEMENTATION_PLAN.md`). The second
mock draft is the real-world check that the annotation is actually legible/useful under time
pressure, not just correct in tests.

## Out of scope / follow-up

**Rookie and new-outlook player research** — flagged mid-conversation as a distinct follow-up,
not part of this spec. The first mock draft already surfaced a concrete instance of this gap:
2025-rookie players (e.g. Colston Loveland) are entirely invisible to `stats vorp`-based tools
because they have zero rows in the prior season's stats (`wiki/team/roster-philosophy.md`'s
data-currency caveat). The same blind spot applies more broadly to: players who changed teams in
free agency/trades with a materially different offensive-role outlook, and rookies generally
(no NFL stats history at all, only college production + draft capital as signal). This needs its
own research/design pass on how to source and incorporate that qualitative signal (likely via
the wiki News-page pattern already used for injury/trend context in `value/scoring.py`'s
`recent_news_excerpt`, extended with a rookie/new-situation research sweep akin to
`.claude/skills/news-research.md`) — deliberately not folded into this spec to keep this one
focused on the positional-need problem it was scoped to fix.
