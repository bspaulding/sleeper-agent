from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sleeper_agent.sleeper_client.players import (
    PlayersSyncPerformed,
    PlayersSyncSkipped,
    sync_players,
)
from sleeper_agent.storage.parquet_store import read_table
from tests.support.mock_http import Request, Response, mock_http_server

RAW_PLAYERS = {
    "7564": {
        "player_id": "7564",
        "first_name": "Ja'Marr",
        "last_name": "Chase",
        "full_name": "Ja'Marr Chase",
        "position": "WR",
        "team": "CIN",
        "status": "Active",
        "injury_status": "",
        "fantasy_positions": ["WR"],
        "years_exp": 4,
    },
    "6770": {
        "player_id": "6770",
        "first_name": "Joe",
        "last_name": "Burrow",
        "full_name": None,
        "position": "QB",
        "team": "CIN",
        "status": "Active",
        "injury_status": None,
        "fantasy_positions": ["QB"],
        "years_exp": 5,
    },
}


def players_handler(request: Request) -> Response:
    body = json.dumps(RAW_PLAYERS).encode()
    return Response(status=200, headers={"Content-Type": "application/json"}, body=body)


def test_sync_players_fetches_and_writes_when_no_cache(tmp_path: Path) -> None:
    players_path = tmp_path / "players.parquet"
    meta_path = tmp_path / "players.meta.json"
    now = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)

    with mock_http_server(players_handler) as base_url:
        result = sync_players(
            players_path, meta_path, base_url=base_url, now=lambda: now
        )

    assert isinstance(result, PlayersSyncPerformed)
    assert result.player_count == 2
    assert result.fetched_at == now

    df = read_table(players_path, expected_schema_version=1)
    assert df.height == 2
    names = set(df["name"].to_list())
    assert names == {"Ja'Marr Chase", "Joe Burrow"}

    meta = json.loads(meta_path.read_text())
    assert meta["fetched_at"] == now.isoformat()


def test_sync_players_skips_when_cache_is_fresh(tmp_path: Path) -> None:
    players_path = tmp_path / "players.parquet"
    meta_path = tmp_path / "players.meta.json"
    fetched_at = datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC)
    meta_path.write_text(json.dumps({"fetched_at": fetched_at.isoformat()}))
    later = fetched_at + timedelta(hours=1)

    def failing_handler(request: Request) -> Response:
        raise AssertionError("should not fetch when cache is fresh")

    with mock_http_server(failing_handler) as base_url:
        result = sync_players(
            players_path, meta_path, base_url=base_url, now=lambda: later
        )

    assert result == PlayersSyncSkipped(fetched_at=fetched_at)
    assert not players_path.exists()


def test_sync_players_refetches_when_cache_is_stale(tmp_path: Path) -> None:
    players_path = tmp_path / "players.parquet"
    meta_path = tmp_path / "players.meta.json"
    fetched_at = datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC)
    meta_path.write_text(json.dumps({"fetched_at": fetched_at.isoformat()}))
    much_later = fetched_at + timedelta(hours=25)

    with mock_http_server(players_handler) as base_url:
        result = sync_players(
            players_path, meta_path, base_url=base_url, now=lambda: much_later
        )

    assert isinstance(result, PlayersSyncPerformed)
    assert players_path.exists()


def test_sync_players_force_refetches_even_with_fresh_cache(tmp_path: Path) -> None:
    players_path = tmp_path / "players.parquet"
    meta_path = tmp_path / "players.meta.json"
    fetched_at = datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC)
    meta_path.write_text(json.dumps({"fetched_at": fetched_at.isoformat()}))
    soon_after = fetched_at + timedelta(minutes=5)

    with mock_http_server(players_handler) as base_url:
        result = sync_players(
            players_path,
            meta_path,
            base_url=base_url,
            force=True,
            now=lambda: soon_after,
        )

    assert isinstance(result, PlayersSyncPerformed)
