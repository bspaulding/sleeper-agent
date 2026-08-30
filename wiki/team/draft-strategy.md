---
last_updated: '2026-08-30'
source: docs/superpowers/specs/2026-08-16-draft-strategy-research-and-positional-need.md
---

# Drafting strategy — general reference

Standing reference on fantasy-football drafting theory, distinct from
`wiki/team/roster-philosophy.md` (which holds this team's own retrospectives and standing
rules). Written up from research done while fixing the first 2026 mock draft's 8 RB/2 WR/0 DEF
result — see `roster-philosophy.md` for that specific incident.

## Value-based drafting (VBD) baselines

VBD assigns every player a value by comparing their projected points to a baseline
"replacement" player at the same position. The baseline you pick changes what the number means:

- **VORP** (value over replacement player) — baseline is a readily available waiver-wire
  player. This is what `stats vorp`/`draft board` compute today.
- **VOLS** (value over last starter) — baseline is the worst player who'll actually start
  *somewhere* in the league, given every team's roster requirements. Bakes roster-slot scarcity
  into the number itself, unlike VORP.
- **VONA** (value over next available) — baseline is the best player likely still available at
  your *next* pick. Accounts for draft position and pick-to-pick gaps, but can't be computed
  before the draft since it depends on what actually happens.

**Why this matters here:** a pure-VORP board (what `draft board` produces) doesn't know about
roster slots at all — it will keep recommending the highest-VORP player regardless of position,
which is exactly what produced the 8 RB result. VOLS-style thinking is "does this position still
have a player at all left to fill a starting slot" — a different question than "what's the
single highest-value player." `draft board`'s new roster-need annotation (added alongside this
page) is a lightweight way to get VOLS-style information without recomputing VBD baselines from
scratch: it shows starter-slot counts directly, next to the existing VORP ranking.

## RB strategy spectrum: Zero-RB, Hero-RB, Robust-RB

These are named points on a spectrum of how early/heavily to draft running backs, driven by two
facts about the position: RB has the steepest value drop-off of any position (confirmed in this
league's own VORP data — see `roster-philosophy.md`), and RB carries the highest in-season
injury/role-loss risk of the skill positions.

- **Robust-RB** — draft RB heavily in the first 3-4 rounds (e.g. 3 RBs in the first 4 picks),
  betting on locking in the scarcest, highest-value position before it's gone. Historically
  strong when true 3-down "bell-cow" backs were common; weaker as more offenses split RB touches
  by committee.
- **Zero-RB** — deliberately punt RB in the first several rounds, load up on WR/QB/TE value
  instead, and address RB later once the position's depth (and price) has normalized. Bets on RB
  being volatile enough that early RB draft capital is a bad risk-adjusted price, and that
  useful RB production can still be found later or via the waiver wire in-season.
- **Hero-RB** — a middle path: take exactly one true RB1 early (accepting the position's
  scarcity premium for a top player), then pivot to WR/QB/TE depth, treating the rest of the RB
  room as bench lottery tickets rather than a second early investment.

**Which fits this league:** this league has `best_ball: true` (`league.settings.best_ball`), but
that only means Sleeper auto-optimizes the weekly starting lineup — it does **not** mean waivers
are unavailable. **Corrected 2026-08-28:** an earlier version of this note claimed "no in-season
waiver-wire management modeled by this codebase" and used that to argue against Zero-RB. That's
wrong — `PROJECT_PLAN.md` explicitly describes this as "a regular league (waivers, trades,
keepers, in-season transactions all enabled)," this league runs active FAAB waivers
(`waiver_type: 2`, budget 100/season), and this codebase has working tooling for exactly this
(`waiver recommend`, `freeagent recommend`, `.claude/skills/waivers.md`,
`.claude/skills/free-agents.md`). Streaming RB replacements off waivers is a real, available
lever here.

