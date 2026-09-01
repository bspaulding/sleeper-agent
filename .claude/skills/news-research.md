---
name: news-research
description: Research news/injury/transaction context for rostered or targeted NFL players and file it into the wiki, following a consistent, deduplicated, sourced format. Run ahead of any lineup-affecting decision, opportunistically when `wiki stale` flags a page, or whenever asked to "do a news sweep."
---

# news-research

There is no scraper for this (see `PROJECT_PLAN.md` §5.4) — the LLM does this research directly
with WebSearch/WebFetch during normal runs, and this skill is what keeps that ad hoc process from
producing inconsistent, duplicated, or stale coverage.

## 1. Trigger conditions

There are two distinct modes — don't conflate them:

- **Targeted lookup** (always): a rostered or trade/waiver/draft-targeted player, or their NFL
  team, ahead of a decision that could change based on new information (injury, depth chart,
  suspension, coaching change, etc.). Scoped to that specific player/team only.
- **Full sweep** (periodic, e.g. weekly, or whenever asked to "do a news sweep"): scoped by
  **time**, and covers the **whole league**, not just our own roster — every team's roster has an
  owner whose decisions interact with ours (trades, waiver competition), and a full sweep exists to
  catch anything that changes a player's *production outlook*: playing time or touches. Contract
  news, quotes, awards, and "leadership" narratives are not the target unless they carry a concrete
  role/snap-share signal — filter for that on every finding, not just at filing time.

  Work it in **two angles**, both required, not either/or:

  **Angle 1 — every NFL team.** One search per team (32 total, run several in parallel per batch —
  6-12 at a time worked well), phrased as team + 2-3 of that team's fantasy-relevant rostered
  players + "news/depth chart/injury", e.g. `"Denver Broncos Nix Sutton Harvey news <month> <year>"`.
  A bare `"<team> depth chart injury"` query mostly returns generic depth-chart-site links with low
  signal — naming actual rostered players in the query surfaces the specific stories. Skip
  kickers/IDP-only teams with no rostered skill player.

  **Angle 2 — every rostered player, league-wide.** Enumerate every player on every roster, not
  just our own:
  ```
  for i in 1..N: sleeper-agent sleeper roster show --roster-id <i> --season <year>
  ```
  (or read `data/sleeper/rosters/2026.parquet` directly and join against `players.parquet` for
  `name`/`position`/`team` — faster when doing all N rosters at once). Group by NFL team first so
  Angle 1's per-team searches double as first-pass coverage for most of these players; then run
  **targeted, name-specific searches** for anyone Angle 1 didn't clearly surface — especially
  players flagged `[INJ: ...]` or `[MOVED: ...]` by `value rank`/`value roster`, and any bench/depth
  name a team-level query skipped past.

  Procedure once both angles' raw results are in hand:
  1. Read `wiki/news-sources.md`'s `last_swept` frontmatter field (create the file with
     `last_swept: null` if it doesn't exist yet — treat `null` as "look back ~7 days" for the
     first sweep).
  2. For each finding, apply the production-impact filter above before deciding whether to file it.
  3. **Verify before filing a "new" injury**, don't take a search summary at face value — outlets
     sometimes disagree on details (e.g. "knee" vs. "ankle") that turn out to be the same incident
     reported inconsistently. One follow-up search naming the specific body part/date resolves this
     cheaply; filing two entries for what's actually one event creates false urgency.
  4. File it on whatever page(s) it concerns — an existing `wiki/players/*.md` page, or a **new
     one** via `sleeper-agent wiki scaffold` if the player doesn't have a page yet (e.g. a
     waiver-relevant player who was never rostered), plus the relevant `wiki/nfl-teams/*.md` page
     for team-level news (a story affecting multiple players on one team files once on the team
     page, cross-referenced — see Notes below).
  5. Bump `last_researched` on every page actually checked this sweep — including team and player
     pages where nothing new was found (see §5). At league scale this is most of them; that's
     expected and still worth recording, since it's what lets tomorrow's sweep (or `wiki stale`)
     trust the date instead of re-checking blind.
  6. **Commit and push in batches as you go** (e.g. every 6-12 teams), not one giant commit at the
     end — a league-wide sweep is dozens of tool calls and can run long; incremental commits mean
     partial progress survives an interruption.
  7. When the sweep finishes, update `wiki/news-sources.md`'s `last_swept` to the current
     date/time — this is the checkpoint the *next* full sweep reads, independent of any individual
     page's own `last_researched` date.

`wiki stale --days N` is still useful, but only as a secondary sanity check for the targeted-lookup
mode (e.g. "has this specific rostered player been looked at recently") — it is not how a full
sweep decides scope, since a player with no wiki page at all wouldn't show up in `wiki stale`
regardless.

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
