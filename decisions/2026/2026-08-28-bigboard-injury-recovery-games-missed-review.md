---
date: '2026-08-28'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Brock Purdy
  - Lamar Jackson
  - Joe Burrow
  - Jayden Daniels
  - Daniel Jones
  - Garrett Wilson
  - Malik Nabers
  - Mike Evans
  - Tyreek Hill
related_wiki: []
---

## Summary

Triggered by a user question while building the printable big-board backup: "Brock Purdy is
-96.5 VORP?!" Verified the pipeline is computing correctly, but the *methodology* is blind to
"elite when healthy, missed half the season" — `vorp.py` computes VORP off season **totals**, not
per-game rate, and QB's replacement rank is just QB12 (only 1 starting QB slot), so a shallow
sample size swings a player's rank enormously. Scanned `data/vorp/2025.parquet` for
`games_played < 14 and vorp_per_game > 0` (missed a meaningful chunk of the season but still
produced at a clearly-above-replacement rate when playing) and found 27 candidates. Triaged to
the 8 with (a) the largest season-vs-per-game distortion and (b) a confirmed-healthy 2026 status,
researched each individually, and manually re-placed them — this is exactly the judgment-review
pass `.claude/skills/bigboard.md` describes, not a mechanical `bigboard build` step.

## Reasoning

**QB is most affected** because the league only starts 1 QB — replacement rank is QB12 by
straight season-point total, so missing 4-10 games (out of 17) craters a player's season total
against a full-season replacement baseline, even when their per-game rate was excellent.

- **Lamar Jackson** (181 -> 23): 13 GP in 2025 (vorp_season -61.1, vorp_per_game +0.48). Ravens
  camp reports (Aug 2026) describe him as "100% healthy" and sharper than ever. Historically a
  top-2-3 fantasy QB in full seasons on passing + rushing floor alone. Placed right behind Josh
  Allen.
- **Joe Burrow** (458 -> 24): Grade 3 turf toe + surgery limited him to 8 games (vorp_season
  -146.5 — the single worst distortion found). Fully cleared for 2026 ("no nagging injuries,"
  full camp participant). Elite full-season ceiling. Placed just behind Jackson, ahead of Drake
  Maye.
- **Daniel Jones** (163 -> 64): Torn Achilles Week 14 2025 (13 GP, vorp_season -48.5). Re-signed
  as the Colts' starter, full camp participant; 2025 pre-injury was a "renaissance" year (top-7
  completion%/YPA). Kept conservative — Achilles recoveries are historically inconsistent and his
  per-game bump (+1.45) was modest, not elite. Placed near Bo Nix.
- **Jayden Daniels** (525 -> 65): Missed 10 games across three separate injuries (knee,
  hamstring, elbow) — the worst raw distortion by rank movement. GM says he's "already
  jump-started" recovery, looked strong in camp. 2024 OROY with a Hurts-like rushing floor. Placed
  in the Hurts/Goff tier, not higher — three distinct injuries reads as more fragility risk than
  Jackson's or Burrow's single-injury profile.
- **Brock Purdy** (244 -> 85, the one that started this review): 9 GP in 2025 (vorp_season
  -96.5), but the *best* per-game VORP of the whole distorted group (+4.22 — ahead of
  Jackson/Stroud/Rodgers/Geno Smith). Fully recovered per his own camp comments, now throwing to
  Mike Evans (also moved below, same team). Placed as a mid-tier QB1 near Herbert/Mahomes — his
  ceiling reads as efficient-and-healthy, not truly elite, so not pushed as high as Jackson/Burrow.

**WR moves, more conservative** since the league's replacement level is deeper (WR/FLEX-eligible
pool), so the season-total distortion is smaller in relative terms — these are more "notably
underranked" than "broken."

- **Garrett Wilson** (196 -> 39): Knee injury (IR November) cost him the back half of 2025. Fully
  cleared, "back healthy and ready," expected to be the Jets' clear #1 target under new OC Frank
  Reich — the strongest, least-hedged positive signal in this whole review. Placed alongside Nico
  Collins/Davante Adams as full-value WR1/2.
