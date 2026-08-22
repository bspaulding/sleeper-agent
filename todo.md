# Project TODO

## Live-draft pick tracker should be a tested CLI command, not an ad hoc script

During the 2026-08-22 mock draft #3 (`decisions/2026/2026-08-22-draft-mock-draft-3-slot8.md`),
the live-pick monitor loop (poll Sleeper's picks endpoint, compute snake order, detect "next pick
is mine", fetch+print a fresh `draft board`) was written from scratch as a throwaway bash script
in the scratchpad directory and run under the `Monitor` tool.

**Why:** User flagged (2026-08-22) that this shouldn't be re-derived ad hoc every draft session —
it should be a proper, tested `sleeper-agent` subcommand (e.g. `draft watch-picks` or folded into
`draft board --watch`'s existing machinery) so the snake-order math and turn-detection logic are
covered by tests instead of being freshly (and untested-ly) rewritten each time.

**How to apply:** Next draft-tooling pass, promote the bash-loop logic into `draft_tools/board.py`
(or a sibling module) as a real command, with unit tests for the snake-order pick→slot math
(round parity, ascending/descending offset) and the "next pick is mine" detection. Keep the
`Monitor`-tool wrapper (still useful for surfacing notifications), but the actual polling/logic
should live in tested project code, not a scratchpad script.

## Rookie / new-outlook player research strategy

Need a follow-up design pass on how to research and evaluate players whose fantasy outlook
isn't captured by `stats vorp` at all: rookies (no prior-NFL-season stats row), players who
changed teams/roles via free agency or trade with a materially different offensive situation,
and generally anyone with a new-for-this-season outlook. Flagged 2026-08-16 while scoping
`docs/superpowers/specs/2026-08-16-draft-strategy-research-and-positional-need.md`
(positional-need-aware `draft board`), explicitly left out of that spec's "Out of scope /
follow-up" section to keep it focused.

**Why:** The first 2026 mock draft already hit this concretely — 2025-rookie Colston Loveland
was entirely invisible to `draft board`/`stats vorp` because he has zero rows in the prior
season's stats (`wiki/team/roster-philosophy.md`'s data-currency caveat). This isn't a data-lag
problem that resolves itself; it's structural — a player with no prior-season NFL stats will
always be invisible to a stats-vorp-only pipeline, rookie or not.

**How to apply:** The likely direction sketched at flag-time: extend the wiki News-page pattern
already used for injury/trend context (`value/scoring.py`'s `recent_news_excerpt`) with a
rookie/new-situation research sweep akin to `.claude/skills/news-research.md`, so qualitative
signal (draft capital, college production, offensive scheme fit, camp reports) fills the gap
VORP structurally can't. This is its own research+design cycle — don't fold it into small
draft-tooling changes.