The actual, data-grounded case against a pure Zero-RB bet in this league is different: per
`decisions/2026/2026-08-27-bigboard-season-type-postseason-fix.md`, RB's replacement level in
this league's VORP data is structurally worse than WR's in points-per-game terms (~8.4 ppg vs.
~10.5 ppg) — meaning a *streamed* waiver-wire RB is more likely to land at true replacement level
(or below) than a streamed WR would, since RB touches concentrate more heavily with rostered
starters across a 12-team league, leaving thinner scraps on the wire. That's a real scarcity
argument for leaning Hero-RB over Zero-RB, grounded in this league's actual VORP baselines — not
because streaming is impossible, but because what's left to stream at RB specifically tends to be
worse. A Hero-RB-leaning approach (one strong early RB, then broaden) is still a reasonable
starting hypothesis on that basis, but it should be tested against the next mock draft for the
right reason, not the wrong one.

## Named failure mode: committee backfield taken at bell-cow pricing

A recurring, specific way RB picks go wrong here: drafting/pricing a running back as if he holds
a clean bell-cow role when beat reporters are already live-reporting a real committee at the time
of the pick. This isn't the general "RB is volatile" point above — it's a concrete, checkable
signal (current depth-chart/committee reporting for that specific player, already sitting in
`wiki/players/`) that keeps not getting checked against the pending pick in the moment.

Confirmed twice, a full season apart:

- **Mock-draft-1 (2026-08-09), the original "8 RB" retro** (`roster-philosophy.md`) — a pure-VORP
  policy loaded up on RBs without checking any of them for role clarity.
- **2026 real draft** (R3 D'Andre Swift, CHI; R4 Jaylen Warren, PIT — see
  `decisions/2026/2026-08-30-draft-adp-market-comparison-post-draft-review.md`) — both picks
  walked into backfields where beat reporters were already reporting a real committee (Monangai in
  CHI; Dowdle in PIT under a new HC running an explicit competition) at the time of the pick, and
  the market (ADP) had already priced that in while our own board hadn't. Not disastrous
  individually, but a repeat of the same shape, still not priced in live even with the signal
  sitting in `wiki/players/` before the pick.

**How to apply this:** before locking in an RB pick (live or during a `bigboard` review pass),
check that player's current `wiki/players/<player>.md` entry specifically for committee/timeshare
language, not just injury/depth-chart status generally — a "committee" signal should discount the
pick toward the committee-mate's share of value, not the bell-cow price the raw VORP number
implies.

## Tiered drafting and positional runs

The mainstream answer to "should I reach for a position" isn't raw position count, it's
**tiers** — clusters of players separated by real value gaps. If the last player in a tier is
still on the board and the next tier down is a real drop-off, that's a legitimate reason to
deviate from strict best-player-available; if a "run" on a position starts but there's no real
tier cliff yet, chasing it is usually a mistake (jumping in reactively rather than reading the
board).

`draft board`'s new per-row `tier=N` tag (computed independently per position, a ≥20% VORP drop
counts as a new tier — see the CLI implementation) is a direct, mechanical version of this idea:
a jump in a position's tier number between two rows is the signal to weigh a reach against,
regardless of how many players of that position are already gone.

## Best-ball positional allocation

Large-pool best-ball guidance (e.g. from sites covering DraftKings-scale multi-entry contests)
suggests rough ranges like 2-3 QB, 5-7 RB, 6-9 WR, 2-4 TE per roster. **This doesn't translate
directly to this league** — that guidance is tuned for huge best-ball player pools with
different roster sizes and lineup-scoring rules. This league's actual grid is
`QB,RB,RB,WR,WR,TE,FLEX,FLEX,DEF,BN×6` (15 total, `roster-philosophy.md`'s roster grid section),
which implies a much tighter allocation: `QB≥1, RB≥2, WR≥2, TE≥1, DEF≥1` as an absolute floor,
with the 2 FLEX + 6 bench spots as the only real room for leaning into whichever position is
paying off that draft. The 8 RB mock-draft-1 result used up nearly all of that flexible room on
one position, at the direct cost of a completely unfillable DEF slot and zero WR bench cushion.
`draft board`'s per-row tag now reflects this properly (fixed 2026-08-27, after a second mock
draft reproduced the same RB overrun): NEED/SURPLUS reflects only a position's own hard_min, and
`FLEX` is a second, independent tag appended only when the *shared* pool across RB/WR/TE
(`board.remaining_flex_capacity`) still has room — e.g. `RB (SURPLUS), FLEX` means your starting
RB slots are full but this pick would still occupy a real, currently-open FLEX slot. Once another
position (or enough of the same one) claims those FLEX slots, everything still over its own
hard_min shows plain `SURPLUS` with no FLEX suffix — so three rows tagged `FLEX` really do share
one pool, not three independent ones.

