---
last_updated: '2026-08-16'
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

**Which fits this league:** this is a **best-ball** league (`league.settings.best_ball`) with no
in-season waiver-wire management modeled by this codebase (`PROJECT_PLAN.md`'s best-ball note).
That cuts against a pure Zero-RB bet, which leans on being able to actively stream RB
replacements off waivers all season — a lever this team doesn't really pull. A Hero-RB-leaning
approach (one strong early RB, then broaden) is a more natural fit than either extreme, but this
is a starting hypothesis to test against the next mock draft, not a hard rule yet.

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
Note that `draft board`'s per-row NEED/FLEX/SURPLUS tags check each of RB/WR/TE against the
*full* FLEX capacity independently (e.g. "would a 3rd RB still be FLEX-eligible" ignores how many
FLEX spots WR and TE have already claimed) — a deliberate approximation, not true joint
allocation across the shared pool, so don't read three FLEX-tagged rows across different
positions as three additional slots.

## Sources

- [FantasyPros: VORP, VONA, VOLS explained](https://www.fantasypros.com/2025/06/fantasy-football-draft-strategy-vorp-vols-vona/)
- [Athlon: How to Handle Positional Runs](https://athlonsports.com/fantasy/fantasy-football-draft-strategy-navigating-positional-runs)
- [FantasyLife: What is Zero RB?](https://www.fantasylife.com/articles/best-ball/what-is-zero-rb-drafting-tips-from-a-pro)
- [Athlon: Stud RB vs. Zero RB Theories](https://athlonsports.com/fantasy/fantasy-football-strategy-stud-rb-theory-vs-zero-rb-theory)
- [Establish The Run: Optimal Position Allocation for Best Ball](https://establishtherun.com/optimal-position-allocation-for-draftkings-best-ball/)