- **Malik Nabers** (291 -> 68): Season-ending torn ACL + meniscus damage 4 games into 2025. Team
  says "reasonable to assume" a Week 1 2026 return, but Nabers himself won't commit to a date
  ("no target date, just stacking days"). Elite talent but real recovery-timeline risk — placed
  solidly WR2 (Drake London/Michael Pittman neighborhood), not at his pre-injury WR1 talent level.
- **Mike Evans** (224 -> 73): Two *separate* significant injuries in 2025 (hamstring strain,
  broken collarbone), not one bad-luck game — 8 GP. Signed with SF (now Purdy's receiver), plans
  to play Week 1 barring a minor camp groin issue. Kept conservative given age (33) plus a
  multi-injury season is a real risk profile. Placed near Justin Jefferson/CeeDee Lamb, a modest
  bump only.

**Explicitly reviewed and NOT promoted: Tyreek Hill** (season-vs-per-game gap was real — 4 GP,
vorp_per_game +3.25 — but he's still a free agent with no team, and per his agent there's no
return timetable as of the most recent public update ("no power in my left leg"). His current low
rank (304) is accurate, not a distortion; left untouched.

**Scope note:** 27 candidates matched the `games_played < 14 and vorp_per_game > 0` filter; the
other 19 (mostly WR/TE already ranked in a plausible 60-180 band, or players already off the
draft pool as 2026 keepers — Rashee Rice, Tucker Kraft, Zay Flowers) were left as-is. Not
re-litigated here; worth a look in a future pass if time allows, per the skill's "no automated
re-sweep schedule" note.

## Data

| Player | Pos | 2025 GP | Season VORP (old) | Per-game VORP | Old rank | New rank |
|---|---|---|---|---|---|---|
| Lamar Jackson | QB | 13/17 | -61.1 | +0.48 | 181 | 23 |
| Joe Burrow | QB | 8/17 | -146.5 | +0.61 | 458 | 24 |
| Daniel Jones | QB | 13/17 | -48.5 | +1.45 | 163 | 64 |
| Jayden Daniels | QB | 7/17 | -166.6 | +0.22 | 525 | 65 |
| Brock Purdy | QB | 9/17 | -96.5 | +4.22 | 244 | 85 |
| Garrett Wilson | WR | 7/17 | -72.7 | +4.09 | 196 | 39 |
| Malik Nabers | WR | 4/17 | -115.1 | +4.15 | 291 | 68 |
| Mike Evans | WR | 8/17 | -87.4 | +0.47 | 224 | 73 |
| Tyreek Hill | WR | 4/17 | -118.7 | +3.25 | 304 | 304 (unchanged) |

Sources checked (Aug 2026 web search, all dated within the last few weeks of camp):
- Purdy: SI/49ers Webzone camp reports, fully recovered
- Burrow: Bengals.com/CBS Sports camp reports, fully cleared
- Jayden Daniels: Newsweek/Yardbarker, GM Adam Peters comments
- Daniel Jones: ESPN, re-signed + full camp participant
- Lamar Jackson: Baltimore Ravens official site, Kyle Hamilton quote
- Garrett Wilson: NY Sports Day, fully cleared for camp
- Malik Nabers: Bleacher Report/Yahoo, uncertain Week 1 timeline in his own words
- Mike Evans: ESPN/Bleacher Report, signed with SF, plans to play Week 1
- Tyreek Hill: NFL.com/Yahoo, still a free agent, no return timetable

## Outcome

`data/bigboard/2025.csv`: 616 rows, 0 flagged (`value bigboard build --season 2025` confirms
clean, strict ordinal 1..616). All 8 rows carry an `[INJURY REVIEW 2026-08-28: ...]` rationale and
`log_ref` pointing at this entry. Printable big-board backup (`reports/bigboard-print-2026.html`)
regenerated from the updated file next.
