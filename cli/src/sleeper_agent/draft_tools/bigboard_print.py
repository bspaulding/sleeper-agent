"""Printable, paginated HTML backup of the pre-draft big board.

An analog fallback for draft day in case anything goes wrong technically —
see decisions/2026/2026-08-28-bigboard-injury-recovery-games-missed-review.md
for the origin story and the headless-Chrome page-geometry validation this
module's constants are pinned to. Originally a one-off ad hoc script
(scratchpad/gen_bigboard_print.py, never committed); rebuilt here as a
repeatable command after the 2026-08-29 VORP-shrinkage pass made the old
static reports/bigboard-print-2026.html stale.
"""

from __future__ import annotations

import datetime
import html as html_lib
import math
import re
from dataclasses import dataclass
from pathlib import Path

from sleeper_agent.config import data_dir, wiki_dir
from sleeper_agent.draft_tools.bigboard import BigboardRow, load_bigboard
from sleeper_agent.draft_tools.keepers import DEFAULT_NUM_TEAMS, DEFAULT_TOTAL_ROUNDS
from sleeper_agent.sleeper_client.sync import ROSTERS_SCHEMA_VERSION, USERS_SCHEMA_VERSION
from sleeper_agent.storage.parquet_store import read_table

# --- Page geometry (CSS reference px, 96px = 1in, matches how browsers size
# @page). Validated against an actual headless-Chrome print render during
# the original 2026-08-28 backup (5 physical pages, no overflow/clipping) —
# change only alongside the matching CSS below, and re-verify with a real
# print render, not just this script's own row-count math.
PX_PER_IN = 96
PAGE_W_IN, PAGE_H_IN = 8.5, 11
MARGIN_IN = 0.4
PAGE_W_PX = PAGE_W_IN * PX_PER_IN
PAGE_H_PX = PAGE_H_IN * PX_PER_IN
MARGIN_PX = MARGIN_IN * PX_PER_IN
USABLE_H_PX = PAGE_H_PX - 2 * MARGIN_PX
USABLE_W_PX = PAGE_W_PX - 2 * MARGIN_PX
CONTENT_W_IN = PAGE_W_IN - 2 * MARGIN_IN
CONTENT_H_IN = PAGE_H_IN - 2 * MARGIN_IN
COL_GAP_PX = 16
COL_W_PX = (USABLE_W_PX - COL_GAP_PX) / 2

# Row metrics, must match the CSS template below exactly.
ROW_FONT_PX = 9
ROW_LINE_HEIGHT = 1.3
ROW_PAD_V_PX = 2  # 1px top + 1px bottom
ROW_BORDER_PX = 1
ROW_HEIGHT_PX = math.ceil(ROW_FONT_PX * ROW_LINE_HEIGHT) + ROW_PAD_V_PX + ROW_BORDER_PX

SAFETY_BUFFER_PX = 24  # slack per page for font-metric rounding error
H1_BLOCK_PX = 26  # 18px font, ~1.2 line-height, + 4px margin
NOTE_FONT_PX = 11

# Judgment call carried over unchanged from the original 2026-08-28 backup:
# 163 open picks (see _pick_counts) covers everyone likely to actually get
# drafted, and this buffer adds slack for reaches/handcuffs so the printed
# list still reads as "the board", not just "the plausible picks". Override
# via generate_bigboard_print(cutoff=...) rather than tuning this for a
# one-off season.
DEFAULT_CUTOFF_BUFFER = 87

# bigboard.py's shrinkage-resort re-sort leaves this exact bracket marker on
# every mechanically-resorted row (hundreds, whenever the shrinkage
# methodology changes) — see
# decisions/2026/2026-08-29-bigboard-vorp-shrinkage-review-pass.md. Starring
# every one of those rows in the printout would bury the handful that carry
# a real judgment call under noise, so it's stripped before deciding whether
# a row is appendix-worthy.
_MECHANICAL_ONLY_MARKER_RE = re.compile(r"\[VORP RECALIBRATED[^\]]*\]")


def _appendix_worthy(rationale: str) -> str:
    """The rationale text worth a footnote, or "" if all this row carries is
    mechanical bookkeeping."""
    return _MECHANICAL_ONLY_MARKER_RE.sub("", rationale).strip()


@dataclass(frozen=True)
class ConfirmedKeeper:
    team_label: str
    flag: str | None


