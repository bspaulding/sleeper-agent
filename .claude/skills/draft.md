---
name: draft
description: Sit in on a live draft (real or mock) on the user's behalf — watch picks land, detect when it's our turn, and make the pick judgment call fast under the clock. Use whenever asked to run/watch/join a draft live, as distinct from `bigboard` (pre-draft ranking) or `keepers` (pre-deadline, untimed).
---

# draft

An agent can't attach to `draft board`'s default Textual TUI — it's interactive and blocking.
Use two long-running background processes instead of a human watching the screen.

## Prerequisites

- The season's big board is built (`bigboard` skill) — `draft board` requires
  `data/bigboard/<season>.csv`.
- Know the draft's identity and our seat:
  - Mock draft: `--draft-id <id> --draft-slot <n> --num-teams <n>` (no league behind a mock, so
    `--num-teams` isn't auto-discoverable — pull `settings.teams` from `GET /v1/draft/<id>` if
    unstated).
  - Real draft: `--league-id <id> --me` (or `--roster-id <n>`).

## 1. Board watcher — the recommendation feed

```
sleeper-agent draft board --draft-id <id> --draft-slot <n> --num-teams <n> \
  > /path/to/scratch/board_watch.log 2>&1
```

Run via Bash `run_in_background: true`. No `--once`. Stdout must be a file, not a tty —
`cmd_draft_board` checks `sys.stdout.isatty()` and auto-selects the plain `watch_board` loop
(5s poll, re-renders only when picks change) instead of the TUI when it isn't one. Every render
already carries NEED/SURPLUS/FLEX and tier tags against our current roster.

## 2. Turn-alert watcher — the timing signal

The board watcher's plain-text render has no "your turn" banner — that logic lives only in the
TUI's app class. Poll `GET https://api.sleeper.app/v1/draft/<id>/picks` directly (cheap, no
bigboard load, no CLI startup) and compute the next unmade pick's owning slot with snake math:

```
round = (pick_no - 1) // num_teams + 1
pos_in_round = pick_no - (round - 1) * num_teams
slot = pos_in_round if round is odd else num_teams - pos_in_round + 1
```

Emit one line per new pick, and one `OUR TURN: pick N (round R)` line the first time the next
unmade pick's slot matches ours — dedupe on pick number. Wrap this in `Monitor` so its stdout
lines arrive as notifications.

## During the draft

- Plain `PICK ...` notification: context only, no action.
- `OUR TURN` notification: read the tail of the board watcher's log file. Don't re-invoke the
  CLI — that's a full process start plus a Sleeper API refetch while a pick clock is running.
  Take the top-ranked `NEED`-tagged row; if none are `NEED`, take the top row overall. State the
  pick and one line of reasoning, then stop.

## DEF gap

`data/bigboard/<season>.csv` has zero DEF rows. Team defenses aren't in the bigboard build, so
`draft board` never recommends one even while DEF sits at 0/1 NEED. Pick a defense by outside
judgment when it's still open and remaining board value has flattened out, or a run on DEF
starts. Tracked in `todo.md`.

## After the draft

Stop both watchers. Log the real draft with `decisions new --kind draft ...`. Fold any new
tool gaps or strategy lessons into this file or `wiki/team/draft-strategy.md`.
