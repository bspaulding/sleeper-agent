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

```
sleeper-agent draft board --draft-id <id> --draft-slot <n> --num-teams <n> --notify-my-turn \
  > /path/to/scratch/board_watch.log 2>&1
```

Run via Bash `run_in_background: true`. No `--once`. Stdout must be a file, not a tty —
`cmd_draft_board` auto-selects the plain `watch_board` loop (5s poll, re-renders only when picks
change) instead of the TUI. `--notify-my-turn` adds a `YOUR TURN: pick N (round R)` line the
moment the next unmade pick is ours, alongside the normal NEED/SURPLUS/FLEX/tier-tagged board.

Wrap this same command in `Monitor`, filtering for `YOUR TURN`. One process, one Monitor — no
separate picks poller, no hand-rolled snake-math script.

## During the draft

`YOUR TURN` notification: read the tail of the watcher's log file — it's already fresh. Don't
re-invoke the CLI. Take the top-ranked `NEED`-tagged row; if none are `NEED`, take the top row
overall. State the pick and one line of reasoning, then stop.

## Defenses — no data, don't go hunting for it

`data/bigboard/<season>.csv` has zero DEF rows. `draft board` will never surface a defense even
though DEF sits at 0/1 NEED. Don't spend draft time searching for defense data or projections —
there isn't any in this pipeline. Use general judgment instead: recent real-season defensive
performance (pressure rate, takeaways) is enough. Reasonable timing: once remaining board rows
have gone SURPLUS with converging near-replacement value, or a visible run on defenses starts.
Don't wait for the last pick — autopick or another team can take the one you want.

## After the draft

Stop the watcher. Log the real draft with `decisions new --kind draft ...`. Fold any new tool
gaps or strategy lessons into this file or `wiki/team/draft-strategy.md`.
