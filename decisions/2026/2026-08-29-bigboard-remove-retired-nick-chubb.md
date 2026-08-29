---
date: '2026-08-29'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Nick Chubb
related_wiki:
  - wiki/players/4988-nick-chubb.md
---

## Summary

Found during a full top-180 news-research sweep (`decisions/2026/2026-08-29-draft-mock-draft-8-slot8.md`'s follow-up): Nick Chubb retired August 22, 2026 after not re-signing with any team following March free agency. He was still sitting on `data/bigboard/2025.csv` at rank 165 with a real (negative) VORP, because — per `bigboard.md`'s own "known sharp edges" note — nothing automatically removes a stale row when a player drops off entirely. This is exactly that maintenance case: mechanical deletion, not a ranking judgment call.

## Reasoning

Retired players have zero draft relevance and shouldn't occupy a board slot, however low-value. Removed the row and renumbered every subsequent rank down by one to keep the strict 1..N sequence `draft board` requires (was 623 rows 1-623, now 622 rows 1-622).

## Data

- `data/bigboard/2025.csv`: deleted the Nick Chubb row (old rank 165, sleeper_id 4988), renumbered ranks 166-623 → 165-622.
- Verified post-edit: 622 rows, ranks strictly 1..622 with no gaps/duplicates (read-only `csv.DictReader` check — `sleeper-agent value bigboard build` itself was blocked by this session's Bash auto-mode classifier, so the strict-ordering check that command would normally do was reproduced by hand instead).
- Source: `wiki/players/4988-nick-chubb.md`, filed during the batch-AF news-research pass (retirement announced 2026-08-22, no team signed him after March free agency).

## Outcome

Row removed, board renumbered. No other rows touched — this is scoped narrowly to the one confirmed-retired player found during the sweep, not a broader review pass.
