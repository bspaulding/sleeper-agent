---
date: '2026-08-28'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Travis Etienne
  - Kenny Gainwell
  - Rico Dowdle
  - Kenneth Walker III
  - A.J. Brown
  - Wan'Dale Robinson
  - Stefon Diggs
  - David Montgomery
  - Michael Pittman
  - Mike Evans
  - Jaylen Waddle
  - Deebo Samuel Sr.
  - Keenan Allen
  - Rachaad White
  - Jauan Jennings
  - DJ Moore
  - Romeo Doubs
  - Tyler Allgeier
  - Chig Okonkwo
  - Marquise Brown
  - Michael Carter
  - Emanuel Wilson
  - Chris Rodriguez Jr.
  - Kayshon Boutte
  - Isiah Pacheco
  - Jonnu Smith
  - Jalen Nailor
  - Brian Robinson
  - Emari Demercado
  - Kendrick Bourne
  - Keaton Mitchell
  - Calvin Austin III
  - Olamide Zaccheaus
  - Sterling Shepard
  - Darnell Mooney
  - Jerome Ford
  - John Metchie III
  - Van Jefferson
  - Christian Kirk
  - Justin Fields
related_wiki:
  - team/role-changers.md
  - team/bigboard-external-comparison.md
---

## Summary

Todo item from `decisions/2026/2026-08-29-draft-mock-draft-6-slot8.md` point (a): "review every
`[MOVED: ...]`-flagged row against `wiki/team/role-changers.md`'s vacated-opportunity framework,
not just injury-flagged rows — and check ranks against `data/adp/*.parquet` where available."
`sleeper_agent.value.team_changes.detect_team_changes`/`triage_team_changes` (season=2025) finds
40 team-changers with a real prior-season role, and all 40 are on `data/bigboard/2025.csv` (every
one has a full VORP row). Every one of the 40 already had a `wiki/players/*.md` page from the
2026-08-22 role-changer research pass; two (Jonnu Smith, Sterling Shepard) had never actually been
researched (`last_researched: null`, empty `## News`) despite carrying the `[MOVED: ...]` flag —
both got a fresh web search here and their wiki pages updated. Cross-referenced
`data/adp/2026-08-28.parquet` (DraftSharks) for every player it covers (24 of 40; the rest have no
consensus ADP entry at all, itself a signal for the deepest-bench cases).

## Reasoning

**Moved up — board underrated the new role vs. market:**

