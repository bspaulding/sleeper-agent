# `draft watch-picks` design

## Background

Live/mock draft sessions currently track picks via an ad hoc bash script (poll Sleeper's picks
endpoint, compute snake order, detect when the next pick is mine, fetch a fresh `draft board`)
written from scratch each time and run under the `Monitor` tool. This was flagged as a follow-up
during the 2026-08-22 mock draft #3
(`decisions/2026/2026-08-22-draft-mock-draft-3-slot8.md`, `todo.md`'s "Live-draft pick tracker
should be a tested CLI command" entry): the snake-order math and turn-detection logic should live
in tested project code, not be re-derived untested every draft.

## Goal

A new `sleeper-agent draft watch-picks` subcommand that:

- Streams one line per new pick as it happens (not a full board reprint per pick, unlike
  `draft board --watch`).
- The instant the next pick belongs to the user, fetches and prints the full best-available board
  (same rendering as `draft board`'s non-watch path) — folded into the same detection event, no
  separate round-trip.
- Is still meant to run under the `Monitor` tool for live notifications; this command owns the
  polling/logic, `Monitor` just surfaces stdout as chat notifications, unchanged from today's
  usage pattern.

## Non-goals

- Does not touch `draft board --watch`'s existing full-reprint-on-any-change behavior — that
  command/flag is untouched, this is an additive sibling command.
- Does not mirror to a decisions-log file (`draft-live.md`) — this command's job is fast live
  notifications, not a durable record; the post-draft retro (`.claude/skills/draft.md` step 4)
  already covers that from the final board state.
- Does not support linear or auction draft types' turn-detection — snake is this league's actual
  format and every mock run so far. Non-snake drafts still get per-pick lines, just never trigger
  the "next pick is mine" board auto-fetch.
- Does not auto-submit picks — this project's Sleeper client is read-only and Sleeper has no
  public pick-submission endpoint either; the human still clicks the pick in Sleeper's UI.

## Architecture

Three additions, all within the existing `draft_tools`/`commands` layout — no new modules.

### 1. `slot_for_pick(pick_no: int, num_teams: int) -> int` (new, `draft_tools/board.py`)

Pure function computing which draft slot owns a given overall pick number, for a standard snake
draft (no 3rd-round-reversal):

```
round = (pick_no - 1) // num_teams + 1
pos_in_round = pick_no - (round - 1) * num_teams
slot = pos_in_round if round is odd else (num_teams - pos_in_round + 1)
```

### 2. `watch_picks(...)` (new, `draft_tools/board.py`)

Orchestration function, same dependency-injection shape as the existing `watch_board` (so it's
testable the same way: `fetch_picks`, `sleep`, `render` all injectable; `max_iterations` caps the
loop for tests).

Signature (illustrative — finalize during implementation):

```python
def watch_picks(
    draft_id: str,
    *,
    num_teams: int,
    draft_type: str,
    my_roster_id: int | None,
    my_draft_slot: int | None,
    total_picks: int,
    board_context: BoardRenderContext,  # everything needed to render the board on my turn
    base_url: str = SLEEPER_BASE_URL,
    poll_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
    render: Callable[[str], None] = _flush_print,
    fetch_picks: Callable[..., list[DraftPick]] = fetch_draft_picks,
) -> None:
```

Per iteration:

1. Fetch all picks.
2. For every pick not yet seen (by `pick_no`, in order), print:
   `Pick {pick_no} (slot {draft_slot}): {name} ({position}, {team})`, appending ` <== MY PICK`
   when the pick belongs to me. Matching convention mirrors `my_roster_positions`: compare
   `draft_slot` when `my_draft_slot` is set, else `roster_id`.
3. Compute `next_pick_no = len(picks) + 1`. If `draft_type == "snake"` and my slot/roster is
   known and `slot_for_pick(next_pick_no, num_teams)` is mine, and this `next_pick_no` hasn't
   already been announced: render the full board and print it, then remember `next_pick_no` as
   announced so it isn't reprinted on subsequent polls before the pick actually lands. The
   board-render callable takes the *already-fetched* `picks` list from this same iteration as its
   argument (no second fetch) and closes over the rest of `board_context` (vorp_df, requirement,
   rookie watch, team changes) — same inputs `cmd_draft_board`'s non-watch path already uses.
4. Stop when `len(picks) >= total_picks` (draft complete) or `max_iterations` reached.

### 3. `cmd_draft_watch_picks` (new, `commands/draft_cmd.py`) + shared setup refactor

New subparser `draft watch-picks` with the same option surface as `draft board`:
`--league-id`/`--draft-id` (mutually exclusive, required), `--rounds` (default 15),
`--value-season`, `--num-teams` (default 12), `--me`/`--roster-id`/`--draft-slot`, plus
`--poll-seconds` (default `1.0`).

**Refactor:** `cmd_draft_board`'s setup block — resolving `draft_id`/`value_season`/`num_teams`
from league-or-draft-id, resolving `my_roster_id`/`my_draft_slot`, loading `vorp_df` +
rookie-watch + team-changes — is extracted into a helper (e.g. `_resolve_draft_context(args, root,
base_url) -> DraftContext`) that both `cmd_draft_board` and `cmd_draft_watch_picks` call. Avoids
duplicating that resolution logic a second time.

`cmd_draft_watch_picks` uses the resolved context to build the "render board on my turn" callable
(same `board_view` + `render_board` call the non-watch `draft board` path already makes) and
passes it into `watch_picks` along with `draft.draft_type`, `num_teams`, and
`args.rounds * num_teams` as `total_picks`.

## Error handling

- Same missing-VORP-data error as `draft board` (`no VORP data for season ... — run stats vorp
  ...`), via the shared `_resolve_draft_context` helper.
- Same invalid-`--draft-slot` error as `draft board` (slot not in `slot_to_roster_id`).
- Non-snake `draft_type`: no error — per-pick lines still stream, board auto-fetch is simply
  never triggered. (No board-render path exists for "my turn" without slot-order math, so this is
  the natural degradation, not a special case to code around.)

## Testing

- **`slot_for_pick`**: direct unit tests — round boundaries (last pick of a round vs. first pick
  of the next), first slot / last slot, at least two `num_teams` values (12, and an odd count like
  10) to catch off-by-one errors in the ascending/descending switch.
- **`watch_picks`**: same fake-injection pattern as existing `watch_board` tests (`fake_fetch`
  returning canned pick lists per call, `sleeps.append`, `rendered_calls.append`,
  `max_iterations`):
  - One line per new pick, in `pick_no` order, on each call that returns new picks.
  - ` <== MY PICK` marker appears correctly for both `draft_slot`-based and `roster_id`-based
    matching.
  - The board renders (via the injected board-render callable) exactly once when the next pick
    becomes mine, and is not re-rendered on a subsequent poll where the pick still hasn't landed.
  - Non-snake `draft_type` streams pick lines but never invokes the board-render callable.
  - Loop stops at `max_iterations`, and also stops once `len(picks) >= total_picks`.
- **`cmd_draft_watch_picks` / `_resolve_draft_context`**: thin CLI-level tests mirroring
  `cmd_draft_board`'s existing tests for both the mock-draft (`--draft-id`/`--draft-slot`) and
  league (`--league-id`/`--me`) sources, confirming the resolved context matches what
  `cmd_draft_board` would have produced.
