---
name: waivers
description: Decide FAAB waiver bids from sleeper-agent's suggested ranges — budget pacing across the season, when to bid $0. Use on Mondays ahead of Tuesday waiver processing (this league's waiver_day_of_week), or whenever a notable trending add appears.
---

# waivers

This league uses FAAB (`waiver_type: 2`, budget 100/season, 2-day clear cycle, processes
Tuesdays). `waiver recommend --me --season <year>` gives a ranked list of targets with a
**suggested bid range** per target, not a single number — picking the actual bid within (or
outside) that range is this skill's job.

## Budget pacing across ~17 weeks

The single biggest mistake FAAB waiver strategy can make is spending too much early on players
who turn out to be one-week overreactions. Before bidding:

- Check remaining budget (`waiver recommend`'s printed "FAAB budget remaining") against how many
  weeks are actually left in the fantasy-relevant season (through the fantasy playoffs, roughly
  week 17) — the tool's `--weeks-remaining` flag drives its range math, so pass a real estimate,
  not the default.
- Early season (weeks 1-4): bid toward the **low end** of the suggested range unless a player is
  an obvious league-winner-tier addition (a starting-role change from an injury, a clear workhorse
  emerging) — the goal is not to empty the budget on noise.
- Mid-season: bid range as suggested is a reasonable starting point; adjust up for a player filling
  a real roster need (check `value roster --me` for positional thinness) and down for pure depth.
- Approaching the fantasy playoffs (week 14+, this league's `playoff_week_start`): budget
  remaining matters less than closing out — bid more aggressively for anyone who could be a
  playoff-run difference-maker, since unspent FAAB has no value after the season ends.

## Weighing the suggested range down to one number

- The tool's range already reflects budget pacing and relative value (see
  `waiver/recommend.py`'s `suggested_bid_range`) — treat the **low end** as "I'd be happy to get
  this player but won't be upset losing the bid" and the **high end** as "this player meaningfully
  changes the roster, worth spending real budget."
- Positional need pushes toward the high end: cross-check `value roster --me` — a target at a
  position where the roster is below-replacement is worth more than the raw VORP ranking implies.
- A target with high trending count but low/unranked VORP (shows as `vorp=n/a` or a low number) is
  a name entering the news cycle before the data catches up — worth a speculative low bid, not a
  high one, until there's more signal (check the player's wiki page / run news-research first if
  time allows).

## When a $0 bid is correct

Not every waiver claim needs FAAB spent — Sleeper's FAAB system still processes $0 claims in
priority order (by whatever tiebreak the league uses) as long as nobody else bids. Use $0 when:

- The player is a low-value speculative add nobody else is likely to want (check trending count —
  if it's low and the position isn't scarce on this roster, don't spend budget defending against
  competition that probably isn't coming).
- Adding purely for roster depth/bye-week insurance rather than a real upgrade.

## Logging the decision

After deciding, file it: `decisions new --kind waiver --slug <slug> --season <year>`, recording
the actual bid chosen and the reasoning (why this number within/outside the suggested range).