## QB raw VORP is the least reliable of the four core positions

Researched 2026-08-28 alongside the DEF ranking work
([[2026-08-28-bigboard-def-vorp-research-streaming-recommended]]): pooled year-over-year
`vorp_season` correlation (2018-2025, this league's own `compute_vorp`/`scoring_settings`) looks
similar-and-high across all four core positions at first glance — QB r=+0.696, RB r=+0.681, WR
r=+0.739, TE r=+0.731 — but that QB number is inflated by roster mechanics, not real
predictability: a league only carries 1-2 real QBs per team, so a backup who plays 0 games two
years running contributes an easy, meaningless "both near the floor" data point. Restricting to
players with **≥8 games played in both years** (i.e., comparing actual established starters to
themselves) tells a different story:

| Position | r, full population | r, ≥8 games both years |
|---|---|---|
| QB | +0.696 | **+0.399** |
| RB | +0.681 | +0.667 |
| WR | +0.739 | +0.713 |
| TE | +0.731 | +0.679 |

RB/WR/TE barely move when filtered to real starters — their high full-population correlation
reflects genuine year-to-year stickiness in performance, not just usage. QB's collapses by nearly
half. Among established starters, **QB is the most volatile of the four core positions year over
year**, not the most stable, despite what the raw number suggests.

**Why this is plausible, not just noise:** a QB's fantasy output leans heavily on TD rate and
game script (both of which regress hard year to year) and is uniquely exposed to a single
injury/backup-QB game erasing a whole season's raw total (see Joe Burrow's -146.5 vorp_season
distortion in
[[2026-08-28-bigboard-injury-recovery-games-missed-review]]) — whereas a workhorse RB's role/
opportunity or a true WR1/TE1's target share tends to persist more directly into next year's
usage, independent of scoring variance.

**How to apply this:** during the `bigboard` skill's review pass, weight a QB row's raw
`vorp_season` less than an RB/WR/TE row's at the same distance from a tier line — situational
context (offensive-line/scheme continuity, injury-recovery ceiling, a rushing floor that survives
bad passing luck) should move a QB row further from its raw-VORP slot than the same context would
move a skill-position row. This isn't a new rule so much as a name for what the review pass has
already been doing in practice: QB is by far the most hand-overridden position on the current
board — Lamar Jackson, Joe Burrow, Daniel Jones, Jayden Daniels, and Brock Purdy all carry manual
injury-recovery rationale (plus Justin Fields via a role-change review), five of six overrides
driven by a single injury distorting a season's raw total — which this number now explains
rather than just observes.

## Sources

- [FantasyPros: VORP, VONA, VOLS explained](https://www.fantasypros.com/2025/06/fantasy-football-draft-strategy-vorp-vols-vona/)
- [Athlon: How to Handle Positional Runs](https://athlonsports.com/fantasy/fantasy-football-draft-strategy-navigating-positional-runs)
- [FantasyLife: What is Zero RB?](https://www.fantasylife.com/articles/best-ball/what-is-zero-rb-drafting-tips-from-a-pro)
- [Athlon: Stud RB vs. Zero RB Theories](https://athlonsports.com/fantasy/fantasy-football-strategy-stud-rb-theory-vs-zero-rb-theory)
- [Establish The Run: Optimal Position Allocation for Best Ball](https://establishtherun.com/optimal-position-allocation-for-draftkings-best-ball/)
