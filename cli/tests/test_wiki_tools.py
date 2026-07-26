from __future__ import annotations

import pytest

from sleeper_agent.wiki_tools.frontmatter import (
    MalformedFrontmatterError,
    WikiPage,
    append_news_entry,
    parse_page,
    render_page,
)


def make_page_text(frontmatter_yaml: str, body: str) -> str:
    return f"---\n{frontmatter_yaml}\n---\n{body}"


def test_parse_page_splits_frontmatter_and_body() -> None:
    text = make_page_text("sleeper_id: '123'\nname: Test Player\n", "Some notes.\n")

    page = parse_page(text)

    assert page.frontmatter == {"sleeper_id": "123", "name": "Test Player"}
    assert page.body == "Some notes.\n"


def test_parse_page_raises_when_missing_opening_fence() -> None:
    with pytest.raises(MalformedFrontmatterError):
        parse_page("no frontmatter here\n")


def test_parse_page_raises_when_missing_closing_fence() -> None:
    with pytest.raises(MalformedFrontmatterError):
        parse_page("---\nkey: value\n")


def test_parse_page_treats_empty_frontmatter_as_empty_dict() -> None:
    page = parse_page("---\n\n---\nbody text\n")

    assert page.frontmatter == {}
    assert page.body == "body text\n"


def test_render_page_round_trips_through_parse_page() -> None:
    page = WikiPage(
        frontmatter={"sleeper_id": "123", "name": "Test Player"}, body="Notes.\n"
    )

    rendered = render_page(page)
    reparsed = parse_page(rendered)

    assert reparsed == page


def test_append_news_entry_creates_section_when_absent() -> None:
    page = WikiPage(frontmatter={}, body="Intro text.\n")

    updated = append_news_entry(
        page, "2026-07-26 [injury] hurt ankle ([source](https://x))"
    )

    assert "## News" in updated.body
    assert "- 2026-07-26 [injury] hurt ankle ([source](https://x))" in updated.body
    assert updated.body.index("## News") > updated.body.index("Intro text.")


def test_append_news_entry_prepends_within_existing_section() -> None:
    page = WikiPage(
        frontmatter={},
        body="Intro.\n\n## News\n\n- older entry\n",
    )

    updated = append_news_entry(page, "newer entry")

    lines_after_heading = updated.body.split("## News\n", 1)[1]
    assert lines_after_heading.strip().splitlines()[0] == "- newer entry"
    assert "- older entry" in updated.body


def test_append_news_entry_accepts_entry_already_prefixed_with_dash() -> None:
    page = WikiPage(frontmatter={}, body="")

    updated = append_news_entry(page, "- already prefixed")

    assert updated.body.count("- already prefixed") == 1
