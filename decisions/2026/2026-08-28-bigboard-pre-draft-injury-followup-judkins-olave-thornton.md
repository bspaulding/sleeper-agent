---
date: '2026-08-28'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Quinshon Judkins
  - Chris Olave
  - Dont'e Thornton
related_wiki:
  - players/12512-quinshon-judkins.md
  - players/8144-chris-olave.md
  - players/12541-dont-e-thornton.md
---

## Summary

Manual follow-up (run a day ahead of the scheduled `sleeper-agent: pre-draft news sweep` Routine,
which still fires as planned at 2026-08-29T20:00Z / 1pm PT) on the three cases
`decisions/2026/2026-08-27-bigboard-injury-status-review.md` left open: **Quinshon Judkins**,
**Chris Olave**, **Dont'e Thornton**. Synced live Sleeper player data and ran a targeted news pass
on each per `.claude/skills/news-research.md`, explicitly checking whether the ambiguous/possibly
future-dated headlines that review flagged were real current signal or the date-scoping trap it
described.

## Reasoning

**Live data first.** `sleeper players sync` (2026-08-28) now shows Judkins and Olave with
`injury_status: None` (cleared) and `status: Active`; Thornton remains `Questionable`.

**Quinshon Judkins — no change.** Confirmed via NBC Sports/PFT that the current issue is still the
"nagging"/precautionary injury Todd Monken described around 2026-08-19-20, with no Week 1 concern.
The season-ending "fractured fibula/dislocated ankle vs. Bills" headlines the prior review flagged
as suspicious turned out to be dated **2026-12-21** — a Week 16 game that has not been played yet
relative to today. Confirms the date-scoping trap exactly as anticipated: search surfaces real
articles from later in the season, written as if "today," regardless of when the search is run.
Not acted on. Matches the prior review's existing wiki framing; no new material information.

**Chris Olave — no change.** Confirmed via NBC Sports that HC Kellen Moore attributed the Aug 25
medical-tent exit to having the wind knocked out of him in a hard fall, with no structural issue
found — matching the "wind knocked out" framing already in the wiki from the prior review. The
"concussion IR" headlines the prior review flagged turned out to date to **November 2024** — an
unrelated event from a prior season, not 2026 signal. Not acted on; no new material information.

**Dont'e Thornton — no change, but new context recorded.** Still hasn't played a preseason snap
(sat out both the Aug 13 opener and the Aug 20 Houston game), and the latest report has him working
"off to the side without pads" — genuinely unresolved, unlike the other two. His roster spot is a
real, live competition (Tucker/Nailor/Bech/Benson, one day before the Aug 30 3pm PT 53-man cutdown
deadline — the day *after* our draft). However, he currently sits at bigboard rank #476 (VORP
-148.7), far below the ~220-pick threshold that matters for a 180-pick, 15-round draft — per the
prior review's explicit scoping rule, a roster-bubble outcome here doesn't change any real
draft-day decision regardless of which way it breaks. Recorded the current context on his wiki
page for continuity (so a future in-season pass isn't starting from a stale "still recovering"
picture) but did not move his bigboard row.

## Data

`value bigboard build --season 2025` re-run after this pass: 616 rows, 0 added, 0 flagged — no rank
changes were needed for any of the three cases.

## Outcome

All three of the 2026-08-27 review's open cases are now resolved as "reconsidered, no bigboard
change" — two (Judkins, Olave) because the ambiguous search results were confirmed to be the
anticipated date-scoping artifacts rather than real signal, one (Thornton) because the real,
still-unresolved roster-bubble risk sits too far below the draft-relevant range to matter. Wiki
pages for all three updated with dated, sourced entries and `last_researched` bumped to
2026-08-28. The scheduled Routine firing tomorrow at 1pm PT will still run as a final safety net,
but per this pass there is no known open item it needs to catch for these three players.
