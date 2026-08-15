---
last_updated: '2026-08-09'
source: decisions/2026/2026-08-09-draft-mock-draft-1-turn-by-turn.md
---

# Team roster philosophy

Standing strategy notes for our team's drafting, built up from mock/real draft retrospectives.
Checked at the start of every draft per `.claude/skills/draft.md`.

## Standing rules (read this first)

1. **Never take pure best-player-available (highest VORP) blind.** RB carries roughly 2x WR's
   value-over-replacement at every depth down to about rank 24 (see below) — a pure-VORP policy
   will over-draft RB by construction, not by chance. Check positional need against the roster
   grid (below) before taking the board's #1 suggestion.
2. **Draft exactly one DEF, rounds 10–15.** Required starting slot, no bench value in a second
   one, no positional runs on it worth reaching into early for — see §4.
3. **Never spend a pick on a kicker.** No K slot exists in this league.
4. **During a live draft, keep responses to a refresh+recommendation, nothing else.** If something
   looks wrong (stale board, missing player), say so in one line and keep going — investigate
   after the draft, not mid-pick. See §1.
5. **Don't fully trust a player being on the `draft board` list as proof they're rosterable.**
   Cross-check `data/sleeper/players.parquet`'s `team` field (not `status`) before or during a real
   draft if it's been more than a couple weeks since `sleeper players sync`. See §3.
6. **Re-run VORP against the most recent completed season before trusting rankings for a real
   draft.** This retro's source draft ran on 2024 VORP because 2025 wasn't published upstream yet
   as of 2026-08-09 — check `data/vorp/` for a fresher file before the real draft on Aug 29 and
   re-sync if one's available by then.

## Roster grid (this league, 2026)

`roster_positions`: `QB, RB, RB, WR, WR, TE, FLEX, FLEX, DEF, BN×6` (15 total). No kicker.
`best_ball: true` — Sleeper auto-optimizes the *weekly starting lineup* from whatever's on the
roster, but it cannot invent a player you didn't draft: if a slot's eligible position isn't on the
roster, that slot scores zero that week. Minimum-viable roster by position: **QB≥1, RB≥2, WR≥2,
TE≥1, DEF≥1**, with the 2 FLEX + 6 bench spots free to lean into whichever of RB/WR/TE actually
carries value that year.

---

## 2026 mock draft #1 retrospective — 2026-08-09

Source: `decisions/2026/2026-08-09-draft-mock-draft-1-turn-by-turn.md`. Mock draft
`1392286240727908352`, slot 8, all 15 rounds, run on `--value-season 2024` (2025 VORP not yet
available upstream — see standing rule 6). Final roster: **2 QB, 8 RB, 2 WR, 3 TE, 0 DEF**
(Barkley, Henry, Lamar Jackson, Colston Loveland, Mike Evans, Joe Mixon, Alvin Kamara, James
Conner, Aaron Jones, Baker Mayfield, Najee Harris, Jonnu Smith, Zach Ertz, Kareem Hunt, Jerry
Jeudy).

### 1. The turn-timeout incident (Rounds 4–5 skipped)

Two full rounds (4 and 5 — Colston Loveland and Mike Evans) happened with **no board refresh or
recommendation exchanged in the session at all**. The chat jumped from a Round 3 recommendation
straight to a refresh that, per the draft's own pick log, actually reflected a point in time after
Round 6. Separately, two consecutive refreshes right around that gap came back byte-for-byte
identical while picks were continuing live, which is what triggered "you need to refresh now i am
running out of time" and then "you were too slow, don't do that again."

I can't prove from the Sleeper API alone whether Rounds 4–5 were server-side autopicks on a clock
or picks made directly in the app without asking me that round — the public picks endpoint doesn't
expose an autopick flag. But the pattern (silence exactly where the "too slow" complaints cluster,
plus a real stale-board incident in the same window) is strong circumstantial evidence for your
read on it. Whichever it was, the fix is the same:

- **During a live/mock draft, a refresh-and-recommend turn should be one tool call and a couple
  sentences — no side investigation.** When I noticed the stale-board oddity mid-draft, I started
  pulling the raw Sleeper API to root-cause it in the moment, which is exactly the kind of
  time-costing detour that shouldn't happen on the clock. That's now recorded as standing behavior
  (a session memory, separate from this repo) — diagnose stale-data weirdness *after* the pick
  clock isn't running, not during.
- Concretely, what got lost: reconstructing the true best-available board at pick 41 and pick 56
  shows **Joe Mixon (142.4 VORP) sat available through both skipped rounds** before finally being
  drafted in Round 6 — a real value cost on top of the roster-construction cost, not just a
  process complaint.

### 2. Why so many RBs, so few WRs — this wasn't random

