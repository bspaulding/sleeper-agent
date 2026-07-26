"""`wiki scaffold players|teams` — idempotently ensure wiki stub pages exist.

Idempotent means: create a page with the agreed frontmatter + empty body
sections if it doesn't exist yet, and never touch a page that already
exists (a scaffolded page may have real research content by the time this
runs again).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sleeper_agent.models.sleeper import Player, Roster
from sleeper_agent.wiki_tools.frontmatter import WikiPage, render_page

NFL_TEAM_CODES: tuple[str, ...] = (
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
)  # fmt: skip


@dataclass(frozen=True)
class ScaffoldResult:
    created: tuple[Path, ...]
    already_existed: tuple[Path, ...]


def slugify(name: str) -> str:
    lowered = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "player"


def _player_page_path(wiki_dir: Path, player: Player) -> Path:
    return wiki_dir / "players" / f"{player.player_id}-{slugify(player.name)}.md"


def _write_if_absent(path: Path, page: WikiPage) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_page(page))
    return True


def scaffold_players(
    wiki_dir: Path,
    players: list[Player],
) -> ScaffoldResult:
    """Scaffold `wiki/players/*.md` stubs — skipping DEF units.

    Sleeper rosters a defense as a "player" keyed by team code (e.g. `BUF`,
    position `DEF`). Per PROJECT_PLAN.md §5.3, a DEF slot's notes/news live
    on that team's `wiki/nfl-teams/<code>.md` page (scaffolded separately by
    `scaffold_teams`), not a standalone player page — so DEF entries are
    filtered out here rather than producing a redundant, orphaned page.
    """
    created: list[Path] = []
    already_existed: list[Path] = []
    for player in players:
        if player.position == "DEF":
            continue
        path = _player_page_path(wiki_dir, player)
        page = WikiPage(
            frontmatter={
                "sleeper_id": player.player_id,
                "name": player.name,
                "position": player.position,
                "nfl_team": player.team,
                "last_researched": None,
            },
            body="\n## News\n\n",
        )
        if _write_if_absent(path, page):
            created.append(path)
        else:
            already_existed.append(path)
    return ScaffoldResult(
        created=tuple(created), already_existed=tuple(already_existed)
    )


def players_for_roster(
    roster: Roster, players_by_id: dict[str, Player]
) -> list[Player]:
    return [players_by_id[pid] for pid in roster.player_ids if pid in players_by_id]


def scaffold_teams(wiki_dir: Path) -> ScaffoldResult:
    created: list[Path] = []
    already_existed: list[Path] = []
    for code in NFL_TEAM_CODES:
        path = wiki_dir / "nfl-teams" / f"{code}.md"
        page = WikiPage(
            frontmatter={"team_code": code, "last_researched": None},
            body="\n## News\n\n",
        )
        if _write_if_absent(path, page):
            created.append(path)
        else:
            already_existed.append(path)
    return ScaffoldResult(
        created=tuple(created), already_existed=tuple(already_existed)
    )
