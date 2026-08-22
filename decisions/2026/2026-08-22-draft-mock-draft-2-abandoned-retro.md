---
date: '2026-08-22'
kind: draft
season: '2026'
week: null
status: recommended
players_involved:
  - Kyren Williams
  - Travis Etienne
  - Drake Maye
  - Rhamondre Stevenson
related_wiki:
  - team/roster-philosophy.md
---

## Summary

Second 2026 rehearsal mock draft (Sleeper mock `1396989748353974272`, 12 teams, slot 8,
`--value-season 2025`), **abandoned mid-draft by the user** after repeated bad recommendations
and slow turnaround. Root-caused and fixed in-session rather than just logged; this entry is the
retro plus the fix record.

## Reasoning — what went wrong

**1. `draft board`'s roster-need tracking was silently broken for every mock draft, not just
stale.** After round 5 (Kyren Williams, Travis Etienne, Drake Maye, Rhamondre Stevenson drafted —
3 RBs total), the board still reported `RB 0/2` and tagged every remaining RB `[NEED]`. This led
directly to a bad recommendation (Kenny Gainwell, RB) when RB was actually already `SURPLUS`. The
user caught it ("are you sure we need another rb?") — the tool should have caught it first.

Root cause: Sleeper's picks endpoint returns `roster_id: null` on every pick in a mock draft
(confirmed directly against the API — no real league roster exists behind a mock). `--draft-slot`
correctly resolves `my_roster_id` to a real integer via the draft's `slot_to_roster_id` map, but
`my_roster_positions` (`draft_tools/board.py`) matched ownership by comparing
`pick.roster_id != my_roster_id` — `None != 8` is always `True`, so **zero of the caller's own
picks were ever counted**, for the entire life of the `--draft-id`/`--draft-slot` mock-draft
codepath. This is a strictly worse version of the exact gap `.claude/skills/draft.md` already
flagged after the *first* 2026 mock (missing `--me` ⇒ no roster annotation at all) — this time
`--draft-slot` *was* passed, correctly, and the annotation was still wrong, just wrong silently
instead of absent.

Fix: `pick.draft_slot` is populated on every pick in both mock and league drafts (unlike
`roster_id`), so `my_roster_positions` now takes an optional `my_draft_slot` and matches on it
whenever the caller resolved ownership via `--draft-slot`, falling back to `roster_id` only for
the `--me`/`--roster-id` league path. `DraftPick.roster_id`'s type was also corrected to
`int | None` — it was silently `None` in mock drafts even before this bug, the annotation just
lied about it. Verified against the live mock draft's real state post-fix: `RB 5/2 [SURPLUS]`,
correctly reflecting all 5 RBs actually drafted.

**2. The `--watch` background monitor never fired a single notification across ~5+ picks.**
`watch_board` re-renders only when the picked-player set changes (by design, per
`.claude/skills/draft.md`), using plain `print()`. When stdout isn't a tty — exactly the case
when a process is run under a background monitor/pipe rather than an interactive terminal —
Python fully block-buffers stdout (~8KB) instead of line-buffering it, so renders sat unflushed
instead of reaching the monitor. The process was internally working correctly (confirmed via
direct `draft board` fetches showing real state) but produced zero observable output while
running, making the whole point of `--watch` — hands-off live notification — silently inert.
Every pick had to be manually prompted by the user instead.

Fix: `watch_board`'s default `render` callable now flushes explicitly (`print(s, flush=True)`)
instead of relying on Python's buffering heuristics.

**3. Compounding factor, not a bug:** even before catching root cause #1, [[feedback-draft-board-refresh]]
(loop-refresh a `draft board` call until the top result changes, before ever reporting a
recommendation) was already established from the *first* mock draft's retro and was not
consistently followed here — several recommendations were made off a single fetch rather than a
confirmed-fresh one, and the user had to catch a stale recommendation (D'Andre Swift, already
gone) before it was tightened up mid-session. That memory has been strengthened to make single-
fetch-during-live-play explicitly insufficient.

## Data

- Mock draft ID `1396989748353974272`, 12 teams, slot 8, best ball.
- Root cause confirmed directly against `https://api.sleeper.app/v1/draft/<id>/picks`
  (`roster_id: null` on every pick) and `https://api.sleeper.app/v1/draft/<id>`
  (`slot_to_roster_id["8"] = 8`, a real int) — the mismatch that broke matching.
- Fix commits: `board.py::my_roster_positions` (draft_slot-based matching + flush-on-render),
  `models/sleeper.py::DraftPick.roster_id` (`int` → `int | None`), `commands/draft_cmd.py`
  (thread `my_draft_slot` through both the `--watch` and single-fetch codepaths), plus a
  regression test (`test_my_roster_positions_matches_by_draft_slot_when_roster_id_is_null`).
  Full test suite (300 tests) + ruff pass after the fix.

## Outcome

Draft abandoned unfinished by the user — not completed, no final roster to record. The value of
this session was catching and fixing two real, previously-invisible bugs (roster tracking always
zero in mock drafts; `--watch` never actually notifying) before the real 2026 draft (Sat Aug 29),
rather than discovering either live. Recommend one more mock draft rehearsal before the real
draft specifically to confirm both fixes hold up under live play — this session's "second mock"
never got a clean run.