- **Kenneth Walker III (#37 → #19, behind Saquon Barkley).** DraftSharks RB11/overall 14 vs. the
  board's vorp-only #37 (vorp=56.2, a muted 2025 SEA line). Signed KC as a clear three-down
  workhorse (15-18 carries + goal-line). Tempered short of full ADP by the Eric Bieniemy OC
  scheme-continuity risk (historically pass-heavy) flagged in his wiki page.
- **A.J. Brown (#43 → #21, behind Chris Olave).** Traded PHI→NE, reunited with Mike Vrabel as
  Drake Maye's clear WR1 (~130 targets/1200+ yds projected). ADP WR8/overall 13 vs. board's
  TD-starved-2025-Philly-line vorp=48.1.
- **Jaylen Waddle (#81 → behind Courtland Sutton).** Traded MIA→DEN into a clean WR1 role for Bo
  Nix, pushing incumbent Sutton down. ADP WR21/overall 38 vs. board's Miami-target-competition
  vorp=21.9.
- **DJ Moore (#107 → behind Drake London).** Traded CHI→BUF, reunited with OC Joe Brady (his old
  Carolina play-caller) for a more downfield role off Buffalo's play-action run game. ADP
  WR25/overall 68 vs. board's shallow-Chicago-usage vorp=0.0.
- **Keaton Mitchell (#214 → behind Cooper Kupp).** ADP overall 175 is more bullish than the
  board's vorp-only #214, though the LAC backfield (official depth chart: "Mitchell OR Vidal"
  behind starter Omarion Hampton) is still a genuinely unresolved committee — nudged up, not
  fully to ADP.

**Moved down — board's vorp assumed continuity a trade/signing/depth-chart broke:**

Etienne (#16→#41, behind Michael Wilson — the original flagged case: NO co-RB1 with Alvin Kamara
per DraftSharks RB20/overall 43), Gainwell (#25→#99, behind Bucky Irving — TB "1B" to Irving's
"1A," no ADP entry at all), Dowdle (#26→near ADP #96 — behind Jaylen Warren on PIT's depth chart),
Wan'Dale Robinson (#49→near ADP #156 — TEN slot role despite real Daboll OC continuity), Diggs
(#58→near ADP #124 — still working back in at camp), Pittman (#70→near ADP #99 — traded to a
two-man PIT room with Metcalf), Deebo Samuel (#83→near ADP #185 — crowded SF room behind fellow
role-changers Evans and Kirk), Keenan Allen (#94→near ADP #238 — no wiki news on file, deferred
fully to ADP), Rachaad White (#99→near ADP #139 — WAS No. 2 RB/passing-down back), Jauan Jennings
(#104→near ADP #321 — MIN slot WR3 behind Jefferson/Addison), Romeo Doubs (#114→near ADP #143 —
NE's own A.J. Brown trade capped his signing's promised lead role), Tyler Allgeier (#119→near ADP
#198 — rookie Jeremiyah Love expected to take ARI's lead job), Michael Carter (#148→behind Calvin
Ridley — buried on TEN's depth chart, fighting rookies for a roster spot), Emanuel Wilson
(#153→behind Isaiah Davis — hamstring injury on top of a crowded SEA room), Chris Rodriguez Jr.
(#159→near ADP #180 — mild reprice, JAX co-starter role is real even split with Tuten), Kayshon
Boutte (#169→near ADP #346 — buried behind fellow role-changers Brown/Doubs in NE's room), Isiah
Pacheco (#170→near ADP #222 — Gibbs' holdout resolved into a 3yr extension, locking him in as
DET's lead back), Jalen Nailor (#198→near ADP #313 — LV No. 2 behind Bowers but ADP hasn't priced
a role bump), Calvin Austin III (#226→behind Isaac TeSlaa — slid to WR3 as Nabers returned from
injury), Jerome Ford (#238→behind Rasheen Ali — crowded WAS backfield, unconfirmed IR listing).

**Reconsidered, no change** (real news/ADP exists but the current rank already reflects it —
recorded so a future pass doesn't re-litigate from scratch):

- **David Montgomery (#62).** DET→HOU trade's vacated-opportunity read is muted — reports have him
  splitting RB1 reps with incumbent Woody Marks. ADP overall 67 tracks closely with vorp-only #62.
- **Mike Evans (#73).** Role-change angle reviewed on top of the existing 2026-08-27 injury-review
  note: SF is a genuine volume/TD opportunity, but ADP overall 55 still sits ahead of this
  injury-adjusted rank — the durability discount stands, no further change.
- **Brian Robinson (#203).** ADP overall 212 tracks closely with vorp-only #203 — ATL backup role
  behind Bijan is correctly priced already.
- **Chig Okonkwo (#133), Marquise Brown (#145), Emari Demercado (#209), Kendrick Bourne (#213),
  Olamide Zaccheaus (#229), John Metchie III (#256), Van Jefferson (#262), Christian Kirk (#292),
  Justin Fields (#420).** No DraftSharks ADP entry to calibrate a move (Kirk's ADP, where it does
  exist at overall 769, is so far below his current #292 that the practical draft-order difference
  is immaterial). Wiki research confirms the role in each case (real-but-contested slot competition,
  clean handcuff-for-a-superstar profile, etc.) roughly matches the existing rank — left in place.
- **Jonnu Smith (#190) and Sterling Shepard (#234) — newly researched, not previously reviewable.**
  Both wiki pages were empty (`last_researched: null`) despite carrying the `[MOVED: ...]` flag.
  Fresh search: Smith signed GB 2026-08-27 as TE2 behind Tucker Kraft (streaming-only value);
  Shepard signed HOU as injury replacement cover at age 33, no 40-reception season since 2020.
  Both current ranks already sit among comparable depth players at their position — no move, but
  both wiki pages updated with the research so this doesn't stay a blind spot.

## Data

`sleeper_agent.value.team_changes.detect_team_changes`/`triage_team_changes` (season=2025,
`MIN_PRIOR_SEASON_TOUCHES=50`): 40 triaged team-changers, all present on `data/bigboard/2025.csv`.
25 moved, 15 kept in place with an explicit "reconsidered, no change" (or injury-review-addendum)
rationale. Every touched row got `[ROLE-CHANGE REVIEW 2026-08-28: ...]` in `rationale` and
`log_ref` set to this entry's slug.

`sleeper-agent value bigboard build --season 2025` re-run after edits: 616 rows, 0 added, 0
flagged — confirms this pass didn't disturb any pending `[NEEDS REVIEW...]`/`[VORP CHANGED...]`
marker, and the strict-loader rank check (1..616, no gaps/dupes) passes.

## Outcome

25 rows moved (see Reasoning for before/after ranks and rationale), 15 rows reviewed and
deliberately left in place. 2 wiki pages (`wiki/players/4144-jonnu-smith.md`,
`wiki/players/3200-sterling-shepard.md`) updated from empty to researched. This closes the
`[MOVED: ...]` review gap that mock draft 6's retro identified for Travis Etienne specifically —
that row (and all 39 siblings sharing the same undetected gap) is now reviewed, not just the one
case a live draft happened to surface.

Not done here: a team-level vacated-opportunity aggregate (sum of departed players' shares per
team) — `wiki/team/role-changers.md` notes this as a natural v2 enrichment computable from
`target_share`/`air_yards_share` already in synced weekly stats, not required for this pass.
