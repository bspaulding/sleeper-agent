---
name: news-research
description: Research news/injury/transaction context for rostered or targeted NFL players and file it into the wiki, following a consistent, deduplicated, sourced format. Run ahead of any lineup-affecting decision, or opportunistically when `wiki stale` flags a page.
---

# news-research

There is no scraper for this (see `PROJECT_PLAN.md` §5.4) — the LLM does this research directly
with WebSearch/WebFetch during normal runs, and this skill is what keeps that ad hoc process from
producing inconsistent, duplicated, or stale coverage.

## 1. Trigger conditions

Research when:

- **Always**: a rostered or trade/waiver/draft-targeted player, or their NFL team, ahead of a
  decision that could change based on new information (injury, depth chart, suspension, coaching
  change, etc.).
- **Opportunistically**: any page `wiki stale --days N` flags, worked through during a normal
  weekly pass rather than trying to cover the whole league at once.

Don't research every rostered player every run — that's wasted effort for players whose situation
hasn't changed. Use `wiki stale` to find out who actually needs a look, per item 4.

## 2. Source prioritization

There's no fixed source list — judge on the fly. Prefer, roughly in this order:

1. Team-issued injury reports and official transaction wires (most authoritative, least spin).
2. Beat reporters who cover the specific team (higher signal on depth-chart/role nuance than
   national outlets).
3. National NFL news outlets, for context and confirmation once the above exists.
4. Aggregator sites — use only when nothing better is available, and say so in the entry if the
   info is otherwise unconfirmed.

Skip anything that's pure speculation/rumor without a named, checkable source.

## 3. Filing convention

Append a dated, tagged, sourced entry to the page's `## News` section — one line per finding:

```
- YYYY-MM-DD [injury|depth-chart|trade|transaction] <one-line takeaway> ([source](<url>))
```

- Always include a link to the source article — never just a paraphrase with no citation.
- Put the entry on every page it's relevant to (a player page, their team page, or both) —
  **link, don't duplicate the summary**: the article is the source of truth, wiki entries are
  pointers plus a one-line takeaway.
- `wiki_tools/frontmatter.append_news_entry` (used internally by any future CLI assist) prepends
  new entries at the top of the section — newest first — so do the same by hand if editing
  directly: put the new line immediately under the `## News` heading, above older entries.

## 4. Check-before-you-write step

Before researching a page, read its existing `## News` section (including already-linked URLs)
and its `last_researched` date. This avoids two failure modes: re-researching something already
covered, and filing a near-duplicate entry for the same story from a second source pass. If the
story is already there, skip it — don't add a second entry citing a different outlet for the same
fact.

## 5. Frontmatter maintenance

After finishing a research pass on a page — **even if nothing new was found** — bump
`last_researched` to today's date. A confirmed "nothing new" is still information: it's what lets
tomorrow's `wiki stale` pass correctly skip this page instead of re-checking it for no reason.

## Notes

- A story relevant to multiple players (e.g. a coaching change affecting the whole offense) gets
  filed on the team page and cross-referenced with a one-line note on each affected player's page
  — not the full story copied onto every player page.
- Kickers get no research effort (`PROJECT_PLAN.md` §3 — no K in the starting lineup).
- Best ball scoring means no weekly start/sit — research should focus on roster-construction
  relevance (is this player still worth rostering, trading for, etc.), not "should he start this
  week."
