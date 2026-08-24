"""`decisions new` — scaffold a decision-log entry with agreed frontmatter.

The LLM fills in the actual content (Summary/Reasoning/Data/Outcome); this
just prevents format drift across the season's worth of decision files.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from enum import Enum
from pathlib import Path

from sleeper_agent.wiki_tools.frontmatter import WikiPage, render_page

BODY_TEMPLATE = """
## Summary

## Reasoning

## Data

## Outcome
"""


class DecisionKind(Enum):
    DRAFT = "draft"
    KEEPER = "keeper"
    TRADE = "trade"
    WAIVER = "waiver"
    FREEAGENT = "freeagent"
    BIGBOARD = "bigboard"


class DecisionAlreadyExistsError(Exception):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"{path} already exists")


def new_decision(
    decisions_dir: Path,
    kind: DecisionKind,
    slug: str,
    season: str,
    *,
    today: Callable[[], date] = date.today,
) -> Path:
    decision_date = today().isoformat()
    path = decisions_dir / season / f"{decision_date}-{kind.value}-{slug}.md"
    if path.exists():
        raise DecisionAlreadyExistsError(path)

    page = WikiPage(
        frontmatter={
            "date": decision_date,
            "kind": kind.value,
            "season": season,
            "week": None,
            "status": "recommended",
            "players_involved": [],
            "related_wiki": [],
        },
        body=BODY_TEMPLATE,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_page(page))
    return path
