---
name: wargame
description: Run a full-dress rehearsal of a live snake draft against the local mock Sleeper server, with separate Sleeper/LLM-Drafter/Human roles, before trusting the draft skill on draft day. Use ahead of the real draft, or any time draft.md's live-draft heuristics change and need re-validation.
---

# wargame

Rehearses the live-draft flow end to end without touching the real Sleeper API: a mock server
plays Sleeper, one session plays the LLM Drafter (decides picks), and a separate session/human
plays the Human (the only role allowed to actually submit a pick). Splitting Drafter and Human
into separate sessions is the point — it reproduces the real constraint that the Drafter cannot
click Sleeper's UI itself, so the exercise actually tests the handoff, not just the recommendation
logic. See `cli/src/sleeper_agent/wargame/` (state machine), `cli/scripts/wargame_server.py`
(server), and `cli/scripts/wargame_publish_rec.py` (Drafter's publish tool) for the implementation;
`decisions/2026/2026-08-23-mock-draft-wargame-slot8.md` is a full retro of a run that voided, and
is the best source of *what goes wrong* if this runbook is skipped.

## Roles

- **Sleeper** — `wargame_server.py`, a real local HTTP server. Serves league/draft/picks like the
  real API, auto-picks for bot personas on a ticker thread, and enforces a 60s human pick clock
  after a configurable cold-start grace period. State is in-memory, rebuilt from
  `wargame_seed.json` on process start — there is no live-reset endpoint.
- **LLM Drafter** — a session running this repo's `draft.md` live-draft flow, pointed at the mock
  server via `SLEEPER_AGENT_BASE_URL`. On its turn it decides a pick the normal way (`draft
  watch-picks`/`draft board`) and hands it off by running `wargame_publish_rec.py` — it never
  calls the picks endpoint itself, matching the real project's read-only Sleeper client.
- **Human** — a separate session (or an actual human) also pointed at the mock server. Reads only
  `/tmp/wargame/current_rec.json`, cross-checks it against the live on-clock pick, and is the only
  role that ever issues the `POST .../picks` call.

## One-time / per-season setup

Do this once per season, not once per run — it doesn't depend on wargame state:

- VORP must exist for whatever `--value-season` you'll pass the Drafter (normally the most
  recently *completed* real season — the mock draft's nominal "2026" label has no stats behind it
  yet). If `draft watch-picks`/`draft board` prints `no VORP data for season <Y> — run stats vorp
  --season <Y> first`, run `sleeper-agent stats sync --season <Y>` then `sleeper-agent stats vorp
  --season <Y>`. Skipping this was the root cause of run #14's failure (see the retro) — the board
  render died, which took the Drafter's live view and every monitor/alarm path down with it.

## Per-run setup

1. Kill anything left over from a previous run: the mock server process, and any watcher/monitor
   process the Drafter or Human spawned. A stray leftover watcher was the direct cause of run #14's
   confusion (a correct rec landed in the audit log from a process nobody knew was still running).
2. `rm -rf /tmp/wargame` — clears `current_rec.json` and `recs.jsonl` from the last run. A stale
   `current_rec.json` left over from a voided run is a hazard for the next one.
3. Export `SLEEPER_AGENT_BASE_URL=http://127.0.0.1:8321/v1` (or whatever host/port you start the
   server on) in **every** shell that will run the `sleeper-agent` CLI this session, Drafter and
   Human alike — it's read once at process start (`cli/src/sleeper_agent/sleeper_client/http.py`),
   so set it before launching, not after.

## Running it

**Start Sleeper:**

```
cd cli && uv run python scripts/wargame_server.py \
    --seed scripts/wargame_seed.json --port 8321 --grace-seconds 90
```

The grace period counts down from *process start*, not from `/start` — don't leave a long gap
between starting the server and starting the Drafter, or the human pick clock may already be
close to armed before the draft even begins. It prints keeper/available counts and confirms
`humans wait at roster_id=5` on boot — the seed's human seat is draft slot 8 / roster_id 5, already
holding the real 2026 keepers (Diggs R7, Darnold R14) so the fixture matches the actual league.

**Start the Human session** (this can be the same session that started the server):

