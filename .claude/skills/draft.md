---
name: draft
description: Sit in on a live draft (real or mock) on the user's behalf — watch picks land, detect when it's our turn, and make the pick judgment call fast under the clock. Use whenever asked to run/watch/join a draft live, as distinct from `bigboard` (pre-draft ranking) or `keepers` (pre-deadline, untimed).
---

# draft

An agent can't attach to `draft board`'s default Textual TUI — it's interactive and blocking.
Run it as a single background, non-interactive watcher instead.

## Prerequisites

- The season's big board is built (`bigboard` skill) — `draft board` requires
  `data/bigboard/<season>.csv`.
- Know the draft's identity and our seat:
  - Mock draft: `--draft-id <id> --draft-slot <n> --num-teams <n>` (no league behind a mock, so
    `--num-teams` isn't auto-discoverable — pull `settings.teams` from `GET /v1/draft/<id>` if
    unstated).
  - Real draft: `--league-id <id> --me` (or `--roster-id <n>`).

## Watching the draft

One process, one `Monitor` call — no separate Bash `run_in_background` process and no
hand-rolled snake-math script. Pipe stdout through `tee` before grepping, so the full board
survives to disk for the next step, then filter the same stream for the turn signal:

```
sleeper-agent draft board --draft-id <id> --draft-slot <n> --num-teams <n> --notify-my-turn \
  2>&1 | tee /path/to/scratch/board_watch.log | grep --line-buffered -E "YOUR TURN|Traceback|Error"
```

Wrap that whole pipeline directly in `Monitor` (`persistent: true`). No `--once`, no separate
Bash task. Stdout must be a file, not a tty — `cmd_draft_board` auto-selects the plain
`watch_board` loop (1s poll, re-renders only when picks change) instead of the TUI. `--notify-my-
turn` adds a `YOUR TURN: pick N (round R)` line the moment the next unmade pick is ours,
alongside the normal NEED/SURPLUS/FLEX/tier-tagged board. Grepping *without* the `tee` stage
loses the full board — only the matched line reaches Monitor's event stream, and the next
step's "read the log tail" has nothing to read (found the hard way in
[[2026-08-27-draft-mock-draft-4-slot8]], worked around that run with repeated `--once` calls).

## During the draft

`YOUR TURN` notification: read the tail of the tee'd log file — it's already fresh (the plain
watcher re-renders the whole board on every change, so the last render in the file is current).
Don't re-invoke the CLI. Take the top-ranked `NEED`-tagged row; if none are `NEED`, take the top
row overall. State the pick and one line of reasoning, then stop.

**QB cap on the top-overall fallback:** before taking a top-overall QB once the starter QB slot
is filled, check the roster line for how many QBs are already rostered. Two is enough (starter +
one buy-low/handcuff bench bet) — a bigboard-curated rank can legitimately put an injury-recovery
QB (e.g. a healthy-again Burrow or Daniel Jones) above a same-tier skill player on raw rank, but
that comparison stops mattering once a 3rd QB is on the table, since a single-QB league has near-
zero marginal use for a 3rd string arm regardless of its rank. At that point skip every QB row
and take the next-highest non-QB row as the real top-overall pick instead. Confirmed live in
[[2026-08-29-draft-mock-draft-6-slot8]] — the fallback recommended a 3rd QB (Daniel Jones) purely
on bigboard rank; user override: "3 QBs should never happen in a draft," took a rookie WR instead.

**Same cap for any position on the top-overall fallback, TE included:** the QB logic above isn't
QB-specific — once a position has a starter, one realistic bench/FLEX backup, and further depth
stops being usable (a single-QB, single-flex-heavy league has near-zero marginal use for a 3rd
QB or, just as much, a 6th TE), skip that position's rows in the top-overall fallback the same
way. Confirmed live in [[2026-08-29-draft-mock-draft-7-slot8]]: with 5 TEs already rostered
(McBride/Kelce/Goedert/Johnson/Henry), Dalton Schultz was next in board order — skipped in favor
of RB/WR bench depth instead. No hard numeric cap defined yet (2 for QB, informally ~3-4 for
TE/RB/WR depending on FLEX capacity) — use judgment on "would a 6th of these ever start or
matter," same test as the QB rule.

