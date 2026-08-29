---
date: '2026-08-29'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Josh Jacobs
  - Rashee Rice
related_wiki:
  - wiki/players/5850-josh-jacobs.md
  - wiki/players/10229-rashee-rice.md
---

## Summary

Follow-up to [[2026-08-29-bigboard-top250-news-sweep-promotions]]: that pass only promoted
players on good news, and never assessed anyone for a *demotion* even though the same research
sweep had already surfaced two real downside-risk items (Josh Jacobs' open legal matter, Rashee
Rice's rehab-disrupting jail stint) that got flagged but never acted on. This entry closes that
gap for those two specific players — a small, targeted pass, not a broader downside review.

## Reasoning

- **Josh Jacobs** (was rank 17, vorp 69.3, clear RB1 tier → rank 27): open legal matter tied to
  a May 2026 domestic-abuse arrest, investigation reportedly still unresolved, no charges or
  league discipline announced as of this research, and the team is playing him as a normal
  starter (minor groin injury, expected fine for Week 1). Deliberately a **modest** nudge, not a
  crash — no suspension has actually been handed down, and the situation has been quiet for
  roughly three months. Overreacting to an undischarged legal matter would be its own mistake;
  the point is pricing in real tail risk on an elite pick, not predicting an outcome. Revisit
  immediately if the league or team takes any action.
- **Rashee Rice** (was rank 138, vorp -15.7, already discounted → rank 154): two separate
  threads here, and they cut opposite ways. The NFL's personal-conduct investigation into
  unrelated allegations was **closed with no discipline** — that removes risk, not adds it. The
  actual reason for demotion is narrower: he's rehabbing recent knee surgery, and that rehab was
  disrupted by a 30-day jail stint (probation violation), which threatens a clean Week 1
  ramp-up. This is an availability/rehab-timeline demotion, not a legal-risk one.

## Data

- Source news: `wiki/players/5850-josh-jacobs.md`, `wiki/players/10229-rashee-rice.md` (filed
  during the batch-AA and batch-AC research passes respectively).
- `data/bigboard/2025.csv`: both rows removed from their old position and reinserted at the
  ranks above (Jacobs above TreVeyon Henderson, Rice above Ty Johnson), all rows shifted
  accordingly, renumbered strictly 1..622 (verified via read-only `csv.DictReader` check, same
  workaround as the prior two bigboard entries this session — `value bigboard build`'s own
  ordering check was not re-run).
- `log_ref` set to this entry's slug on both rows.

## Outcome

Both demotions applied, board still 622 rows / strict 1..622. This was a narrowly-scoped pass
(exactly the two players already flagged as an open gap) — not a systematic re-scan of the other
~183 researched players for missed downside signals. If a broader downside-risk pass is wanted
later, that's a separate task.