- Confirm `pre_draft`: `curl http://127.0.0.1:8321/v1/league/wargame-league-2026`.
- Once the Drafter session reports ready, start the draft:
  `curl -X POST http://127.0.0.1:8321/v1/draft/wargame-draft-2026/start`.
- Track it live: `sleeper-agent draft watch-picks --draft-id wargame-draft-2026 --value-season <Y>
  --draft-slot 8 --poll-seconds 1`. This is the same command used for a real mock draft — draft
  geometry comes from the draft object's own `settings`, and turn detection already handles keeper
  rows correctly via gap logic. Don't recompute "next pick" from `len(picks)` or the last printed
  row instead of trusting this — the seed always has keeper picks interleaved at rounds 7 and 14
  specifically to make a naive row-count wrong.
- On each Human turn, act on `/tmp/wargame/current_rec.json` **only** — `recs.jsonl` is an audit
  trail, not a valid input, even if it looks correct. Before submitting, check the rec's
  `on_clock_pick_no` against `watch-picks`'s current on-the-clock pick; refuse (make no pick) on
  any mismatch or on a missing/stale file rather than guessing.
- Submit: `curl -X POST http://127.0.0.1:8321/v1/draft/wargame-draft-2026/picks -H
  "Content-Type: application/json" -d '{"roster_id": 5, "player_id": "<id>"}'`. A `409` returns a
  rich payload explaining why (not your turn / player already taken) — read `detail`, don't retry
  blindly. A `410` means the draft already voided; stop and go to the retro.

**Start the LLM Drafter session** (separate context from the Human — it should not see the Human's
terminal/tool calls, or the exercise stops testing the handoff):

- Same `SLEEPER_AGENT_BASE_URL`, run the normal `draft.md` live-draft flow against
  `--draft-id wargame-draft-2026 --value-season <Y> --draft-slot 8`.
- If the board render ever fails (e.g. missing VORP), that is a hard stop, not something to
  route around — do not fall back to reasoning about pick numbers from keeper fixtures or prior
  context. A hallucinated pick number is indistinguishable, from a well-formed rec, from a correct
  one, and the Human has no way to catch it (this is exactly how run #14 voided: a plausible,
  fully-formed rec for the wrong pick).
- Publish every decision through the mechanical tool, never by hand-writing the file:
  `uv run --project cli python scripts/wargame_publish_rec.py --pick <n> --player <id> --name
  "<name>" --position <pos> --rationale "<why>"`. It atomically writes `current_rec.json` and
  appends to `recs.jsonl` in one call — no separate bookkeeping step to forget.
- Never call the picks endpoint directly. If the Drafter role finds itself constructing a `POST
  .../picks` call, that's a contract violation — the pick clock is a Human-only surface here, same
  as production.

## Ending a run and cleanup

- Terminal states: all `total_picks` filled, or the server logs `HARD FAIL ... voided_pick_clock`
  and the league status flips to `voided_pick_clock`. Either way, stop and file a decision-log
  entry — `decisions/2026/2026-08-23-mock-draft-wargame-slot8.md` is the bar to match (timeline
  table, pick-by-pick table, failure attribution, a "cheapest fixes before the next run" list).
  A voided run is exactly as worth logging as a completed one; some of the most useful entries so
  far are failures.
- Before the next run: kill the server and every watcher/monitor process, `rm -rf /tmp/wargame`
  again, and restart the server fresh from the seed (per-run setup above). There is no in-process
  reset — reusing a running server between runs will replay the previous run's picks.

## Known sharp edges

- `wargame_server.py`'s bot auto-pick loop (`DraftState._run_bots`) has no guard against the
  player board running out before `total_picks` is reached — it would spin forever holding the
  server lock. The shipped `wargame_seed.json` has enough players that this can't happen (252
  players vs. 180 total picks); if you edit the seed to add rounds/teams or shrink the board,
  keep that margin.
- `HUMAN_ROSTER_ID = 5` is hardcoded in `wargame_server.py` and only works because the seed leaves
  exactly roster 5 without a bot persona. If you edit `personas`/`slot_to_roster_id` in the seed,
  keep that invariant or the ticker will silently stall with no error.
