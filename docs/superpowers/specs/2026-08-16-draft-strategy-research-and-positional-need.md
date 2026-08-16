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
`cli/tests/fixtures/sleeper/draft_picks.json`). Confirmed against
`cli/tests/fixtures/sleeper/draft.json` (a real Sleeper API response), the draft object itself
— fetchable via the existing `fetch_draft(draft_id)` — also carries `slot_to_roster_id` (a
slot→roster_id map, present **before any picks are made**) and per-position slot counts under
`settings` (`slots_qb`, `slots_rb`, `slots_wr`, `slots_te`, `slots_flex`, `slots_def`,
`slots_bn`). This is a better source than `League.roster_positions` for the roster-requirement
math in §2b, and it's available in **both** league and mock-draft mode (a mock draft has no
`League` object, but it does have a `Draft` object) — so `cmd_draft_board` can call
`fetch_draft(draft_id)` unconditionally right after resolving `draft_id`, in both branches,
rather than needing a mock-only fallback.

Extend the models in `cli/src/sleeper_agent/models/sleeper.py`:
- `DraftSettingsRaw`: add `slots_qb: int`, `slots_rb: int`, `slots_wr: int`, `slots_te: int`,
  `slots_flex: int`, `slots_def: int` (all `total=False`, matching the existing TypedDict style).
- `DraftRaw`: add `slot_to_roster_id: dict[str, int]` (Sleeper sends slot numbers as string
  keys, per the fixture).
- `Draft`: add matching flat fields `slots_qb: int`, `slots_rb: int`, `slots_wr: int`,
  `slots_te: int`, `slots_flex: int`, `slots_def: int`, `slot_to_roster_id: dict[int, int]` (int
  keys — convert from the raw string keys in `parse_draft`, matching how other parsers coerce
  raw JSON shapes at the boundary).
- `parse_draft`: read the new settings fields (default 0, same pattern as `rounds`/`teams`
  today) and build `slot_to_roster_id` via `{int(k): v for k, v in (raw.get("slot_to_roster_id")
  or {}).items()}`.

Add CLI args to `draft board` in `cli/src/sleeper_agent/commands/draft_cmd.py` matching the
`--me`/`--roster-id` pair every other command module already uses (`value_cmd.py`'s `value
roster`, `waiver_cmd.py`, `trade_cmd.py`, `wiki_cmd.py`, `sleeper_cmd.py`) — `draft board`
currently has neither, so this is new to this command but not a new pattern in the codebase:

- `--me` (`action="store_true"`) — resolves to the existing `ME_ROSTER_ID = 5` module-level
  constant, same as everywhere else.
- `--roster-id` (int, default `None`) — explicit roster_id override.
- `--draft-slot` (int, default `None`) — new, specific to this command: the slot number chosen
  when starting a mock draft (matches what `draft.md` already tells you to note, e.g. "drafting
  from slot 8"), resolved via the fetched `Draft.slot_to_roster_id[args.draft_slot]`. Works in
  either league or mock mode, since `slot_to_roster_id` is now fetched unconditionally (§2a
  intro).

Resolution order in `cmd_draft_board`, checked in this order, first match wins: `--draft-slot` →
`--me` → `--roster-id`. If **none** of the three are passed, `my_roster_id` is `None` and the
board renders exactly as it does today — no summary line, no tags, no tier numbers. This matches
the rest of the CLI's convention exactly (every other command requires an explicit `--me` or
`--roster-id` too; there's no silent default), so no extra `--no-annotate` flag is needed —
annotation is opt-in by the mere absence of these args, same as everywhere else.

### 2b. Position-count annotation

New helper in `draft_tools/board.py`, e.g. `my_roster_positions(picks, my_roster_id) ->
dict[str, int]` — count drafted-by-me picks by `player_position` (already on `DraftPick`, no
VORP lookup needed so it works even for players with no VORP row, e.g. off-roster or
future-season rookies).

Build the roster requirement directly from the fetched `Draft`'s slot counts (§2a) rather than
parsing `roster_positions` strings:

- hard minimums per position: `{"QB": draft.slots_qb, "RB": draft.slots_rb, "WR":
  draft.slots_wr, "TE": draft.slots_te, "DEF": draft.slots_def}` — for this league, `QB≥1,
  RB≥2, WR≥2, TE≥1, DEF≥1`, matching what `roster-philosophy.md` hand-derived from
  `roster_positions` today.
- shared FLEX capacity: `draft.slots_flex` (2 in this league), poolable across RB/WR/TE.

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
  gets `--me` added to the league-mode example and `--draft-slot <n>` added to the mock-draft
  example, both required in practice to get the new annotation (matching the `--me`/`--roster-id`
  convention already used by every other command). Step 3's "Draft-day judgment the tool can't
  automate" bullet on positional runs gets reworded: the position-count and tier-break facts are
  now shown by the tool when `--me`/`--draft-slot` is passed; weighing them (reach vs. wait,
  which position to prioritize) is still the judgment call.
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
- `cli/tests/test_sleeper_client.py::test_fetch_draft_parses_real_fixture` (existing test,
  already loads `draft.json`): extend its assertions to cover the new fields —
  `draft.slots_qb == 1`, `draft.slots_rb == 2`, `draft.slots_wr == 2`, `draft.slots_te == 1`,
  `draft.slots_flex == 2`, `draft.slots_def == 1`, and `draft.slot_to_roster_id == {1: 3, 2: 8,
  3: 1, 4: 4, 5: 12, 6: 6, 7: 10, 8: 7, 9: 2, 10: 9, 11: 5, 12: 11}` (int-keyed, matching the
  fixture's `slot_to_roster_id` block read literally).
- Roster-requirement construction: hard-min + FLEX-capacity computed correctly from a `Draft`
  fixture's slot counts, including this league's actual grid (`slots_qb=1, slots_rb=2,
  slots_wr=2, slots_te=1, slots_flex=2, slots_def=1`) as one fixture case.
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
