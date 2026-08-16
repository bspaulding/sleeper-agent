---
last_swept: null
---

# News sweep checkpoint

Tracks the last time a **full** news-research sweep ran (time/source-scoped, not player-scoped —
see `.claude/skills/news-research.md` §1). `last_swept: null` means no full sweep has run yet
under this model; treat that as "look back ~7 days" for the first one. After each full sweep,
update `last_swept` to the date/time the sweep completed.

This is separate from the per-page `last_researched` frontmatter on individual
`wiki/players/*.md` / `wiki/nfl-teams/*.md` pages, which tracks targeted-lookup research on that
specific page.
