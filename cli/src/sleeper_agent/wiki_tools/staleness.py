"""`wiki stale` — list pages whose `last_researched` is missing or old.

This is what the news-research skill queries instead of guessing what needs
attention (see `.claude/skills/news-research.md`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from sleeper_agent.wiki_tools.frontmatter import parse_page


@dataclass(frozen=True)
class StalePage:
    path: Path
    last_researched: date | None


def _parse_last_researched(raw: object) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        return date.fromisoformat(raw)
    raise TypeError(f"unexpected last_researched value: {raw!r}")


def stale_pages(
    wiki_dir: Path,
    scope_dirs: list[str],
    *,
    days: int = 7,
    today: Callable[[], date] = date.today,
) -> list[StalePage]:
    cutoff = today() - timedelta(days=days)
    results: list[StalePage] = []
    for scope_dir in scope_dirs:
        directory = wiki_dir / scope_dir
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            page = parse_page(path.read_text())
            last_researched = _parse_last_researched(
                page.frontmatter.get("last_researched")
            )
            if last_researched is None or last_researched < cutoff:
                results.append(StalePage(path=path, last_researched=last_researched))
    return results
