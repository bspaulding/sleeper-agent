---
name: trades
description: Decide when to propose a trade, how to evaluate an incoming offer, and how much to weigh trade evaluate/propose's numbers against team-building narrative and roster fit. Use ahead of the week-11 trade deadline, or whenever an offer comes in.
---

# trades

`trade evaluate --give <ids/picks> --get <ids/picks>` gives a structured value comparison
(value delta, positional totals on both sides — pass `--json` to quote it directly into a
decision log entry). `trade propose [--target-roster-id N | --all]` scans for value-balanced
candidate packages ranked by a plausibility heuristic. Neither tool decides accept/reject/send —
that's this skill's job.

## When to propose vs. wait

- Propose when `trade propose --all` surfaces a package with strong plausibility (need-filling on
  both sides, not just balanced value) — those are the ones most likely to actually get accepted.
- Don't propose purely-value-balanced-but-need-blind packages just because the math clears
  tolerance — check `value roster` for both rosters first; a trade that's numerically fair but
  doesn't address either team's actual construction gap is unlikely to be accepted and wastes a
  negotiation.
- Trade activity should ramp up approaching the week-11 trade deadline (this league's
  `trade_deadline` setting) — a marginal-value trade that improves roster fit is worth more
  urgency close to the deadline than in week 3.

## Evaluating an incoming offer

1. Run `trade evaluate` with the offer as given (our real `--give`/`--get` from our perspective).
2. Check the raw value delta — but don't stop there. Cross-reference:
   - **Roster fit**: does either side of the offer fix a real need (`value roster --me`) or bye-week
     /injury-depth gap? A value-neutral or even slightly value-negative trade can still be worth it
     if it fixes a structural problem the VORP numbers alone don't capture (e.g. we're one injury
     away from a start-worthy hole at a position).
   - **Team-building narrative** from the wiki: check `wiki/league/opponents/<roster_id>.md` if it
     exists for notes on this GM's tendencies — a team known to overpay for a specific position
     after a season-altering injury, for instance, might make a "fair" offer from them still
     lopsided in disguise.
   - **Best-ball context** (`PROJECT_PLAN.md` §3): since Sleeper auto-optimizes the starting
     lineup, value here is about season-long roster construction, not "does this help me start a
     better lineup this week" — don't weigh short-term matchup fit into the decision.
3. A marginal loss that improves positional balance (fixes a real need at real but modest value
   cost) is often worth accepting — see the "roster fit" point above. A marginal *gain* that makes
   the roster more lopsided (more depth at an already-strong position) is often not worth it even
   though the math says yes.

## Logging the decision

Every trade decision (sent, accepted, rejected, or countered) gets a
`decisions new --kind trade --slug <slug> --season <year>` entry — quote the `trade evaluate
--json` output into the Data section, and use Reasoning for the roster-fit/narrative judgment that
the numbers alone don't capture. This is what makes the decision log useful for the season-end
skill self-revision review (`PROJECT_PLAN.md` §9) — a trade that looked good on paper but didn't
work out is only useful to learn from if the reasoning was written down at the time.