You're right that the split is skewed (8 RB vs. 2 WR against a grid that only *requires* 2 RB + 2
WR), and I want to be direct about the cause: **every single recommendation across all 13 rounds I
was actually asked about was "take the single highest-VORP player on the board," with no
positional-need weighting at all.** `draft board`'s ranking is explicitly value-only by design
(`.claude/skills/draft.md` even warns "it doesn't model positional scarcity dynamics mid-draft" and
puts weighing positional runs on the list of "draft-day judgment the tool can't automate") — I
didn't apply that judgment live, I just followed the tool's #1 suggestion every time.

That policy isn't neutral across positions — it mechanically favors RB, and the data shows exactly
why. Pulling percentile cuts from `data/vorp/2024.parquet`:

| Position | Top-5 avg VORP | VORP at rank 12 | VORP at rank 24 | VORP at rank 36 |
|---|---|---|---|---|
| RB | 245.3 | 122.0 | 60.4 | -2.4 |
| WR | 142.3 | 60.7 | 25.2 | -3.2 |
| TE | 93.1 | 2.6 | -32.9 | -69.2 |
| QB | 137.9 | 0.0 | -109.5 | -194.0 |

RB carries **roughly 2x WR's value-over-replacement** at both rank 12 and rank 24 — right where
this league's RB2/FLEX and WR2/FLEX decisions actually happen — and only converges with WR around
rank 36, three-plus rounds deeper. This is the classic "running back scarcity" shape (thin
top-end talent, steep drop-off) versus WR's comparatively deep, generous replacement level. A
pure best-player-available policy will greedily keep clearing the RB shelf specifically *because*
its VORP numbers stay inflated longer, not because RBs are objectively "better players" — it's an
artifact of how replacement level differs by position, and it's a known, expected failure mode of
BPA-only drafting, not a one-off fluke of this mock.

**Fix for the next mock/the real draft:** apply an explicit positional-need check on top of
`draft board`'s ranking, not instead of it — e.g., don't take a 3rd+ RB over a top-of-board WR
once both starting WR slots are unfilled, the way standing rule 1 above now states. TE looks
over-drafted here too (3, when 1 is required) for the same underlying reason — TE's curve is even
flatter/worse than WR's below the top few, so once a mid-tier TE clears the bar it can out-VORP a
mediocre WR even though roster need says otherwise.

### 3. Drafted players not currently on an NFL team

Cross-checking the final 15-man roster against `data/sleeper/players.parquet` (synced
2026-07-26) turned up something worth fixing structurally, not just chalking up to old data: **5
of 15 picks — Joe Mixon, Najee Harris, Jonnu Smith, Zach Ertz, Kareem Hunt — show an empty `team`
field**, and this was cross-verified against the live draft's own pick `metadata.team` (also
empty for all five), so it's not a sync artifact. Sleeper's `status` field said `"Active"` for all
five, which is misleading — `status` tracks something closer to "not retired/PUP," while `team`
is the actual "currently rostered by an NFL club" signal, and `draft board` never reads it at all.

This is a real gap, and it's broader than the 2024-vs-2025 data-season caveat: even with fresh
2025 VORP, `draft board` would still happily recommend a player with no current team, because
nothing in its pipeline joins VORP against live roster/team status. Worth a follow-up: have
`draft board` (or at minimum `value rank`) filter or flag `team == None` players by cross-joining
`data/sleeper/players.parquet`, rather than relying on VORP data alone.

### 4. Should we draft a DEF? Should we draft a "whole ready-to-go team"?

**Draft exactly one DEF — it's not optional.** `roster_positions` has a single hard `DEF` starting
slot, and `best_ball: true` only auto-optimizes lineups from what's actually on the roster; it
can't fill a DEF slot with a skill player. We finished this mock with zero, which means that
starting slot would score zero every week for the whole season — a bigger practical miss than the
RB/WR skew, honestly, because there's no bench-depth argument that makes it okay. DEF has no
meaningful positional runs to worry about (streamable/replaceable in-season on waivers in most
leagues, and nothing in this project's design suggests otherwise), so it doesn't need to be an
early pick — anywhere from round 10 to the very last round is fine, it just cannot be *zero*.

On "whole ready-to-go team": no, not in the sense of needing every bench slot to be a specific,
locked-in starter by the final pick — `best_ball: true` exists precisely so you don't have to
pre-plan a week-by-week lineup. But "ready to go" in the sense of *every starting-slot position
being coverable* is not optional, and that's really the same finding as the RB/WR skew and the
missing DEF: the roster needs to satisfy `QB≥1, RB≥2, WR≥2, TE≥1, DEF≥1` at minimum before spending
remaining picks on best-available depth. This mock roster satisfies QB, RB, and TE with room to
spare, exactly meets WR with zero cushion, and fails DEF outright — that's the concrete shape of
"not ready to go" here, now captured as standing rule 1–2 above for the next draft.
