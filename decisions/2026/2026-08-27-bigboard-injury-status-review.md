---
date: '2026-08-27'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Christian McCaffrey
  - Ashton Jeanty
  - Zach Charbonnet
  - Jordyn Tyson
  - Jayden Higgins
  - Ricky Pearsall
  - Josh Jacobs
  - Breece Hall
  - Tyler Warren
  - DeVonta Smith
  - Emeka Egbuka
  - DK Metcalf
  - Alec Pierce
  - George Kittle
  - Puka Nacua
  - Quinshon Judkins
  - Chris Olave
related_wiki:
  - team/roster-philosophy.md
---

## Summary

Todo item: "bigboard evals ... do not (i think?) take into account injury statuses and other news
about a player ... make sure this is taken into account and that the bigboard has notes for those
players that were moved out of their vorp slot for a some reason." Confirmed the premise —
`merge_bigboard`/`bigboard build` never reads `injury_status` at all, it only inserts new VORP
rows, flags VORP changes, and places rookies; injury/news judgment was never part of the mechanical
half, and no bigboard skill judgment pass had incorporated it either (per the outstanding item
noted in `decisions/2026/2026-08-27-bigboard-season-type-postseason-fix.md`'s Outcome). This entry
is that pass, scoped to the realistic draft range (12-team, 15-round league = 180 picks; reviewed
down through roughly rank 220, since nothing below replacement in a ~200-pick range changes
draft-day behavior regardless of injury flag).

## Reasoning

**Scoping the review.** Joined `data/sleeper/players.parquet`'s live `injury_status` onto
`data/bigboard/2025.csv`: 125 of 616 rows carry a non-null status, but the field is noisy —
"Questionable" alone covers 425 players leaguewide, including plainly-irrelevant deep bench players,
so a non-null tag alone isn't a reordering signal by itself. For every flagged row at or above
roughly rank 220, read the existing `wiki/players/*.md` `## News` section where present, and ran a
fresh targeted web search where `last_researched` was null or the existing entry looked resolved
one way or the other, to get a materiality read a bare "Questionable" tag can't provide by itself.

**Moved (real, current, material signal):**

- **Christian McCaffrey (#1 → #4).** Unresolved calf/soft-tissue "tightness" since 2026-08-10, still
  not fully practicing as of 2026-08-20 (wiki page, `last_researched: 2026-08-22`). Explicitly
  echoes the 2024 pattern where a downplayed camp calf issue became a lost season (out until Wk10).
  Moved behind Bijan Robinson/Jahmyr Gibbs/Jonathan Taylor — a modest slide within the RB1 tier, not
  a wholesale re-rank; raw VORP rewards his healthy-peak production, not this durability risk.
- **Ashton Jeanty (#17 → #26).** Fresh right ankle sprain suffered 2026-08-25 — two days before this
  review. ESPN's read is a low- (not high-) ankle sprain and "not considered major," but explicitly
  flags a real chance he sits Week 1, with a worse (high-ankle) read able to linger into the season.
  Moved behind the rest of the RB1/2 cluster (Jacobs, Barkley, Swift, Gainwell/Dowdle/Warren) given
  the diagnosis isn't finalized and the injury is only 2 days old — re-check before Saturday if any
  update lands.
- **Zach Charbonnet (#48 → #98).** Still on PUP as of late-Aug camp reports, recovering from a
  Jan-2026-playoffs torn ACL. A player still on PUP at the 53-man cutdown must sit a minimum 4 games
  — real risk of missing a meaningful chunk of the season behind Kenneth Walker III. Moved into the
  bench-committee-RB band.
- **Jordyn Tyson (#96 → #175, rookie row).** Hamstring injury from an August joint practice expected
  to cost roughly two months — likely opens the season on IR. Too large a games-missed hit for a
  rookie WR's speculative-upside slot to survive unchanged. Unlike the other five moves, this row
  already carried its original `2026-08-24-bigboard-initial-build-rookie-placement` rationale — the
  injury note was appended to it, not substituted in, so the original round/tier reasoning for the
  rookie insertion survives alongside the new injury context.
- **Jayden Higgins (#149 → #297) and Ricky Pearsall (#219 → #298).** Both placed on season-ending IR
  (Higgins: torn ACL, 2026-08-21; Pearsall: PCL surgery, 2026-08-01, re-aggravated in camp). Both out
  for all of 2026 — no realistic draft-day value this season in a non-dynasty keeper league (max 2
  keepers/yr, unchanged 2026 rules). Moved down into the season-ending-IR cluster alongside similarly
  situated players (Julian Hill, Jack Stoll, etc.) rather than left at their stale VORP slot.

**Reviewed, no change** (real injury signal exists but resolved/minor enough that the existing VORP
slot still holds — recorded here so a future pass doesn't re-litigate these from scratch):

- **Josh Jacobs (#19).** Groin issue resolved, trending toward full practice and Week 1 as of
  2026-08-18. Separately carries an open NFL Personal Conduct Policy investigation with unclear
  suspension risk — not an injury, not acted on here, but worth a specific check in the next news
  sweep since it could matter more than the groin ever did.
- **Breece Hall (#30), Tyler Warren (#51), DeVonta Smith (#66), Emeka Egbuka (#73), DK Metcalf
  (#79), Alec Pierce (#82).** All camp-minor injuries (groin/hamstring/toe/undisclosed/ankle) with
  explicit "no Week 1 concern" framing and, in most cases, already back to full practice as of
  2026-08-22 through 2026-08-27. No rank change warranted.
- **George Kittle (#80).** Positive trajectory — activated off PUP and back in pads 2026-08-26,
  "accelerated" Achilles-recovery timeline, real chance at Week 1. Resolves the open item flagged in
  `todo.md` ("Kittle PUP/practice clearance"); no downward move needed, and no upward bump made
  either (still not full team drills as of the review date, so premature to reward it yet).
- **Puka Nacua (#5).** Psoas/lower-back soreness, day-to-day as of 2026-08-25/26, framed by the Rams
  as not serious and managed cautiously. More ambiguous than McCaffrey's case (no comparable history
  cited, "ready to go" framing) — left unmoved rather than over-correcting on camp-soreness noise, but
  worth a status check before Saturday.

**Flagged, not acted on — genuinely unresolved, hand off to the Aug 27-28 full news sweep already on
`todo.md`:**

- **Quinshon Judkins.** Todd Monken (Browns HC) calls the current issue "nagging... nothing big" as
  of ~2026-08-25, consistent with `todo.md`'s existing "nagging knee" framing. However, search also
  surfaced headlines referencing a season-ending leg injury "vs. Bills" / "in loss to Patriots" —
  games that haven't happened yet relative to this review's 2026-08-27 date. Those are very likely
  real articles from later in the actual 2026 season that a live web search can surface regardless of
  the in-story "today," not information available as of the draft. Not used here since acting on
  results that reference future, unplayed games would be looking past the fold rather than evaluating
  current camp status — but flagged explicitly so the next sweep double-checks with date-scoped
  sourcing rather than assuming the "nagging" framing is still current.
- **Chris Olave.** Similarly ambiguous: the specific 2026-08-2x medical-tent exit was resolved as
  "wind knocked out, no structural issue" per the Saints' own staff, matching `todo.md`'s "post-
  medical-tent" framing. But search also surfaced an apparently-unrelated headline about a concussion
  IR stint, again undated relative to this review and plausibly from later in the season. Not acted
  on for the same reason as Judkins above.
- **Dont'e Thornton Jr.** (`todo.md`'s "Thornton return") — not reached in this pass; still open for
  the full sweep.

## Data

| Player | Rank before | Rank after | Status | Why |
|---|---|---|---|---|
| Christian McCaffrey | 1 | 4 | Questionable | Recurring calf tightness, unresolved 10+ days |
| Ashton Jeanty | 17 | 26 | Questionable | Fresh ankle sprain, 2 days old, Week 1 in doubt |
| Zach Charbonnet | 48 | 98 | PUP | ACL recovery, still on PUP, min. 4-game absence if still on PUP at cutdown |
| Jordyn Tyson | 96 | 175 | Doubtful | ~2-month hamstring, likely opens on IR |
| Jayden Higgins | 149 | 297 | IR | Season-ending torn ACL |
| Ricky Pearsall | 219 | 298 | IR | Season-ending PCL surgery |

`value bigboard build --season 2025` re-run after these edits: 616 rows, 0 added, 0 flagged.
`load_bigboard` (strict loader) confirms ranks strictly ordinal 1..616 with no unresolved markers.

## Outcome

6 rows moved out of pure VORP order with `[INJURY REVIEW 2026-08-27: ...]` rationale explaining the
move; `log_ref` set to this entry's slug on each. 12 additional rows reviewed and deliberately left
in place (documented above, not written into the CSV itself since nothing moved — matches this
repo's existing convention of narrative-only "reconsidered, kept" records for rows without a build-
generated review marker). 2 cases (Judkins, Olave) explicitly left unresolved pending the full Aug
27-28 news sweep rather than acted on from ambiguous/likely-future-dated search results — same for
Thornton, not reached at all.

Not done here: a full injury/news sweep of every non-null `injury_status` row below rank ~220 —
deliberately out of scope since a 180-pick draft can't reach those players regardless of health, so
reordering them wouldn't change any actual draft-day decision.
