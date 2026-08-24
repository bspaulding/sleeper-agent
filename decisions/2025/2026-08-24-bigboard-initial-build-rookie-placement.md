---
date: '2026-08-24'
kind: bigboard
season: '2025'
week: null
status: recommended
players_involved:
  - '13287'  # Jeremiyah Love (RB) rank 42
  - '13286'  # Jadarian Price (RB) rank 47
  - '13279'  # Carnell Tate (WR) rank 74
  - '13294'  # Makai Lemon (WR) rank 83
  - '13330'  # Kenyon Sadiq (TE) rank 88
  - '13417'  # De'Zhaun Stribling (WR) rank 91
  - '13281'  # Jordyn Tyson (WR) rank 96
  - '13298'  # KC Concepcion (WR) rank 103
  - '13346'  # Denzel Boston (WR) rank 110
  - '13276'  # Omar Cooper (WR) rank 119
  - '13414'  # Kaelon Black (RB) rank 148
  - '13274'  # Germie Bernard (WR) rank 152
  - '13269'  # Fernando Mendoza (QB) rank 172
  - '13275'  # Ty Simpson (QB) rank 183
related_wiki:
  - wiki/team/rookie-evaluation.md
  - wiki/team/roster-philosophy.md
---

## Summary

First-ever `bigboard` skill run. `value bigboard build --season 2025` (after fixing a real bug —
see Data) mechanically merged 616 VORP-ranked veterans with 14 rookies triaged from the 2026 NFL
draft class, flagging all 14 `[NEEDS REVIEW: new rookie placement]`. This entry records placing
all 14 into the ordinal ranking via real research (current consensus rookie fantasy rankings,
landing-spot/opportunity reporting), not the mechanical percentile heuristic's rough starting
slots. Re-running `bigboard build` afterward reports 0 flagged rows, and `load_bigboard` accepts
the file (ranks 1..616, contiguous, no duplicates) — ready for the real draft (Sat Aug 29).

## Reasoning

Followed `.claude/skills/bigboard.md`'s process: no prior `--kind bigboard` entries existed to
check for continuity (first run), so went straight to placement using
`wiki/team/rookie-evaluation.md`'s draft-capital-hit-rate framework as the baseline prior, then
overrode individual placements against real situational reporting (landing spot, backfield/WR-room
competition, injury recency, per-position secondary signals) where it was available and
specific — exactly the "weight landing spot over pure draft capital" instruction in that wiki
page's best-ball framing section, not a deviation from it.

Researched via web search (2026 rookie fantasy consensus rankings, training-camp status pieces)
rather than guessing. Key findings that shaped placement, beyond the mechanical round number:

- **Jadarian Price** (R1 RB, Seattle) landed in what's arguably the single best pure
  opportunity-share situation in the class — Kenneth Walker III departed, Zach Charbonnet
  recovering from an ACL tear — so he's placed near round-1 peer Jeremiyah Love despite being the
  literal last pick of round 1, on situational grounds per the RB secondary-signal framework
  (opportunity share, backfield competition).
- **De'Zhaun Stribling** (R2 WR) is a real, direct example of the "situational upside beats raw
  draft capital" override: consensus rookie fantasy rankings place him #5 overall, ahead of four
  round-1 WRs (Tyson, Concepcion, Boston, Cooper) in this same batch — placed accordingly, ahead
  of those round-1 picks, not left at a generic round-2 discount.
- **Kenyon Sadiq** (R1 TE) gets the single strongest positional-hit-rate signal in the whole
  framework (round-1 TE: 81.8% top-24, 54.5% top-12) plus a specific "positioned for immediate
  impact" report — placed just below the TE12 landmark (Brock Bowers, rank 80).
