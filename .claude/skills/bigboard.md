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

1. Run `sleeper-agent value bigboard build --season <year>` (from `cli/`). This mechanically
   merges in anything new — a VORP-ranked veteran not yet on the board gets inserted by value
   order (no judgment needed), a newly-triaged rookie gets inserted at a rough starting slot and
   flagged `[NEEDS REVIEW: new rookie placement]`, and any existing row whose VORP changed since
   last build gets `[VORP CHANGED: <old> -> <new>]` appended to its rationale — without moving
   it. The command prints every flagged row.
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
   should report 0 flagged rows. If it doesn't, you missed one; go back to step 3.

## Known sharp edges

(none yet — fill in as real usage surfaces issues, same convention as `wargame.md`)
