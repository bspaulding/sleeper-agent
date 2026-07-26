"""Full Sleeper player dictionary sync, with a 24h cache per Sleeper's guidance.

Sleeper asks callers not to hit `/players/nfl` more than once/day (it's a
~5k-row payload). `players.meta.json` next to the parquet file records
`fetched_at`; a sync within 24h of the last one is a no-op unless `force`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from sleeper_agent.models.sleeper import parse_player
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL, get_json
from sleeper_agent.storage.parquet_store import write_table

PLAYERS_SCHEMA_VERSION = 1
_CACHE_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class PlayersSyncSkipped:
    fetched_at: datetime


@dataclass(frozen=True)
class PlayersSyncPerformed:
    player_count: int
    fetched_at: datetime


PlayersSyncResult = PlayersSyncSkipped | PlayersSyncPerformed


def _read_meta(meta_path: Path) -> datetime | None:
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    return datetime.fromisoformat(meta["fetched_at"])


def _write_meta(meta_path: Path, fetched_at: datetime) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps({"fetched_at": fetched_at.isoformat()}))


def sync_players(
    players_path: Path,
    meta_path: Path,
    *,
    base_url: str = SLEEPER_BASE_URL,
    force: bool = False,
    now: Callable[[], datetime] = datetime.now,
) -> PlayersSyncResult:
    current = now()
    if not force:
        previous_fetched_at = _read_meta(meta_path)
        if (
            previous_fetched_at is not None
            and current - previous_fetched_at < _CACHE_TTL
        ):
            return PlayersSyncSkipped(fetched_at=previous_fetched_at)

    raw = get_json(f"{base_url}/players/nfl")
    players = [parse_player(player_id, data) for player_id, data in (raw or {}).items()]

    df = pl.DataFrame(
        {
            "player_id": [p.player_id for p in players],
            "name": [p.name for p in players],
            "position": [p.position for p in players],
            "team": [p.team for p in players],
            "status": [p.status for p in players],
            "injury_status": [p.injury_status for p in players],
            "fantasy_positions": [list(p.fantasy_positions) for p in players],
            "years_exp": [p.years_exp for p in players],
        }
    )
    write_table(df, players_path, schema_version=PLAYERS_SCHEMA_VERSION)
    _write_meta(meta_path, current)
    return PlayersSyncPerformed(player_count=len(players), fetched_at=current)
