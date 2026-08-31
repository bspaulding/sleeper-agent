---
date: '2026-08-31'
kind: waiver
season: '2026'
week: null
status: recommended
players_involved:
  - MarShawn Lloyd
  - Josh Jacobs
related_wiki:
  - wiki/players/11581-marshawn-lloyd.md
  - wiki/players/5850-josh-jacobs.md
  - wiki/nfl-teams/GB.md
---

## Summary

Weekly news sweep (2026-08-31, first since the 2026-08-22 checkpoint) surfaced a confirmed,
dated, sourced roster-altering event: Packers starting RB Josh Jacobs was placed on the NFL's
Commissioner's Exempt List on 2026-08-30 (misdemeanor charges from a May domestic-abuse arrest),
cannot practice or play while on it, and has no fixed return date — his next court hearing isn't
until Nov 17, past Week 10. `waiver recommend` independently flagged MarShawn Lloyd (id 11581,
GB RB) at trending=412,569 — an order of magnitude above every other name on the list — which is
the market pricing in exactly this. Recommending a claim, not a logged pass, because this clears
the skill's bar for a "real, need-filling target": our roster's RB corps is thin (Emanuel Wilson
buried behind Price/Holani in SEA, TreVeyon Henderson in a committee with Stevenson in NE, Kareem
Hunt still an unsigned FA) and Lloyd projects as Green Bay's presumptive lead/early-down back for
at least several weeks in a competent offense, not a marginal depth add.

## Reasoning

- **Confirmed, not speculative.** Multiple independent outlets (CBS Sports, Yahoo Sports,
  ProFootballRumors, NBC Sports) all dated 2026-08-30 corroborate the exempt-list placement and
  that Jacobs will open the season unavailable. This is the resolution of the open item the
  2026-08-27 bigboard injury review flagged ("open NFL Personal Conduct Policy investigation with
  unclear suspension risk... worth a specific check in the next news sweep").
- **Timeline is genuinely open-ended, not a 1-week blip.** No suspension length has been announced
  and Jacobs' own legal process doesn't reach its next checkpoint (Nov 17) until after Week 10.
  Whatever the league ultimately decides, Lloyd is very unlikely to be a 1-and-done handcuff-only
  add — this reads as a multi-week-minimum window at worst, a change-of-role for the year at best.
- **Fills a real roster need, not just a hot name.** Cross-checked our own roster
  (`sleeper roster show --roster-id 5`): RB is our thinnest position by a clear margin (Wilson,
  Henderson, unsigned Hunt) with no established lead-role back. This is the "starting-role change
  from an injury/absence, a clear workhorse emerging" exception the waivers skill calls out as
  worth bidding above the low end for, even in Week 1.
- **Bid sizing.** `waiver recommend --season 2026 --roster-id 5 --weeks-remaining 17` returned
  Lloyd at `vorp=n/a bid=$1-$3` — the tool's suggested range is anchored on 2025 value-season VORP
  and hasn't caught up to a depth/backup player suddenly holding a starting job, exactly the
  "name entering the news cycle before the data catches up" case the skill describes, except here
  the underlying signal is confirmed fact (an exempt-list placement), not a rumor, so I'm not
  treating this as a speculative low bid. With FAAB at $100/100 remaining and 17 weeks left,
  budget pacing says stay conservative on noise but spend real budget on a clear workhorse
  opportunity — the trending count (412,569, ~7x the next name on the list) signals this will draw
  serious competing bids across the league. Recommending **$30** (well above the tool's range,
  meaningfully below going all-in) — enough to be competitive for a likely-contested claim while
  preserving most of the season's budget for further opportunities.

## Data

| Candidate | Position | Trending adds | Tool bid range | Recommended bid |
|---|---|---|---|---|
| MarShawn Lloyd (GB) | RB | 412,569 | $1-$3 | $30 |

Next-best options from the same `waiver recommend` run, for context (none cleared the bar for a
logged claim this week — either low VORP with no role-change story behind them, or a kicker):
Jacksonville Jaguars DEF (vorp=20.0, bid $4-$12, streaming-tier only, not a season-long need),
Justice Hill / Keaton Mitchell / Malik Davis / Jacob Saylors (RB depth, no confirmed role change),
Odell Beckham (WR, no confirmed 2026 signing found in this sweep — flagged for a follow-up check,
not acted on).

## Outcome

Recommended: claim MarShawn Lloyd (GB RB, sleeper_id 11581) for **$30 FAAB**. This run does not
place waiver claims (no Sleeper write access) — the commissioner needs to submit the bid manually
before Tuesday's processing.
