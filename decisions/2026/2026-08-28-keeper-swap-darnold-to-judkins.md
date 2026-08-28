---
date: '2026-08-28'
kind: keeper
season: '2026'
week: null
status: executed
players_involved:
  - Sam Darnold
  - Quinshon Judkins
  - Stefon Diggs
  - Bo Nix
related_wiki:
  - wiki/team/keeper-strategy.md
  - wiki/league/season-2026.md
  - wiki/league/projected-keepers-2026.md
---

## Summary

Revisits `decisions/2026/2026-08-23-keeper-diggs-r7-darnold-r14.md` after the
2026-08-27 postseason-VORP fix (`decisions/2026/2026-08-27-bigboard-season-type-postseason-fix.md`)
regenerated the 2025 VORP board that decision's surplus math was built on. **Recommendation:
keep Diggs (R7), swap Darnold (R14) out for Quinshon Judkins (R8).** Not yet executed in
Sleeper — today (2026-08-28) is the keeper deadline, so this needs to be set in the app before
end of day.

## Reasoning

**Why re-open this at all.** The Aug 23 decision computed keeper surplus from VORP figures that
included postseason games (the bug fixed 2026-08-27). Darnold's team won the Super Bowl, so his
old total included ~4 extra playoff games — his surplus number was built on inflated input and
needed to be re-checked once the underlying data changed, same as any other derived analysis.

**Recomputed round baselines** (2025 VORP board, corrected, 12-team snake):

| Round | Old baseline (pre-fix) | New baseline (post-fix) |
|---|---|---|
| R7 | 14.1 | 14.6 |
| R8 | 2.2 | 7.0 |
| R14 | −62.9 | −49.5 |
| R15 | −74.0 | −57.5 |

**Recomputed surplus** (fresh `draft keepers --me --season 2026`):

| Player | Cost | VORP old → new | Surplus old → new |
|---|---|---|---|
| Stefon Diggs | R7 | 62.3 → 38.1 | +48.2 → **+23.5** |
| Sam Darnold | R14/R15* | 7.0 → −30.5 | +69.9 → **+19.0 (R14) / +27.0 (R15)** |
| Quinshon Judkins | R8 | (rejected pre-fix, +25.3) → 34.1 | +25.3 → **+27.1** |

\* CLI's `KeeperEligibleUndraftedDefault` still hard-codes R15 for undrafted/FA players
(`todo.md` tracks replacing it with a real ADP lookup); the house ADP−1 rule was applied by hand
in the Aug 23 decision to get R14. Not re-derived here since it doesn't change the conclusion
either way.

**Why Judkins over Darnold, given the surplus numbers are close either way:**

- Darnold's surplus is positive only because the R14/R15 baseline is very low — his own
  corrected production is now **below replacement** (−30.5 VORP). This is exactly the
  "late-round surpluses are inflated" trap `wiki/team/keeper-strategy.md` already warns about:
  check absolute production, not just the surplus number, especially at cheap late-round cost.
- Judkins' surplus is positive because he is an actually-productive, currently-healthy starting
  RB (+34.1 VORP) — real value, not a baseline artifact.
