---
date: '2026-08-09'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - Lamar Jackson
  - Joe Mixon
  - Alvin Kamara
  - James Conner
  - Aaron Jones
  - Baker Mayfield
  - Najee Harris
  - Jonnu Smith
  - Zach Ertz
  - Kareem Hunt
  - Jerry Jeudy
related_wiki: []
---

# Mock draft — 1392286240727908352 (--value-season 2024)

Rehearsal mock draft ahead of the real 2026 draft (Sept 5). Ran `draft board --draft-id
1392286240727908352 --value-season 2024` for a `--watch` stretch, then manual refreshes for the
rest once the background watcher was killed by request.

## My picks (in order taken)

1. Lamar Jackson (QB)
2. Joe Mixon (RB)
3. Alvin Kamara (RB)
4. James Conner (RB)
5. Aaron Jones (RB)
6. Baker Mayfield (QB)
7. Najee Harris (RB)
8. Jonnu Smith (TE)
9. Zach Ertz (TE)
10. Kareem Hunt (RB)
11. Jerry Jeudy (WR)

Note: value-season is 2024, not 2025 — `stats sync --season 2025` fails because the installed
`nfl_data_py` (0.3.3) hardcodes the old `player_stats` nflverse release, which nflverse renamed to
`stats_player` months ago (`stats_player_week_2025.parquet` exists there right now). This is a
library/pipeline bug, not a real data-publishing lag — 2025 data is available. This rehearsal ran
on last-known-good 2024 VORP rather than current-season data as a result. Re-run against real 2025
VORP once the sync path is fixed, before trusting rankings for the real draft.

## Final best-available board (end of draft)

Best available by value:
 1. Sam Darnold               QB  vorp=   37.6
 2. Pat Freiermuth            TE  vorp=   28.0
 3. Austin Ekeler             RB  vorp=   26.6
 4. Tyreek Hill               WR  vorp=   25.0
 5. Justice Hill              RB  vorp=   13.3
 6. Rashod Bateman            WR  vorp=    8.4
 7. Calvin Ridley             WR  vorp=    7.0
 8. Alexander Mattison        RB  vorp=    4.4
 9. David Njoku               TE  vorp=    1.7
10. Jerome Ford               RB  vorp=    0.0