def _parse_confirmed_keepers_section(text: str) -> dict[int, tuple[list[str], bool]]:
    """Parses the "## Confirmed real keepers" table in a
    wiki/league/projected-keepers-<season>.md page (see e.g.
    decisions/2026/2026-08-28-real-keepers-confirmed-via-graphql.md for where
    that table comes from) into roster_id -> (kept player names, ineligible
    flag). Returns {} if the page has no such section — keepers are just
    left unmarked in that case, not an error.
    """
    marker = "## Confirmed real keepers"
    start = text.find(marker)
    if start == -1:
        return {}
    section = text[start:]
    end = section.find("\n## ", 1)
    if end != -1:
        section = section[:end]

    # The Roster cell is sometimes annotated (e.g. "5 (us)" for our own
    # roster) — match the leading number and ignore the rest of that cell.
    row_re = re.compile(r"^\|\s*(\d+)\b[^|]*\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")
    result: dict[int, tuple[list[str], bool]] = {}
    for line in section.splitlines():
        m = row_re.match(line.strip())
        if not m:
            continue
        roster_id = int(m.group(1))
        kept_cell = m.group(2).strip()
        notes_cell = m.group(4).strip()
        if kept_cell.lower() in ("*(none)*", "(none)", "—", "-", ""):
            continue
        names = [
            re.sub(r"\s*\(only\)\s*$", "", part.strip())
            for part in kept_cell.split(",")
            if part.strip()
        ]
        if names:
            result[roster_id] = (names, "ineligible" in notes_cell.lower())
    return result


def _load_confirmed_keepers(root: Path, draft_season: str) -> dict[str, ConfirmedKeeper]:
    """Player name -> ConfirmedKeeper, for the printout's struck-through KEPT
    rows. Best-effort: returns {} (no strikethroughs, not an error) when the
    keepers wiki page or that season's roster/user data isn't there yet —
    the printout is still useful without keeper annotations.
    """
    wiki_path = wiki_dir(root) / "league" / f"projected-keepers-{draft_season}.md"
    if not wiki_path.exists():
        return {}
    by_roster = _parse_confirmed_keepers_section(wiki_path.read_text(encoding="utf-8"))
    if not by_roster:
        return {}

    sleeper_dir = data_dir(root) / "sleeper"
    rosters_path = sleeper_dir / "rosters" / f"{draft_season}.parquet"
    users_path = sleeper_dir / "users" / f"{draft_season}.parquet"
    if not rosters_path.exists() or not users_path.exists():
        return {}
    rosters = read_table(rosters_path, expected_schema_version=ROSTERS_SCHEMA_VERSION)
    users = read_table(users_path, expected_schema_version=USERS_SCHEMA_VERSION)
    joined = rosters.join(users, left_on="owner_id", right_on="user_id", how="left")
    team_label_by_roster = {
        row["roster_id"]: row["team_name"] or row["display_name"]
        for row in joined.select(["roster_id", "display_name", "team_name"]).to_dicts()
    }

    result: dict[str, ConfirmedKeeper] = {}
    for roster_id, (names, ineligible) in by_roster.items():
        team_label = team_label_by_roster.get(roster_id, f"Roster {roster_id}")
        flag = "ineligible" if ineligible else None
        for name in names:
            result[name] = ConfirmedKeeper(team_label, flag)
    return result


def _pick_counts(num_teams: int, total_rounds: int, num_keepers: int) -> tuple[int, int]:
    total_picks = num_teams * total_rounds
    return total_picks, total_picks - num_keepers


def _note_text(
    *,
    gen_date: str,
    season: str,
    total_rows: int,
    cutoff: int,
    num_teams: int,
    total_rounds: int,
    num_keepers: int,
) -> str:
    total_picks, open_picks = _pick_counts(num_teams, total_rounds, num_keepers)
    return (
        f"Generated {gen_date} from data/bigboard/{season}.csv, in rank order, top {cutoff} "
        f"of {total_rows} ({num_teams} teams x {total_rounds} rounds = {total_picks} picks, "
        f"minus {num_keepers} keepers = {open_picks} open picks, plus buffer). Struck-through "
        "rows are confirmed keepers (already off the draft board, not draftable). Names marked "
        "* have a rationale note in the appendix. Full board is in the CSV if you need to go "
        "deeper."
    )


@dataclass(frozen=True)
class BigboardPrintResult:
    out_path: Path
    total_rows: int
    printed_rows: int
    pages: int
    appendix_rows: int
    unmatched_keepers: list[str]


