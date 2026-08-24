# Skills — self-revision process

The files in this directory (`draft.md`, `trades.md`, `waivers.md`, `free-agents.md`,
`news-research.md`, `code-review.md`, `wargame.md`) are playbooks for the judgment calls the
CLI's pure functions can't make by themselves (`PROJECT_PLAN.md` §9). They are meant to change
over the season as decisions play out — this is the "skills that update themselves" requirement,
not a one-time authoring exercise. `wargame.md` is the exception in kind (a rehearsal runbook,
not an in-season judgment playbook) but follows the same revision trigger: update it after any
wargame run whose retro surfaces a process gap, not on a fixed cadence.

## When to revise a skill

- **End of season** — a full retrospective pass over `decisions/`, checking which recommendations
  worked, which didn't, and whether a skill's heuristics (e.g. FAAB pacing curve, trade
  plausibility weighting, keeper-vs-draft tradeoffs) should change for next year.
- **After a notably good or bad decision** — don't wait for season-end if a single decision (a
  trade that looked fair but wasn't, a waiver bid that way over/underpaid, a keeper call that
  aged badly) reveals a clear gap in the relevant skill's guidance. Revise it then, while the
  reasoning is fresh, rather than letting the same mistake repeat for weeks.
- **Not on a fixed cadence otherwise.** Mid-season churn on skill files for minor stylistic
  reasons isn't the goal — the trigger is evidence from the decision log, not a calendar.

## How to revise a skill

1. Identify the specific decision-log entries (`decisions/<year>/*.md`) that motivate the change
   — cite them in the rationale, don't revise from vague impression.
2. Edit the skill file directly. Keep changes scoped to what the evidence supports; don't
   rewrite unrelated sections opportunistically.
3. Commit the skill edit on its own, with a decision-log-style rationale in the commit message:
   what changed, which decisions motivated it, what's expected to be different going forward.
   A skill edit is a real change to how the agent behaves — it gets the same
   "why," not just "what," treatment as a code change.
4. If the revision reflects a broader strategic shift (not just a tuning tweak), consider adding
   a corresponding `decisions/` entry so the meta-decision itself is logged, not just the skill
   diff.

## Status as of Phase I (2026-07-26)

This is groundwork only — process, not execution. There is no decision-log history yet (the
season hasn't started; `decisions/` currently holds one pre-season entry). No skill has been
revised under this process yet. The first real revision is expected either after the first bye
week (enough waiver/trade decisions to evaluate) or at the end of the 2026 season, whichever
surfaces a clear enough signal first.
