---
name: bigboard
description: Build or refresh the pre-draft big board (data/bigboard/<season>.csv) — merges VORP-ranked veterans with triaged rookies into one ordinal ranking, resolving ties and rookie placement via LLM judgment informed by recent bigboard decision-log entries and fresh news. Use before a draft, or any time news/injury/depth-chart signal changes enough to warrant a re-sweep.
---

# bigboard

Builds/refreshes `data/bigboard/<season>.csv`, the single ordinal ranking `draft board`/
`watch-picks` require at draft time (see
`docs/superpowers/specs/2026-08-23-draft-bigboard-design.md`). Splits mechanical work (adding
new players, flagging changes) from judgment work (placement, tie-breaking) — this skill drives
the judgment half.

## When to run this

- Before any draft (real or mock/wargame) — a required prerequisite, same footing as `stats vorp`.
- Any time news/injury/depth-chart signal changes enough that the current ranking might be
  stale (a manual trigger — there's no automated re-sweep schedule).

## Process

1. Run `sleeper-agent value bigboard build --season <value-season>` (from `cli/`). This
   mechanically merges in anything new — a VORP-ranked veteran not yet on the board gets inserted
   by value order (no judgment needed), a newly-triaged rookie gets inserted at a rough starting
   slot and flagged `[NEEDS REVIEW: new rookie placement]`, and any existing row whose VORP
   changed since last build gets `[VORP CHANGED: <old> -> <new>]` appended to its rationale —
   without moving it. The command prints every flagged row.
   - `--season` here is the **VORP value-season** (the most recently completed real season), not
     the season you're drafting for — it defaults `--rookie-season` to `--season + 1`, since a
     rookie draft class is always dated to the *upcoming* season, one year after the completed
     season VORP is computed from (same directional relationship `draft keepers` already defaults
     the other way, `value_season = season - 1`). This isn't cosmetic: the first real run of this
     skill (2026-08-24) silently triaged **zero** rookies before this was a flag at all, because
     `--season` was being used for both concepts at once and `data/nfl/draft_picks.parquet` only
     had rows for the season *after* the one passed. If a build reports 0 rookies flagged and
     that seems surprising, check `--rookie-season` resolved to the right year before assuming
     there are none to triage — pass it explicitly if the default (`--season + 1`) isn't right for
     a non-standard `--season` use (backtesting, historical analysis).
2. Read the most recent `--kind bigboard` decision-log entries for this season
   (`decisions/<season>/`) — continuity matters: don't re-litigate a call that was already
   deliberately reconsidered and kept. Check current news/injury/wiki context (especially
   `wiki/team/rookie-evaluation.md` for rookie judgment, `wiki/team/roster-philosophy.md` for
   roster-construction framing) for anything flagged.
3. For every row still carrying `[NEEDS REVIEW...]` or `[VORP CHANGED...]`: make the call.
   - New rookie: place it using the same reasoning `draft.md` used to describe live (tier
     cliffs at the position, the round's historical hit rate, `wiki/team/rookie-evaluation.md`'s
     framework) — just done here, calmly, pre-draft, instead of live under a clock. Edit the
     row's `rank` directly (renumber neighbors if you're inserting between two adjacent ranks —
     open the CSV, it's a small hand-editable file) and replace the `[NEEDS REVIEW...]` marker
     in `rationale` with a one-line reason.
   - VORP-changed veteran: decide whether the new VORP value actually changes where they belong
     relative to neighbors. If yes, move the row and update `rationale`. If no, still clear the
     `[VORP CHANGED...]` marker and say so explicitly (e.g. `"reconsidered 2026-09-01, no
     change: still ahead of the next tier"`) — the distinction between "never revisited" and
     "revisited and kept" has to survive, not just the changes.
   - Any near-tied cluster you notice while reviewing (even if nothing flagged it): resolve it
     into a strict order now. This is the whole point — a tie resolved here never costs a live
     pick's clock again.
4. Run `sleeper-agent decisions new --kind bigboard --slug <slug> --season <year>` and fill in
   Summary/Reasoning/Data: what changed, why, and what was explicitly reconsidered-and-kept.
5. Update every row you touched this pass to set `log_ref` to this entry's date/slug.
6. Re-run `sleeper-agent value bigboard build --season <year>` once more as a final check — it
   should report 0 flagged rows. If it doesn't, you missed one; go back to step 3. Then run
   `sleeper-agent draft board` (or just let it be the next thing that reads the file): it
   refuses to load a board whose `rank` column isn't a strict 1..N with no duplicates or gaps,
   which is what catches a neighbor you forgot to renumber in step 3.

## Known sharp edges

- **A hand-reordered board can silently absorb a new row in the wrong place.** `bigboard
  build` inserts a new VORP-ranked player with a top-down first-match scan that assumes the
  board is still VORP-monotonic — but breaking that monotonicity is the whole point of the
  review pass (promoting a lower-VORP player above where raw VORP would put them). Once you've
  promoted someone, any *later*-added player whose VORP is higher than the promoted player's
  will be inserted **above** them, silently and with no review marker, undoing the deliberate
  placement. After every `bigboard build`, re-check the position of any row you moved by hand.
- **Nothing removes a stale row.** A player who drops off `vorp_df` entirely (retired, or no
  longer computable) stays on the big board indefinitely, keeping a stale `vorp` and carrying
  no flag. `filter_off_roster` catches players with no current NFL team, but that's not every
  removal reason. Periodically scan the board for players no longer present in the current VORP
  data and delete those rows by hand.
