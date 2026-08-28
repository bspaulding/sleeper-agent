---
name: draft-recap
description: Generate a tongue-in-cheek, graded (A-F) draft report card for the whole league as a shareable HTML report, after any draft (mock or real) completes. Use when asked for a draft recap, draft grades, or a report card — not for live-draft assistance (`draft`) or pre-draft ranking (`bigboard`).
---

# draft-recap

Yahoo Fantasy's old emailed draft-grade reports, sleeper-agent style: one A-F grade and a few
freeform superlative trophies for the whole league, in an over-the-top sports-radio voice,
grounded in our own big board rather than vibes.

## Prerequisites

- The draft is complete (every pick made).
- That value-season's big board is built (`bigboard` skill) — `draft recap` hard-stops
  otherwise, same as `draft board`.

## Get the data

```
sleeper-agent draft recap --draft-id <id> [--value-season <year>] --json
```

`--value-season` defaults to current-year-minus-1 (prints a notice when defaulted), same
convention as `draft board`. This prints one JSON object: per team (`draft_slot`, `roster_id`,
`team_name`, `mean_value_delta`), and per pick (`round`, `pick_no`, `name`, `position`,
`is_keeper`, `board_rank`, `vorp`, `value_delta`). `value_delta = pick_no - board_rank`: positive
means the player was still on the board later than their rank deserved (good value), negative
means they were reached for ahead of their rank. A `null` `board_rank`/`vorp`/`value_delta` means
the big board has no row for that player (mainly DEF) — leave it as "no data," don't invent a
number.

## Write the recap

**Persona**: an over-the-top sports-radio hot-take host — bombastic, confident, quotable, having
way too much fun. Roast and praise equally hard, but good-natured: this is a real league of
people you know, not strangers, so the target is ribbing, not mean-spirited. Stay in character
for every team's write-up, not just the extremes.

**Lean on the bit, not the box score.** The JSON data is there to find the *material* — the one
absurd reach, the one lucky steal, the one roster quirk worth razzing — not to be recited.
(Confirmed 2026-08-28, after the first real run read as too spreadsheet-y: cut the
number-dropping hard.) A team's write-up should read like a comedian riffing on a draft, not an
analyst's notes with jokes bolted on. Concretely: **at most one stat per team** (one `Δ`, one
rank, whatever's funniest — not both, and never a running tally of five picks in a row), and
spend the rest of the sentences on the bit: a scenario, a voice, a comparison, an insult with
some craft to it. If a team's whole story is "every pick was fine," don't summarize that
flatly — find the *angle* that's funny about a team with nothing to make fun of.

**Grades**: one A-F letter grade per team. Anchor loosely to that team's `mean_value_delta` —
real signal, not decoration — but don't linearly map it to a grade, and don't show your work.
Weigh it against your own read of roster construction the way a human draft analyst would, then
mostly keep that reasoning invisible; the reader sees the verdict and the joke, not the math.
Call out `is_keeper` picks as a keeper decision made seasons ago, not this draft's judgment call
— but only if it's actually funny to; skip it otherwise. 2-4 sentences per team, mostly bit.

**Trophies**: 3-6 freeform superlative awards across the whole league — invent them fresh each
run, there's no fixed list. Each should still be traceable to something real in the data (don't
invent a pick that didn't happen), but the trophy *name* and the one-liner around it are where
the effort goes — a flat "Team X had the best value" is a stat, not a trophy.

## Build and ship the report card

1. Load the `artifact-design` skill for the visual pass — this is a fun, shareable page, worth
   real design effort, not a plain table dump.
2. Write the finished HTML directly to a new file at
   `reports/draft-recap-<draft_season>-<draft_id>.html` (create the top-level `reports/`
   directory if it doesn't exist yet) — `draft_season`/`draft_id` come straight off the JSON
   output above. This is the exact file the `Artifact` tool publishes from.
3. Publish it with the `Artifact` tool from that path.
4. Commit the file to git with a short message (draft id, season, one-line summary of the
   headline grades/trophies). Committing the recap is this skill's normal job every run, not a
   one-off — push per whatever the invoking session's git workflow already does.
5. Report the Artifact URL and the committed file path back in chat.

## Not this skill's job

- Deciding *when* to run — nothing here watches for a draft finishing. Triggered by request.
- Emailing or otherwise notifying the league — publishing produces a link; sending it anywhere
  is a human call.
