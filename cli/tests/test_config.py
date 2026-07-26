from __future__ import annotations

from pathlib import Path

import pytest

from sleeper_agent.config import (
    RepoRootNotFoundError,
    data_dir,
    decisions_dir,
    find_repo_root,
    wiki_dir,
)


def test_find_repo_root_walks_up_to_git_marker(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "cli" / "src" / "sleeper_agent"
    nested.mkdir(parents=True)

    assert find_repo_root(nested) == tmp_path


def test_find_repo_root_walks_up_to_project_plan_marker(tmp_path: Path) -> None:
    (tmp_path / "PROJECT_PLAN.md").write_text("# plan\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert find_repo_root(nested) == tmp_path


def test_find_repo_root_raises_when_no_marker_exists(tmp_path: Path) -> None:
    with pytest.raises(RepoRootNotFoundError):
        find_repo_root(tmp_path)


def test_path_constants_are_relative_to_repo_root(tmp_path: Path) -> None:
    assert data_dir(tmp_path) == tmp_path / "data"
    assert wiki_dir(tmp_path) == tmp_path / "wiki"
    assert decisions_dir(tmp_path) == tmp_path / "decisions"
