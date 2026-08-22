"""`wiki sync-frontmatter` -- refresh `nfl_team` on player pages from the
latest Sleeper player sync.

`nfl_team` is set once at scaffold time (`wiki_tools/scaffold.py`) and never
touched again, so a player who changes team *after* their page already
exists -- exactly the role-changer population `value/team_changes.py`
detects -- goes stale silently. Confirmed live: a `sleeper players sync`
refresh during the 2026 pre-draft pass found 3 wiki pages with a stale
`nfl_team` despite the underlying Sleeper data already being correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sleeper_agent.wiki_tools.frontmatter import WikiPage, parse_page, render_page


@dataclass(frozen=True)
class FrontmatterSyncResult:
    updated: tuple[Path, ...]
    unchanged: tuple[Path, ...]
    skipped: tuple[Path, ...]


def sync_player_team_frontmatter(
    wiki_dir: Path, players_df: pl.DataFrame
) -> FrontmatterSyncResult:
    """Update every `wiki/players/*.md` page's `nfl_team` to match
    `players_df` (`data/sleeper/players.parquet`).

    A page whose `sleeper_id` has no matching row in `players_df` is
    skipped rather than errored -- a sync gap, not evidence the page is
    wrong (same convention as `value/scoring.py::filter_rostered`). Only
    `nfl_team` is touched; every other frontmatter field and the body are
    preserved exactly.
    """
    team_by_id = dict(
        zip(
            players_df["player_id"].to_list(),
            players_df["team"].to_list(),
            strict=True,
        )
    )
    updated: list[Path] = []
    unchanged: list[Path] = []
    skipped: list[Path] = []
    for path in sorted((wiki_dir / "players").glob("*.md")):
        page = parse_page(path.read_text())
        sleeper_id = page.frontmatter.get("sleeper_id")
        if sleeper_id is None or str(sleeper_id) not in team_by_id:
            skipped.append(path)
            continue
        current_team = team_by_id[str(sleeper_id)]
        if page.frontmatter.get("nfl_team") == current_team:
            unchanged.append(path)
            continue
        new_frontmatter = dict(page.frontmatter)
        new_frontmatter["nfl_team"] = current_team
        path.write_text(
            render_page(WikiPage(frontmatter=new_frontmatter, body=page.body))
        )
        updated.append(path)
    return FrontmatterSyncResult(
        updated=tuple(updated), unchanged=tuple(unchanged), skipped=tuple(skipped)
    )
