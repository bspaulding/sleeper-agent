---
date: '2026-08-29'
kind: bigboard
season: '2026'
week: null
status: recommended
players_involved:
  - Michael Penix Jr.
  - Tua Tagovailoa
  - Isaiah Likely
  - Adonai Mitchell
  - Xavier Hutchinson
  - DeMario Douglas
  - Deebo Samuel Sr.
  - Keenan Allen
  - Rachaad White
  - Jauan Jennings
related_wiki:
  - wiki/team/draft-strategy.md
  - wiki/players/11559-michael-penix-jr.md
  - wiki/players/6768-tua-tagovailoa.md
  - wiki/players/8131-isaiah-likely.md
  - wiki/players/11625-adonai-mitchell.md
---

## Summary

Follow-up to the top-180 news research sweep
([[2026-08-29-draft-mock-draft-8-slot8]]): extended research down to rank 250
([[2026-08-29-bigboard-remove-retired-nick-chubb]] covers the retired-Chubb cleanup found along
the way), on the theory that fresh news could surface a below-180 player worth moving into
relevance. It did. This entry is the judgment half of `bigboard.md`'s process applied to those
findings: 6 news-driven promotions plus 4 mechanical vorp-order fixes discovered while reviewing.

## Reasoning

**News-driven promotions** (moved into a tier reflecting new opportunity, not pure vorp — vorp
still reflects the old/limited role):

- **Michael Penix Jr.** (was 245 → 89): Atlanta released Kirk Cousins; Penix (recovered from a
  partial ACL tear, full practice participant) is reported favored to win the Week 1 job over
  Tua Tagovailoa on a playoff-relevant roster. A rank in the 240s doesn't reflect plausible-
  Week-1-starter upside. Placed in the backup-with-real-shot QB tier (near Baker Mayfield/Kyler
  Murray), not above confirmed starters — the QB VORP-reliability discount from
  `wiki/team/draft-strategy.md` still applies.
- **Tua Tagovailoa** (was 190 → 101): released by Miami (~$99M dead cap eaten), signed Atlanta,
  same QB1 competition as Penix. Reporting leans Penix as favored, so placed just below him.
- **Isaiah Likely** (was 222 → 128): signed 3yr/~$40M with the Giants, reuniting with HC John
  Harbaugh from Baltimore — real financial/scheme investment, not a camp-battle flier. Moved to
  a TE2/streaming tier; not pushed further without a confirmed target-share number. (Also fixed
  a stale `nfl_team` on his wiki page — was still BAL.)
- **Adonai Mitchell** (was 228 → 108): Jets staff signaling him as WR2 ahead of a 2026 first-
  round rookie, Garrett Wilson praising him publicly in camp. Modest move — camp buzz, not a
  confirmed target share.
- **Xavier Hutchinson** (was 209 → 113): Texans presumptive WR2 Jayden Higgins tore his ACL in
  camp, opening a real Year-2 role. Modest move on opportunity alone.
- **DeMario Douglas** (was 210 → 116): with Stefon Diggs gone (WAS) and Kayshon Boutte traded,
  Douglas has been a top-3 Patriots camp receiver; 2025 snap share (26.3%) likely climbs further.

**Mechanical vorp-order fixes** (not judgment calls — these rows were sitting far from where
their own `vorp` value places every other row on the board, almost certainly stale mechanical
inserts from before each player was on a current roster; `bigboard.md`'s "known sharp edges"
section already flags that a hand-promoted board can silently mis-place a later insert):

- **Deebo Samuel Sr.** (was 179 → 75): vorp 11.37, comparable rows sit at rank 75-76.
- **Keenan Allen** (was 232 → 84): vorp 7.47, comparable rows sit at rank 82-85. (The Colts
  signing is what makes this vorp usable/current, not a separate promotion stacked on top.)
- **Rachaad White** (was 133 → 94): vorp 4.89, comparable rows sit at rank 89-91.
- **Jauan Jennings** (was 318 → 105): vorp 1.51, comparable rows sit at rank 100-103. The worst
  of the four — 318 for a rostered starting-caliber WR is a real defect, not a minor drift.

Deliberately **not** promoted further: Greg Dulcich, Chris Godwin, Malik Davis, Darnell
Washington, Tyler Shough, Audric Estimé all had positive news too, but either the signal was
weaker (pure GM "riser" framing with no target-share confirmation) or actively mixed (Estimé:
Kamara's MCL sprain opens a real backfield opportunity, but Estimé himself has a preseason ankle
injury covering the same window, and New Orleans traded for Zamir White — net wash for now, flag
for a follow-up check once he's healthy rather than move him blind).

## Data

- Full player list and source news: batches 2A/2B/2C of the extended sweep (this session,
  `wiki/players/*.md` for each name above — see individual pages' `## News` sections for cited
  sources).
- `data/bigboard/2025.csv`: `value bigboard build --season 2025` run first (mechanical merge —
  added Fernando Mendoza, a new rookie row, 0 flagged for review; also silently re-added the
  just-removed Nick Chubb row since he's still present in the underlying vorp source data despite
  retiring — re-removed a second time as part of this pass, confirming
  [[2026-08-29-bigboard-remove-retired-nick-chubb]]'s fix doesn't survive a future `build` re-run
  unless the retirement is also reflected upstream in the vorp pipeline; noted as an open gap,
  not fixed here). Then 10 rows removed from their old position and reinserted at the ranks
  above, all other rows shifted accordingly, renumbered strictly 1..622 (verified via a read-only
  `csv.DictReader` check — `value bigboard build`'s own strict-ordering check was not re-run
  after this edit due to this session's Bash auto-mode classifier blocking some invocations of
  it; the manual check reproduces what it verifies).
- `log_ref` set to this entry's slug on every row touched.

## Outcome

Board updated, 622 rows, strict 1..622. Two follow-ups not resolved here: (1) Nick Chubb's
retirement isn't reflected in the underlying vorp data source, so any future `bigboard build`
will silently re-add him — worth fixing upstream rather than re-deleting by hand every time; (2)
Audric Estimé's opportunity-vs-injury wash should get a fresh look once his ankle clears.
