---
date: '2026-09-28'
kind: waiver
season: '2026'
week: 3
status: recommended
players_involved: ['12495', '4034']
related_wiki:
  - wiki/players/12495-ollie-gordon.md
related_decisions:
  - decisions/2026/2026-09-23-waiver-week3-weekly-review-hold-no-moves.md
---

## Summary

Recommend a claim on Ollie Gordon II (RB, MIA), FAAB bid **$18-$22** (target $20), funded by
dropping Kyle Pitts. `waiver recommend --season 2026 --roster-id 5` ranked Gordon dead last of the
top 10 (vorp -12.9, bid $0-$2) purely because our local `data/stats` weekly file is only synced
through Week 2 — it has no visibility into Sunday 9/27's Week 3 game, where starting Dolphins RB
De'Von Achane exited in the first quarter with a knee injury serious enough that HC Jeff Hafley
said postgame "it does not sound very optimistic," with an MRI scheduled Monday 9/28 (today) to
confirm. Gordon (RB2 → likely a real 2026 season-long lead-back opportunity if Achane's MRI is
bad) posted 37 yards and a TD in relief before himself battling cramps. This is exactly the
skill's "name entering the news cycle before the data catches up" pattern
(`.claude/skills/waivers.md`) — Gordon's trending count (2,096,255 adds) was the highest of any
player on our recommend list by nearly 20x, consistent with a real, sourced, breaking-injury signal
rather than noise.

## Reasoning

- **Injury signal is real and sourced**, not a rumor: ESPN, CBS Sports, NBC Sports/PFT, and
  Washington Times all independently reported the Sunday 9/27 exit and the coach's "not
  optimistic" quote; MRI pending as of this writing (2026-09-28). Treated as a genuine
  starting-role-change candidate per the skill's "obvious league-winner-tier addition" carve-out
  from the normal early-season low-bid rule — worth bidding above the tool's mechanical $0-$2
  suggestion, but not maxing out, since the MRI result isn't confirmed yet and Gordon himself left
  Sunday's game with cramping (unproven as a bell-cow workload, not just an injury question mark).
- **Roster fit**: `value roster --me` shows RB as our second-strongest position by avg VORP (10.8)
  already (Judkins, Henderson, Swift, Warren) — this isn't a bare-need add, it's a speculative
  stash on a plausible every-down role with real Week 4+ fantasy relevance. Roster is full at 15
  (`wiki/team/roster-philosophy.md`'s `QB,RB,RB,WR,WR,TE,FLEX,FLEX,DEF,BN×6` grid, no IR slot), so
  the claim needs a corresponding drop.
- **Drop candidate: Kyle Pitts** (TE, ranked outside `value rank`'s top 40 at the position,
  well behind Trey McBride #1 at 22.8 and Juwan Johnson at 5.2). We rostered 3 TEs; McBride is the
  clear starter and Johnson has been the better bench option in his own right this season. The
  2026-09-23 review held Pitts on the theory that Michael Penix's return would revive his target
  share — worth re-checking Week 3 box score results before this claim is submitted Tuesday, since
  local stats don't yet have Week 3 synced; if Pitts had a strong bounce-back game Sunday, swap the
  drop candidate for Juwan Johnson instead. Flagging this explicitly rather than deciding
  blind — commissioner should verify Week 3 Pitts/Johnson stat lines once available before
  finalizing which TE to cut.
- **Bid sizing**: $95 FAAB remaining, ~15 fantasy-relevant weeks left. Early-season guidance says
  bid low unless it's a real starting-role change from injury — this qualifies, but the MRI isn't
  confirmed and Gordon shares change-of-pace duties even in a best case, so $18-$22 (not a
  max/panic bid) balances the asymmetric upside against the real chance Achane's injury proves
  less severe than the coach's tone suggested.

## Data

- `waiver recommend --season 2026 --roster-id 5 --weeks-remaining 15 --top 20`: Ollie Gordon II
  RB, trending=2,096,255, vorp=-12.9 (stale, pre-Week-3), suggested bid $0-$2 (tool-computed,
  superseded by this entry's reasoning).
- `value roster --season 2026 --roster-id 5`: RB n=4 total_vorp=43.3 avg=10.8; TE n=3
  total_vorp=10.7 avg=3.6 (weakest bench position by count-adjusted depth).
- `value rank --season 2026 --position TE --top 40`: Trey McBride #1 (22.8), Juwan Johnson #8
  (5.2), Kyle Pitts unranked (outside top 40).
- Sources: [CBS Sports](https://www.cbssports.com/nfl/news/devon-achane-knee-injury-dolphins-chiefs-2026/),
  [NBC Sports/PFT](https://www.nbcsports.com/nfl/profootballtalk/rumor-mill/news/dolphins-not-optimistic-about-devon-achanes-knee-injury),
  [ESPN](https://www.espn.com/nfl/story/_/id/50044229/dolphins-rb-devon-achane-suffers-knee-injury-vs-chiefs),
  [CBS Sports (Gordon return)](https://www.cbssports.com/fantasy/football/news/dolphins-ollie-gordon-makes-return-to-sundays-game/).

## Outcome

Not yet executed — this routine has no Sleeper write access. Commissioner to place the FAAB claim
manually in Sleeper before the Tuesday 9/29 waiver deadline, confirming Week 3 Pitts/Johnson stat
lines first to pick the better drop candidate.