def generate_bigboard_print(
    root: Path,
    season: str,
    *,
    draft_season: str | None = None,
    cutoff: int | None = None,
    out_path: Path | None = None,
    gen_date: str | None = None,
) -> BigboardPrintResult:
    """Regenerates the printable, paginated HTML big-board backup from
    data/bigboard/<season>.csv. Refuses to run (via `load_bigboard`'s own
    hard stop) if the board still has unresolved review markers — same
    "draft-usable" bar `draft board` enforces, since this printout exists to
    be a faithful stand-in for that board, not a preview of a half-finished
    one.
    """
    draft_season = draft_season or str(int(season) + 1)
    gen_date = gen_date or datetime.date.today().isoformat()
    out_path = out_path or (root / "reports" / f"bigboard-print-{draft_season}.html")

    rows: list[BigboardRow] = sorted(load_bigboard(root, season), key=lambda r: r.rank)
    confirmed_keepers = _load_confirmed_keepers(root, draft_season)

    total_picks, open_picks = _pick_counts(
        DEFAULT_NUM_TEAMS, DEFAULT_TOTAL_ROUNDS, len(confirmed_keepers)
    )
    resolved_cutoff = cutoff if cutoff is not None else open_picks + DEFAULT_CUTOFF_BUFFER

    note_text = _note_text(
        gen_date=gen_date,
        season=season,
        total_rows=len(rows),
        cutoff=resolved_cutoff,
        num_teams=DEFAULT_NUM_TEAMS,
        total_rounds=DEFAULT_TOTAL_ROUNDS,
        num_keepers=len(confirmed_keepers),
    )

    note_chars_per_line = int(USABLE_W_PX / 5.3)  # ~5.3px/char average for 11px Arial
    note_lines = math.ceil(len(note_text) / note_chars_per_line)
    note_block_px = note_lines * (NOTE_FONT_PX * 1.4) + 14  # + margin-bottom
    header_block_px = H1_BLOCK_PX + note_block_px

    rows_per_col_page1 = (
        math.floor((USABLE_H_PX - header_block_px - SAFETY_BUFFER_PX) / ROW_HEIGHT_PX) - 1
    )
    rows_per_col_pagen = math.floor((USABLE_H_PX - SAFETY_BUFFER_PX) / ROW_HEIGHT_PX) - 1
    rows_per_page1 = rows_per_col_page1 * 2
    rows_per_pagen = rows_per_col_pagen * 2

    printed = [row for row in rows if row.rank <= resolved_cutoff]
    matched_keepers: set[str] = set()
    rows_html: list[str] = []
    appendix_html: list[str] = []
    for row in printed:
        vorp_disp = (
            f"{row.vorp:.1f}"
            if row.vorp is not None
            else (f"Rd{row.draft_round}" if row.draft_round else "")
        )
        kept = confirmed_keepers.get(row.name)
        css_class = ' class="kept"' if kept else ""
        name_disp = html_lib.escape(row.name)
        note = _appendix_worthy(row.rationale)
        if note:
            name_disp = f"{name_disp}*"
        if kept:
            matched_keepers.add(row.name)
            kept_note = f"KEPT — {html_lib.escape(kept.team_label)}"
            if kept.flag:
                kept_note += f" ({html_lib.escape(kept.flag)})"
            name_disp = f'{name_disp} <span class="kept-note">{kept_note}</span>'

        rows_html.append(
            f"<tr{css_class}><td>{row.rank}</td><td>{name_disp}</td>"
            f"<td>{row.position}</td><td>{vorp_disp}</td></tr>"
        )
        if note:
            appendix_html.append(
                f"<tr><td>{row.rank}</td><td>{html_lib.escape(row.name)}</td>"
                f"<td>{html_lib.escape(note)}</td></tr>"
            )

    unmatched_keepers = sorted(set(confirmed_keepers) - matched_keepers)

    header_row = "<tr><th>Rk</th><th>Name</th><th>Pos</th><th>VORP</th></tr>"
    pages: list[str] = []
    remaining = rows_html
    is_first = True
    while remaining:
        cap = rows_per_page1 if is_first else rows_per_pagen
        chunk, remaining = remaining[:cap], remaining[cap:]
        left_n = (len(chunk) + 1) // 2
        pages.append((chunk[:left_n], chunk[left_n:], is_first))
        is_first = False

    page_blocks = []
    for i, (left, right, page_is_first) in enumerate(pages, start=1):
        header_html = (
            f'<h1>2026 Big Board</h1>\n<p class="note">{note_text}</p>\n'
            if page_is_first
            else ""
        )
        page_blocks.append(
            f"""<div class="page">
{header_html}<div class="cols">
<table><colgroup><col class="c-rank"><col class="c-name"><col class="c-pos"><col class="c-vorp"></colgroup>
{header_row}
{chr(10).join(left)}
</table>
<table><colgroup><col class="c-rank"><col class="c-name"><col class="c-pos"><col class="c-vorp"></colgroup>
{header_row}
{chr(10).join(right)}
</table>
</div>
<div class="pagenum">Page {i} of {len(pages)}</div>
</div>"""
        )
    board_pages_html = "\n".join(page_blocks)
    appendix_rows_html = "\n".join(appendix_html)

    document = f"""<title>{draft_season} Big Board</title>
<style>
  body {{ font-family: Georgia, "Times New Roman", serif; font-size: 11px; margin: 20px; color: #111; background: #ccc; }}
  h1 {{ font-family: Arial, Helvetica, sans-serif; font-size: 18px; margin: 0 0 4px 0; }}
  p.note {{ font-family: Arial, Helvetica, sans-serif; font-size: {NOTE_FONT_PX}px; line-height: 1.4; color: #444; margin: 0 0 14px 0; }}
  h2 {{ font-family: Arial, Helvetica, sans-serif; font-size: 15px; margin: 28px 0 4px 0; }}

  /* .page is sized to the *content* area only (page size minus {MARGIN_IN}in
     margin on every side) - the {MARGIN_IN}in margin itself comes from @page
     below (real print dialogs) or the browser/printer's own default margin
     (headless/CLI printing, which typically ignores @page margin and
     imposes ~0.4in regardless). Either way there is exactly one margin
     layer, not two. */
  .page {{
    width: {CONTENT_W_IN}in;
    height: {CONTENT_H_IN}in;
    box-sizing: border-box;
    background: #fff;
    margin: 0 auto 16px auto;
    box-shadow: 0 1px 4px rgba(0,0,0,0.3);
    position: relative;
  }}
  .page:not(:last-child) {{ page-break-after: always; break-after: page; }}
  .cols {{ display: flex; gap: {COL_GAP_PX}px; align-items: flex-start; }}
  .cols table {{ width: {COL_W_PX}px; border-collapse: collapse; table-layout: fixed; }}
  .cols col.c-rank {{ width: 27px; }}
  .cols col.c-pos {{ width: 26px; }}
  .cols col.c-vorp {{ width: 40px; }}
  .cols td, .cols th {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: {ROW_FONT_PX}px;
    line-height: {ROW_LINE_HEIGHT};
    padding: 1px 3px;
    border: 1px solid #999;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .cols th {{ background: #eee; }}
  .cols tr:nth-child(even) {{ background: #f7f7f7; }}
  .cols tr.kept {{ color: #555; }}
  .cols tr.kept td:nth-child(2) {{ text-decoration: line-through; }}
  .kept-note {{ font-size: 8px; text-decoration: none; color: #555; }}
  .pagenum {{
    position: absolute;
    bottom: 0;
    right: 0;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 9px;
    color: #888;
  }}

  table.appendix {{ border-collapse: collapse; width: 100%; }}
  table.appendix th, table.appendix td {{ border: 1px solid #999; padding: 2px 6px; text-align: left; vertical-align: top; }}
  table.appendix th {{ font-family: Arial, Helvetica, sans-serif; background: #eee; }}
  table.appendix tr:nth-child(even) {{ background: #f7f7f7; }}

  @media print {{
    body {{ background: #fff; }}
    @page {{ size: letter portrait; margin: {MARGIN_IN}in; }}
    .page {{ box-shadow: none; margin: 0; }}
    h2 {{ break-before: page; }}
  }}
</style>

{board_pages_html}

<h2>Appendix: Rationale notes</h2>
<table class="appendix">
<tr><th>Rank</th><th>Name</th><th>Rationale</th></tr>
{appendix_rows_html}
</table>
"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")

    return BigboardPrintResult(
        out_path=out_path,
        total_rows=len(rows),
        printed_rows=len(printed),
        pages=len(pages),
        appendix_rows=len(appendix_html),
        unmatched_keepers=unmatched_keepers,
    )
