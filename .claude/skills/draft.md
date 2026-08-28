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

## Defenses — no data, don't go hunting for it

`data/bigboard/<season>.csv` has zero DEF rows. `draft board` will never surface a defense even
though DEF sits at 0/1 NEED. Don't spend draft time searching for defense data or projections —
there isn't any in this pipeline. Use general judgment instead: recent real-season defensive
performance (pressure rate, takeaways) is enough. Reasonable timing: once remaining board rows
have gone SURPLUS with converging near-replacement value, or a visible run on defenses starts.
Don't wait for the last pick — autopick or another team can take the one you want.

Before overriding to DEF, check the current top of the board first: DEF is never a ranked
comparison (zero data means it can't be), so a defense-run/convergence signal alone can still
be wrong if a clearly above-replacement skill player (roughly top-10 rank, rookies included —
see [[2026-08-28-draft-mock-draft-5-slot8]]) is still sitting there. DEF is far more streamable
in-season than a rostered skill player; take the skill player and defer DEF one round rather than
reach for it reflexively once a run starts.

## After the draft

Stop the watcher. Log the real draft with `decisions new --kind draft ...`. Fold any new tool
gaps or strategy lessons into this file or `wiki/team/draft-strategy.md`.