- **Judkins' injury flag (left open by `2026-08-27-bigboard-injury-status-review.md`) is now
  resolved.** That review couldn't tell whether ambiguous search hits about a "season-ending"
  injury were current or leftover noise. A fresh, date-scoped search today confirms the
  season-ending fibula fracture/ankle dislocation was his **2025** injury; the current 2026 issue
  is a minor "nagging" ailment, and Browns HC Todd Monken says he's "not worried" and doesn't
  expect Judkins to miss the opener
  ([NBC Sports](https://www.nbcsports.com/nfl/profootballtalk/rumor-mill/news/todd-monken-quinshon-judkins-dealing-with-nagging-injury-out-as-a-precaution),
  [SI](https://www.si.com/onsi/fantasy/injuries/quinshon-judkins-injury-rb-receives-positive-fantasy-update-after-missing-practice)).
- **Best-ball changes which position's bench value actually gets realized — corrected
  2026-08-28, see below.** This league is `best_ball: true` (`wiki/team/roster-philosophy.md`),
  and per `wiki/team/rookie-evaluation.md` there is **no way to actively stream a hot
  waiver-wire QB into the lineup** in this format — no in-season lineup management is modeled or
  practiced by this team at all. That rules out treating a backup QB as cheap streamable
  insurance (an earlier pass at this reasoning claimed the opposite and was wrong — see
  correction note). What the asymmetry actually is: a backup QB has no active lever to extract
  value beyond his own raw production, and this is a single-QB-slot league where a QB2 rarely
  sees the field regardless. Skill-position bench depth, by contrast, passively captures spike
  weeks via the auto-optimizer every week just by being rostered, no lineup decision required —
  exactly what `best_ball: true` rewards. That favors Judkins' bench/keeper value over a backup
  QB's, via the opposite mechanism from the original (wrong) framing, not the same one.

**Two wrong arguments considered and corrected along the way:**

1. An earlier pass argued Darnold was unnecessary because "we already have a starter in Bo Nix"
   (31.9 VORP, healthy, confirmed DEN starter). That's **incorrect** — Nix is not being kept (his
   own surplus is −5.7, negative, so he's correctly not a keeper candidate), which means he
   returns to the open draft pool at the live draft exactly like any other non-kept player,
   Darnold included. The current roster snapshot (`value roster --me`) reflects who's on the
   roster *today*, not who's guaranteed to be on the 2026 team after the draft. **Don't treat an
   other-position player's presence on the current roster as "coverage" for a positional need
   unless that player is also being kept.**
2. A second pass argued a backup QB matters less because "QB is easily streamable off waivers in
   a 1-QB league." Also **incorrect** — this is a `best_ball: true` league with no active
   in-season lineup management; per `wiki/team/rookie-evaluation.md` there's no way to actively
   stream a hot waiver-wire QB into the lineup here at all. The corrected version of this
   argument (above) actually points the other way mechanically — a backup QB has *no* lever to
   extract extra value beyond raw production, while skill-position bench depth passively cashes
   spike weeks via the auto-optimizer — but happens to still favor the same conclusion.

Neither error changes the recommendation (the production-quality argument above holds
independent of both), but both are recorded here so they aren't repeated: this decision was
revised twice over one day, and each revision should be checked against this league's actual
mechanics (best-ball scoring, no active streaming, non-kept players returning to the pool) rather
than generic redraft-league intuition.

## Data

- `draft keepers --me --season 2026`, run 2026-08-28 against the post-fix `data/vorp/2025.parquet`.
- Round baselines: `data/bigboard/2025.csv` (post-fix), sorted by rank, averaged in 12-pick buckets.
- `value roster --me --season 2025`: QB total_vorp=1.4 (n=2: Nix 31.9, Darnold −30.5), RB
  total_vorp=75.1 (n=4: Henderson 71.5, Judkins 34.1, Hunt 10.7, Wilson −41.2), WR
  total_vorp=−152.4 (n=6, weakest position on the roster), TE total_vorp=−6.7 (n=2).
- `wiki/players/12512-quinshon-judkins.md`, `wiki/players/4098-kareem-hunt.md` (unsigned FA, no
  team — excluded from consideration despite a nominally high surplus), `wiki/players/1339-zach-ertz.md`
  (unsigned FA + ACL recovery — excluded), `wiki/players/4943-sam-darnold.md`,
  `wiki/players/11563-bo-nix.md`.
- Fresh 2026-08-28 web search on Judkins' current injury status (sources linked above).

## Outcome

Executed — keeper selection updated in Sleeper from Darnold to Judkins on 2026-08-28, ahead of
the deadline. Still to confirm: `is_keeper` flags on the draft object's `/picks` endpoint once
they appear close to draft night (same caveat as the original 2026-08-23 decision).
