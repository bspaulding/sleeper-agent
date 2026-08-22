from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from sleeper_agent.models.sleeper import Player, Roster
from sleeper_agent.wiki_tools.frontmatter import (
    MalformedFrontmatterError,
    WikiPage,
    append_news_entry,
    parse_page,
    render_page,
)
from sleeper_agent.wiki_tools.frontmatter_sync import sync_player_team_frontmatter
from sleeper_agent.wiki_tools.scaffold import (
    NFL_TEAM_CODES,
    players_for_roster,
    scaffold_players,
    scaffold_teams,
    slugify,
)
from sleeper_agent.wiki_tools.staleness import stale_pages


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


# --- scaffold ---------------------------------------------------------


def make_player(
    player_id: str = "1", name: str = "Test Player", position: str = "WR"
) -> Player:
    return Player(
        player_id=player_id,
        name=name,
        position=position,
        team="BUF",
        status="Active",
        injury_status=None,
        fantasy_positions=(position,),
        years_exp=3,
    )


def test_slugify_lowercases_and_hyphenates() -> None:
    assert slugify("Ja'Marr Chase") == "ja-marr-chase"


def test_slugify_falls_back_when_name_has_no_alnum_chars() -> None:
    assert slugify("---") == "player"


def test_scaffold_players_creates_pages_for_each_player(tmp_path: Path) -> None:
    players = [make_player("1", "Player One"), make_player("2", "Player Two")]

    result = scaffold_players(tmp_path, players)

    assert len(result.created) == 2
    assert result.already_existed == ()
    page_text = (tmp_path / "players" / "1-player-one.md").read_text()
    page = parse_page(page_text)
    assert page.frontmatter == {
        "sleeper_id": "1",
        "name": "Player One",
        "position": "WR",
        "nfl_team": "BUF",
        "last_researched": None,
    }


def test_scaffold_players_skips_def_units(tmp_path: Path) -> None:
    defense = make_player("BUF", "Buffalo Bills", position="DEF")
    wr = make_player("1", "Player One")

    result = scaffold_players(tmp_path, [defense, wr])

    assert len(result.created) == 1
    assert (tmp_path / "players" / "1-player-one.md").exists()
    assert not (tmp_path / "players" / "BUF-buffalo-bills.md").exists()


def test_scaffold_players_is_idempotent_and_never_overwrites(tmp_path: Path) -> None:
    player = make_player("1", "Player One")
    path = tmp_path / "players" / "1-player-one.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nsleeper_id: '1'\n---\nreal research notes\n")

    result = scaffold_players(tmp_path, [player])

    assert result.created == ()
    assert result.already_existed == (path,)
    assert "real research notes" in path.read_text()


def test_scaffold_teams_creates_all_32_team_pages(tmp_path: Path) -> None:
    result = scaffold_teams(tmp_path)

    assert len(result.created) == 32
    assert len(NFL_TEAM_CODES) == 32
    assert (tmp_path / "nfl-teams" / "BUF.md").exists()


def test_scaffold_teams_is_idempotent(tmp_path: Path) -> None:
    scaffold_teams(tmp_path)

    result = scaffold_teams(tmp_path)

    assert result.created == ()
    assert len(result.already_existed) == 32


def test_players_for_roster_skips_ids_missing_from_the_players_dict() -> None:
    roster = Roster(
        roster_id=1,
        owner_id="u1",
        league_id="lid",
        player_ids=("1", "2", "BUF"),
        starter_ids=(),
        wins=0,
        losses=0,
        ties=0,
        points_for=0.0,
        waiver_budget_used=0,
    )
    players_by_id = {"1": make_player("1"), "2": make_player("2")}

    result = players_for_roster(roster, players_by_id)

    assert [p.player_id for p in result] == ["1", "2"]


# --- staleness ----------------------------------------------------------


def test_stale_pages_flags_missing_last_researched(tmp_path: Path) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    (players_dir / "1-a.md").write_text("---\nlast_researched: null\n---\n")

    pages = stale_pages(tmp_path, ["players"], today=lambda: date(2026, 7, 26))

    assert len(pages) == 1
    assert pages[0].last_researched is None