**TE cap, quantified: apply the QB-style guard at TE #3, not TE #5.** Mock #7 above waited until
5 TEs to intervene; a full retro of mock #8
([[2026-08-29-draft-mock-draft-8-slot8]], every pick checked against `data/adp/*.parquet`
external consensus) showed the cost of waiting that long: TE2–TE4 (Goedert, Juwan Johnson,
Schultz) reached an average of **+44 picks ahead of market ADP**, with Johnson alone at **+73**
— the top-overall fallback has no depth discount for a stacked position, so it kept re-surfacing
TE at full raw VORP with zero penalty for the 3rd/4th copy of the same position. Don't wait for
"would a 6th ever start" to feel obviously absurd — check the roster count *before* taking a TE
row in the top-overall fallback, and once TE is already 2-deep (1 starter + 1 bench), skip
further TE rows unless the VORP gap to the next-best non-TE row exceeds ~15. This is a specific
number precisely because "use judgment" let the pattern repeat across three separate mocks (#7,
#8, and whatever prompted #7's own fix) before anyone quantified the actual cost.

**A speculative injury-recovery bet still needs its NEED weighed against unfilled starter slots.**
The primary "take the top NEED row" rule (not just the fallback) can also misfire: a bigboard row
hand-curated high on a healthy-again ceiling story (e.g. Joe Burrow, re-ranked well above his
season vorp of -146.5 per `2026-08-28-bigboard-injury-recovery-games-missed-review`) still reads
as the top NEED row for an empty QB slot even while a real, uncontroversial starter slot (WR) sits
at 0/2. Flagged in [[2026-08-29-draft-mock-draft-7-slot8]] — user: taking a QB there "seems weird"
ahead of WR. No fix landed yet; when the top NEED row is a heavily speculative/injury-recovery bet
with a strongly negative raw vorp, sanity-check it against whether a different still-empty starter
slot has a solid, non-speculative option before locking it in.

**A bigboard row's own "defer to ADP"/"no wiki news on file" annotation is a hard stop against
overriding it live at the table, not a soft suggestion.** When `bigboard`'s pre-draft review pass
explicitly writes that a row should defer to market ADP given the size of the gap (or that no
wiki news exists to justify a bump), that call was already made calmly, off the clock, with the
same information available live — reaching past it at the table needs genuinely new information
that wasn't there during the review pass, not just the pick "feeling right" in the moment. Keenan
Allen (R12, 2026 real draft, -58 vs. ADP) is the case that established this: the board's own
rationale said to defer fully to ADP given the gap, and the reach happened anyway with no new
information to justify it — see
`decisions/2026/2026-08-30-draft-adp-market-comparison-post-draft-review.md`. Before overriding
any row live, read its `rationale` column for this kind of self-flagged deferral first.

**This keeps happening at QB specifically because raw QB VORP is genuinely the least reliable of
the four core positions, not bad luck.** Researched 2026-08-28
([[2026-08-28-bigboard-def-vorp-research-streaming-recommended]],
`wiki/team/draft-strategy.md`): among established starters, QB's year-over-year VORP correlation
is r≈0.40 vs. RB/WR/TE's r≈0.67-0.71 — a QB's raw season total is far more exposed to a single
injury/TD-rate/game-script swing erasing it than a skill position's is. That's why Lamar Jackson,
Joe Burrow, Daniel Jones, Jayden Daniels, and Brock Purdy all needed hand-promotion on this board
already (all five injury-driven): expect the next speculative QB judgment call, don't treat each
one as a one-off surprise.

## Defenses — deliberately unranked, don't go hunting for a better signal

`data/bigboard/<season>.csv` has zero DEF rows, and this is now a researched decision, not a gap:
`stats vorp` does compute real team-DEF VORP (`compute_def_vorp`, real nflverse team stats + the
league's own scoring_settings) but `value bigboard build` explicitly excludes DEF from the ordinal
merge (`bigboard.POSITIONS_EXCLUDED_FROM_ORDINAL_MERGE`) because the underlying signal doesn't
clear the bar for draft-day ranking — see
[[2026-08-28-bigboard-def-vorp-research-streaming-recommended]]. `draft board` will never surface
a defense even though DEF sits at 0/1 NEED. Don't spend draft time searching for a better defense
signal — one was already researched (pressure rate, sack rate, points allowed, raw fantasy
points) and none of it works: DEF's year-over-year correlation tops out around r≈0.30 (pressure
rate, the best of the bunch) vs. a skill position like RB at r≈0.68, and one real consecutive-year
pair (2023→2024) was statistically zero. Use general judgment at the table instead, same as
before. Reasonable timing: once remaining board rows have gone SURPLUS with converging
near-replacement value, or a visible run on defenses starts. Don't wait for the last pick —
autopick or another team can take the one you want.

Before overriding to DEF, check the current top of the board first: DEF is never a ranked
comparison (deliberately, not for lack of data), so a defense-run/convergence signal alone can
still be wrong if a clearly above-replacement skill player (roughly top-10 rank, rookies included
— see [[2026-08-28-draft-mock-draft-5-slot8]]) is still sitting there. DEF is far more streamable
in-season than a rostered skill player — confirmed with real numbers, not just intuition: a
defense's own trailing-4-week form predicts its next game barely at all (r≈0.09), while the
upcoming opponent's own offensive strength predicts it more than 3x better (r≈0.32). Take the
skill player and defer DEF one round rather than reach for it reflexively once a run starts.

**Future idea, not built:** since the real lever is matchup, not season-long quality, a weekly
DEF-streaming recommender (rank available defenses by upcoming opponent offensive weakness) would
be a more honest tool than trying to rank DEF pre-draft — a distinct feature from anything the
`bigboard`/`draft board` pipeline does today.

## Lessons from the 2026 real draft (live corrections, see [[2026-08-29-draft-real-draft-2026-retro]])

- **The top-NEED-row rule has no live market-ADP check.** It happily recommends filling an empty
  starter slot dozens of picks ahead of where the position actually goes (confirmed twice: a QB
  reach ~55 picks ahead of ADP, caught only by manually cross-checking
  `data/adp/<date>.parquet`). Before locking in a NEED-tagged pick for a position with real market
  timing data (QB especially, given its own volatility), spot-check the top row's ADP against the
  current pick number — a NEED tag alone isn't sufficient justification if ADP says it's still 30+
  picks away.
- **NEED/SURPLUS doesn't distinguish "empty slot" from "full but zero bench depth."** A position
  at exactly hard_min (e.g. WR 2/2) reads identically to one deeply stocked (RB 5/2) even though
  the former has no injury/bye cushion at all. When comparing a genuine NEED row against a
  SURPLUS row from a position sitting exactly at its hard_min with no spare, weigh the latter's
  thinness explicitly — it's a real gap the tag doesn't surface.
- **Zero drafted defenses is a legitimate outcome, not just "defer the pick."** Given this
  league's rules (no requirement to have a full roster before Week 1) and DEF's own
  streaming-favors-matchup research (see below), it's fine to never draft a DEF at all and fill
  the slot for free off waivers before kickoff — don't default to "grab one somewhere in the last
  few rounds" just because the slot is required long-term.

## After the draft

Stop the watcher. Log the real draft with `decisions new --kind draft ...`. Fold any new tool
gaps or strategy lessons into this file or `wiki/team/draft-strategy.md`.
