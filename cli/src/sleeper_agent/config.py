"""Repo-root discovery and path constants.

No secrets or environment variables are needed for Phase 1 (see
IMPLEMENTATION_PLAN.md §0.6) — every path here is derived from the repo root.
"""

from __future__ import annotations

from pathlib import Path

_ROOT_MARKERS = (".git", "PROJECT_PLAN.md")


class RepoRootNotFoundError(Exception):
    pass


def find_repo_root(start: Path) -> Path:
    """Walk upward from `start` looking for a directory containing a root marker."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        if any((candidate / marker).exists() for marker in _ROOT_MARKERS):
            return candidate
    raise RepoRootNotFoundError(f"no repo root found walking up from {start}")


def data_dir(repo_root: Path) -> Path:
    return repo_root / "data"


def wiki_dir(repo_root: Path) -> Path:
    return repo_root / "wiki"


def decisions_dir(repo_root: Path) -> Path:
    return repo_root / "decisions"
