"""`draft keepers` — keeper eligibility/cost for every player on a roster.

Builds the multi-season draft-pick history `keeper_history` needs by
reading already-synced `data/sleeper/drafts/<season>.parquet` files,
season-by-season, decrementing the season year until a season's data isn't
found locally (or `max_seasons_back` is reached). This is a simplification
of "walk `previous_league_id`" (PROJECT_PLAN.md §3, §6.5): that chain walk
already happened implicitly when each season was synced via
`sleeper league sync --season <year> --league-id <id>` (`league.py`'s
`resolve_league_id` fallback exists for exactly this reason) — season year
decrements by exactly 1 per NFL season, so once the data is synced locally
and keyed by season year, re-deriving the league_id chain to re-walk it here
would be redundant. If a season's data was never synced, the walk simply
stops there rather than fetching live — keeper history is computed from
what's already on disk, not a live re-sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sleeper_agent.adp.sync import latest_adp_snapshot
from sleeper_agent.config import data_dir
from sleeper_agent.models.sleeper import DraftPick
from sleeper_agent.sleeper_client import sync as sleeper_sync
from sleeper_agent.sleeper_client.draft import (
    KeeperEligible,
    KeeperEligibleUndraftedDefault,
    KeeperStatus,
)
from sleeper_agent.storage.parquet_store import read_table

DEFAULT_TOTAL_ROUNDS = 15  # this league's confirmed real setting, PROJECT_PLAN.md §3
DEFAULT_NUM_TEAMS = 12  # this league's confirmed real setting, PROJECT_PLAN.md §3


def load_latest_adp(root: Path) -> tuple[str, dict[str, int]] | None:
    """Latest synced ADP snapshot (`adp sync`) as `(retrieved_date,
    {sleeper_id: adp_pick})`, for `keeper_history`'s ADP-reset branch. None
    when no snapshot has been synced yet — callers fall back to
    `keeper_history`'s flat `total_rounds` default.
    """
    result = latest_adp_snapshot(data_dir(root) / "adp")
    if result is None:
        return None
    retrieved_date, df = result
    pick_by_sleeper_id = {
        row["sleeper_id"]: row["adp_pick"]
        for row in df.to_dicts()
        if row["sleeper_id"] is not None
    }
    return retrieved_date, pick_by_sleeper_id


def build_season_chain(
    repo_root: Path,
    starting_season: str,
    *,
    max_seasons_back: int = 10,
) -> tuple[list[str], dict[str, list[DraftPick]]]:
    sleeper_dir = data_dir(repo_root) / "sleeper"
    season_chain: list[str] = []
    picks_by_season: dict[str, list[DraftPick]] = {}

    season_int = int(starting_season)
    for offset in range(1, max_seasons_back + 1):
        season = str(season_int - offset)
        drafts_path = sleeper_dir / "drafts" / f"{season}.parquet"
        if not drafts_path.exists():
            break
        picks = sleeper_sync.dataframe_to_draft_picks(
            read_table(
                drafts_path, expected_schema_version=sleeper_sync.DRAFTS_SCHEMA_VERSION
            )
        )
        season_chain.append(season)
        picks_by_season[season] = picks

    return season_chain, picks_by_season


def infer_total_rounds(
    season_chain: list[str],
    picks_by_season: dict[str, list[DraftPick]],
    *,
    default: int = DEFAULT_TOTAL_ROUNDS,
) -> int:
    """The most recent available season's max round, or `default` if there's no history yet."""
    if not season_chain:
        return default
    most_recent_picks = picks_by_season.get(season_chain[0], [])
    if not most_recent_picks:
        return default
    return max(pick.round for pick in most_recent_picks)


_ELIGIBLE_STATUSES = (KeeperEligible, KeeperEligibleUndraftedDefault)


@dataclass(frozen=True)
class KeeperCandidate:
    player_id: str
    name: str
    position: str | None
    status: KeeperStatus
    vorp_season: float | None


def value_per_cost(candidate: KeeperCandidate) -> float:
    """Rank key for eligible keepers: value-per-cost, not raw value.

    A cheap round-9 keeper can beat an expensive round-2 one — see
    `.claude/skills/draft.md`.
    """
    if (
        not isinstance(candidate.status, _ELIGIBLE_STATUSES)
        or candidate.vorp_season is None
    ):
        return float("-inf")
    return candidate.vorp_season / candidate.status.cost_round


def rank_keeper_candidates(candidates: list[KeeperCandidate]) -> list[KeeperCandidate]:
    eligible = [c for c in candidates if isinstance(c.status, _ELIGIBLE_STATUSES)]
    ineligible = [c for c in candidates if not isinstance(c.status, _ELIGIBLE_STATUSES)]
    eligible.sort(key=value_per_cost, reverse=True)
    return eligible + ineligible
