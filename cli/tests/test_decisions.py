from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from sleeper_agent.decisions.index import build_index, collect_decisions
from sleeper_agent.decisions.scaffold import (
    DecisionAlreadyExistsError,
    DecisionKind,
    new_decision,
)
from sleeper_agent.wiki_tools.frontmatter import parse_page


def test_new_decision_scaffolds_expected_frontmatter_and_sections(
    tmp_path: Path,
) -> None:
    path = new_decision(
        tmp_path,
        DecisionKind.WAIVER,
        "pickup-someone",
        "2026",
        today=lambda: date(2026, 7, 26),
    )

    assert path == tmp_path / "2026" / "2026-07-26-waiver-pickup-someone.md"
    page = parse_page(path.read_text())
    assert page.frontmatter == {
        "date": "2026-07-26",
        "kind": "waiver",
        "season": "2026",
        "week": None,
        "status": "recommended",
        "players_involved": [],
        "related_wiki": [],
    }
    for heading in ("## Summary", "## Reasoning", "## Data", "## Outcome"):
        assert heading in page.body


def test_new_decision_raises_when_file_already_exists(tmp_path: Path) -> None:
    new_decision(
        tmp_path, DecisionKind.TRADE, "slug", "2026", today=lambda: date(2026, 7, 26)
    )

    with pytest.raises(DecisionAlreadyExistsError):
        new_decision(
            tmp_path,
            DecisionKind.TRADE,
            "slug",
            "2026",
            today=lambda: date(2026, 7, 26),
        )


def test_collect_decisions_returns_empty_list_when_dir_missing(tmp_path: Path) -> None:
    assert collect_decisions(tmp_path / "nonexistent") == []


def test_collect_decisions_reads_frontmatter_sorted_by_date(tmp_path: Path) -> None:
    new_decision(
        tmp_path, DecisionKind.WAIVER, "later", "2026", today=lambda: date(2026, 7, 27)
    )
    new_decision(
        tmp_path, DecisionKind.TRADE, "earlier", "2026", today=lambda: date(2026, 7, 20)
    )

    entries = collect_decisions(tmp_path)

    assert [e.path.name for e in entries] == [
        "2026-07-20-trade-earlier.md",
        "2026-07-27-waiver-later.md",
    ]


def test_build_index_writes_wiki_decisions_md(tmp_path: Path) -> None:
    decisions_dir = tmp_path / "decisions"
    wiki_dir = tmp_path / "wiki"
    new_decision(
        decisions_dir,
        DecisionKind.KEEPER,
        "keep-someone",
        "2026",
        today=lambda: date(2026, 7, 26),
    )

    index_path = build_index(decisions_dir, wiki_dir)

    assert index_path == wiki_dir / "decisions.md"
    content = index_path.read_text()
    assert "2026-07-26 [keeper] season 2026 (recommended)" in content
    assert "2026-07-26-keeper-keep-someone" in content
