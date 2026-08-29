---
date: '2026-08-28'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Joe Burrow
  - Lamar Jackson
  - Drake Maye
  - J.J. McCarthy
related_wiki:
  - wiki/team/draft-strategy.md
---

## Summary

Follow-up to [[2026-08-28-bigboard-def-vorp-research-streaming-recommended]]'s DEF predictiveness
research, this time asking the user's follow-up question directly: is `vorp_season`'s
year-over-year predictiveness the same across QB/RB/WR/TE, or does it vary enough to matter? It
varies. All four look similar-and-strong on the raw full-population number (QB r=+0.696, RB
r=+0.681, WR r=+0.739, TE r=+0.731), but that's misleading for QB specifically: restricting to
players with ≥8 games played in *both* years of a pair (i.e., comparing real starters to
themselves, not counting "played vs. never played" pairs) collapses QB to r=+0.399 while RB/WR/TE
barely move (0.667/0.713/0.679). **Among established starters, QB is the most volatile of the
four core positions year over year, not the most stable.** Unlike the DEF finding, this doesn't
justify excluding QB from the ordinal board (r=0.40 is still real signal, and there's no
DEF-style "streaming beats ranking" alternative for a single-QB league) — the fix is judgment
calibration, not exclusion: `wiki/team/draft-strategy.md`, `bigboard.md`, and `draft.md` all
updated to say raw QB VORP should be weighted less heavily than RB/WR/TE VORP at the same
tier-distance during hand review.

## Reasoning

- **Methodology, reused from the DEF work.** Same `compute_vorp` this repo already runs for real
  (`cli/src/sleeper_agent/stats/vorp.py`), same league `scoring_settings`/`roster_positions`/
  `num_teams` (from `data/sleeper/league/2025.parquet`), same 2018-2025 nflverse
  `load_player_stats` pull, same pure-Python Pearson/Spearman (no numpy/scipy in this venv). For
  each of QB/RB/WR/TE, pooled every consecutive-year pair's `vorp_season(year N)` vs.
  `vorp_season(year N+1)` for players present in both years.
- **The full-population number is inflated by roster mechanics for QB specifically, not real
  predictability.** A league only carries 1-2 real QBs per team, so a backup who plays 0 games
  two years running contributes an easy "both near the deeply-negative floor" pair that inflates
  correlation without reflecting any actual predictive skill. RB/WR/TE have much deeper real
  roster churn (committee backfields, WR3/4 rotation, streaming TEs), so restricting to real
  starters doesn't change their story much — but for QB it changes everything: full-population
  r=+0.696 collapses to r=+0.399 once limited to players with ≥8 games in both years of the pair
  (n=182, vs. 424 unfiltered). RB/WR/TE hold at 0.667/0.713/0.679 (vs. 0.681/0.739/0.731
  unfiltered) — real starters at those positions really do carry their production forward; real
  QB starters mostly don't, at least not on raw season-total VORP alone.
- **Plausible real-world mechanism, not just a statistical artifact.** A QB's fantasy point total
  leans heavily on TD rate and game script, both of which are known to regress hard year to year,
  and a QB's raw season total is uniquely exposed to one injury wiping out most of a season (see
  Burrow's -146.5 `vorp_season` from 8 games played, per
  [[2026-08-28-bigboard-injury-recovery-games-missed-review]]) in a way a timeshare RB or a
  target-share WR/TE's role tends not to be — role/opportunity persists into next year more
  directly than QB scoring variance does.
- **This retroactively explains a pattern already visible on the board, rather than predicting a
  new one.** QB is by far the most hand-overridden position on `data/bigboard/2025.csv` already —
  Burrow, Lamar Jackson, Drake Maye, and J.J. McCarthy all carry manual injury/role-change
  rationale overriding raw VORP rank. That wasn't previously understood as a *position-level*
  pattern (each override was reasoned individually, case by case); this research gives a
  quantitative reason those keep happening specifically at QB and should keep being expected
  there, not treated as one-off surprises each time.
- **Decision: calibrate review-pass judgment, don't change the ranking mechanism.** Unlike DEF
  (where the in-season streaming finding gave a clean alternative strategy and justified full
  exclusion from the ordinal merge), QB's r=0.40 is still real, useful signal, and a single-QB
  league has no equivalent "just stream it" escape valve. The right response is qualitative: when
  reviewing a QB row during the `bigboard` skill's pass, situational context (scheme/O-line
  continuity, injury-recovery ceiling, rushing floor surviving bad passing luck) should move a QB
  row further from its raw-VORP slot than the same context would move an RB/WR/TE row — codified
  in `wiki/team/draft-strategy.md`'s new "QB raw VORP is the least reliable of the four core
  positions" section, referenced from both `bigboard.md`'s step-3 review-pass bullet and
  `draft.md`'s live-draft QB-speculative-bet paragraph.

## Data

- Pooled 2018-2025 `vorp_season` year-over-year Pearson r, full population vs. ≥8-games-both-years:
  QB 0.696→0.399 (n 424→182), RB 0.681→0.667 (n 792→464), WR 0.739→0.713 (n 1219→747), TE
  0.731→0.679 (n 677→389). For reference, DEF's pooled full-population r was 0.307
  ([[2026-08-28-bigboard-def-vorp-research-streaming-recommended]]).
- Analysis via a throwaway script (not committed), reusing `compute_vorp` +
  `nflreadpy.load_player_stats`/`load_ff_playerids` for 2018-2025.
- Docs updated: `wiki/team/draft-strategy.md` (new section + `last_updated` bump),
  `.claude/skills/bigboard.md` (step-3 review-pass bullet), `.claude/skills/draft.md` (QB
  speculative-bet paragraph).
- No code/ranking-mechanism changes — this is a judgment-calibration finding, not a mechanical
  one.

## Outcome

`wiki/team/draft-strategy.md`, `.claude/skills/bigboard.md`, and `.claude/skills/draft.md` now
document that QB rows deserve more hand-review skepticism toward raw VORP than RB/WR/TE rows at
the same tier-distance, with the r=0.40-vs-0.67-0.71 numbers as the concrete backing. No change to
`compute_vorp`, `merge_bigboard`, or the ordinal insertion mechanism — this is guidance for the
human/LLM review pass, not a mechanical rule.
