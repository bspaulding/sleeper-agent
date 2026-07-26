"""Parse/write YAML frontmatter + body for a markdown wiki page.

Wiki pages are `---\\n<yaml>\\n---\\n<body>`. The body is treated as opaque
text by this module except for a small helper that appends a dated entry to
a `## News` section, since that's the one body-editing operation several
callers (the news-research skill's instructions, `wiki_tools/staleness.py`)
need in common.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

NEWS_HEADING = "## News"


class MalformedFrontmatterError(Exception):
    pass


@dataclass(frozen=True)
class WikiPage:
    frontmatter: dict[str, object]
    body: str


def parse_page(text: str) -> WikiPage:
    if not text.startswith("---\n"):
        raise MalformedFrontmatterError(
            "page does not start with '---' frontmatter fence"
        )
    end = text.find("\n---\n", 4)
    if end == -1:
        raise MalformedFrontmatterError("no closing '---' frontmatter fence found")
    raw_yaml = text[4:end]
    body = text[end + len("\n---\n") :]
    loaded = yaml.safe_load(raw_yaml)
    frontmatter = loaded if isinstance(loaded, dict) else {}
    return WikiPage(frontmatter=frontmatter, body=body)


def render_page(page: WikiPage) -> str:
    raw_yaml = yaml.safe_dump(page.frontmatter, sort_keys=False).rstrip("\n")
    return f"---\n{raw_yaml}\n---\n{page.body}"


def append_news_entry(page: WikiPage, entry: str) -> WikiPage:
    """Append a formatted line to the page's `## News` section body.

    If the section doesn't exist yet, it's created at the end of the body.
    """
    line = entry if entry.startswith("- ") else f"- {entry}"
    if NEWS_HEADING not in page.body:
        separator = "" if page.body.endswith("\n") or page.body == "" else "\n"
        new_body = f"{page.body}{separator}\n{NEWS_HEADING}\n\n{line}\n"
        return WikiPage(frontmatter=page.frontmatter, body=new_body)

    heading_index = page.body.index(NEWS_HEADING)
    insert_at = heading_index + len(NEWS_HEADING)
    before = page.body[:insert_at]
    after = page.body[insert_at:]
    new_body = f"{before}\n{line}{after}"
    return WikiPage(frontmatter=page.frontmatter, body=new_body)
