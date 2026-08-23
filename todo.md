# Project TODO

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