def test_stale_pages_accepts_unquoted_yaml_date(tmp_path: Path) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    # Unquoted YAML dates parse as datetime.date, not str.
    (players_dir / "1-old.md").write_text("---\nlast_researched: 2026-07-01\n---\n")

    pages = stale_pages(tmp_path, ["players"], days=7, today=lambda: date(2026, 7, 26))

    assert pages[0].last_researched == date(2026, 7, 1)


def test_stale_pages_distinguishes_old_from_fresh(tmp_path: Path) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    (players_dir / "1-old.md").write_text("---\nlast_researched: '2026-07-01'\n---\n")
    (players_dir / "2-fresh.md").write_text("---\nlast_researched: '2026-07-25'\n---\n")

    pages = stale_pages(tmp_path, ["players"], days=7, today=lambda: date(2026, 7, 26))

    assert [p.path.name for p in pages] == ["1-old.md"]


def test_stale_pages_skips_missing_scope_directory(tmp_path: Path) -> None:
    pages = stale_pages(tmp_path, ["nonexistent"], today=lambda: date(2026, 7, 26))

    assert pages == []


def test_stale_pages_rejects_unexpected_last_researched_type(tmp_path: Path) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    (players_dir / "1-a.md").write_text("---\nlast_researched: 20260701\n---\n")

    with pytest.raises(TypeError):
        stale_pages(tmp_path, ["players"], today=lambda: date(2026, 7, 26))


# --- frontmatter sync --------------------------------------------------


def make_players_df(rows: list[dict[str, object]]) -> pl.DataFrame:
    return pl.DataFrame(rows)


def test_sync_player_team_frontmatter_updates_stale_team(tmp_path: Path) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    page_path = players_dir / "1-player-one.md"
    page_path.write_text(
        "---\nsleeper_id: '1'\nname: Player One\nnfl_team: WAS\n"
        "last_researched: '2026-08-01'\n---\n\n## News\n\n- real research notes\n"
    )
    players_df = make_players_df([{"player_id": "1", "team": "SF"}])

    result = sync_player_team_frontmatter(tmp_path, players_df)

    assert result.updated == (page_path,)
    assert result.unchanged == ()
    assert result.skipped == ()
    page = parse_page(page_path.read_text())
    assert page.frontmatter["nfl_team"] == "SF"
    assert page.frontmatter["last_researched"] == "2026-08-01"
    assert "real research notes" in page.body


def test_sync_player_team_frontmatter_leaves_matching_pages_unchanged(
    tmp_path: Path,
) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    page_path = players_dir / "1-player-one.md"
    original_text = "---\nsleeper_id: '1'\nnfl_team: SF\n---\n\n## News\n\n- note\n"
    page_path.write_text(original_text)
    players_df = make_players_df([{"player_id": "1", "team": "SF"}])

    result = sync_player_team_frontmatter(tmp_path, players_df)

    assert result.updated == ()
    assert result.unchanged == (page_path,)
    assert page_path.read_text() == original_text


def test_sync_player_team_frontmatter_skips_pages_with_no_matching_player(
    tmp_path: Path,
) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    page_path = players_dir / "1-player-one.md"
    original_text = "---\nsleeper_id: '1'\nnfl_team: WAS\n---\n"
    page_path.write_text(original_text)
    players_df = make_players_df([{"player_id": "2", "team": "SF"}])

    result = sync_player_team_frontmatter(tmp_path, players_df)

    assert result.updated == ()
    assert result.unchanged == ()
    assert result.skipped == (page_path,)
    assert page_path.read_text() == original_text


def test_sync_player_team_frontmatter_handles_player_with_no_current_team(
    tmp_path: Path,
) -> None:
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    page_path = players_dir / "1-player-one.md"
    page_path.write_text("---\nsleeper_id: '1'\nnfl_team: WAS\n---\n")
    players_df = make_players_df([{"player_id": "1", "team": None}])

    result = sync_player_team_frontmatter(tmp_path, players_df)

    assert result.updated == (page_path,)
    page = parse_page(page_path.read_text())
    assert page.frontmatter["nfl_team"] is None
