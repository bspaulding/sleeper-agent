---
last_swept: '2026-09-01T13:08:55+00:00'
---

# News sweep checkpoint

Tracks the last time a **full** news-research sweep ran (time/source-scoped, not player-scoped —
see `.claude/skills/news-research.md` §1). After each full sweep,
update `last_swept` to the date/time the sweep completed.

This is separate from the per-page `last_researched` frontmatter on individual
`wiki/players/*.md` / `wiki/nfl-teams/*.md` pages, which tracks targeted-lookup research on that
specific page.