- **Fernando Mendoza / Ty Simpson** (both R1 QB) got deliberately modest placements despite
  round-1 capital's own strong QB hit-rate (84%) — this league's single-QB/no-superflex format
  explicitly deprioritizes rookie QB investment per the wiki page's own framing, and neither
  research pass surfaced a situational reason to override that. Mendoza (the only rookie QB in
  either search's top-20) still placed ahead of Simpson (absent from both).
- **Germie Bernard** (R2 WR, Stribling's own teammate in SF) got the opposite treatment from
  Stribling: no standout situational report surfaced despite the shared landing spot, so he stayed
  at a generic round-2 discount rather than being elevated.

Full per-player rationale (with the specific landmark each placement was calibrated against —
2025-live-VORP position-rank thresholds computed directly from this build, e.g. RB24 ≈ rank 44,
WR24 ≈ rank 70, TE12 ≈ rank 80 — not the stale 2024 figures in `roster-philosophy.md`) is recorded
in each row's `rationale` field in `data/bigboard/2025.csv` and won't be duplicated here; that file
is the source of truth going forward, this entry is the reasoning trail behind it.

## Data

**A real bug found and fixed before this build could produce a meaningful board at all:**
`value bigboard build`'s original `--season` argument was silently overloaded for two different
concepts — VORP's value-season (2025, the most recently completed season) and the rookie draft
class to triage (2026, the upcoming draft this board is prepping for). The first build attempt
against `--season 2025` alone triaged **zero** rookies, not because none existed, but because
`data/nfl/draft_picks.parquet` only has season-2026 rows and the code filtered by `season==2025`.
Fixed by adding a `--rookie-season` flag defaulting to `season + 1` (same directional relationship
`cmd_draft_keepers` already uses, inverted) — see commit `5eba936`. Without this fix, the "no
wargame run has ever drafted a rookie" problem this whole feature exists to solve would have
persisted into the real board too, silently.

Sources consulted (rookie fantasy consensus rankings, landing-spot/depth-chart reporting, current
as of this build):
- [RotoBaller: Updated Fantasy Football Rookie Wide Receiver Rankings (2026)](https://www.rotoballer.com/updated-fantasy-football-rookie-wide-receiver-wr-rankings-2026/1899795)
- [SI/OnSI: Best Rookie Wide Receivers in 2026 Fantasy Football](https://www.si.com/onsi/fantasy/rankings/best-rookie-wide-receivers-2026-fantasy-football-kc-concepcion)
- [PFF: Fantasy Football 2026 — Rookie Training Camp Status Checks](https://www.pff.com/news/fantasy-football-2026-rookie-training-camp-status-checks)
- [Yahoo Sports: Fantasy Football Rookie Rankings 2026 — Jeremiyah Love Is the 1.01](https://sports.yahoo.com/articles/fantasy-football-rookie-rankings-2026-120036548.html)
- [RotoBaller: Fantasy Football Rookie RB Outlooks — Love, Price, Coleman (2026)](https://www.rotoballer.com/fantasy-football-rookie-rb-outlooks-jeremiyah-love-jadarian-price-jonah-coleman-2026/1902826)
- [ProFootballNetwork: Fantasy Football Rookie Rankings 2026 — top 20](https://www.profootballnetwork.com/fantasy-football/fantasy-football-rookie-rankings-2026-jeremiyah-love-is-the-1-01-no-quarterback-cracks-the-top-10/)

Position-rank landmarks computed directly from this build's live 2025 VORP (not the stale 2024
figures elsewhere in the wiki): RB12=rank 20/113.1vorp, RB24=rank 44/46.5vorp, RB36=rank
102/-2.8vorp; WR12=rank 42/47.5vorp, WR24=rank 70/22.5vorp, WR36=rank 99/-0.9vorp; TE12=rank
80/13.1vorp, TE24=rank 145/-45.9vorp; QB12=rank 95/0.0vorp.

## Outcome

All 14 flagged rows resolved; `value bigboard build --season 2025 --rookie-season 2026` reports 0
flagged rows on re-run. `load_bigboard` accepts the file cleanly (contiguous ranks 1..616, no
duplicates, no unresolved markers). Board is ready for `draft board`/`draft watch-picks` to
consume for the real draft on 2026-08-29 — no further bigboard work needed before then unless
news/injury/depth-chart signal changes enough to warrant a re-sweep per the skill's own trigger.
