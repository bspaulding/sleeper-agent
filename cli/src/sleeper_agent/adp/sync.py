"""Sync `data/adp/<date>.parquet` — a dated DraftSharks ADP snapshot, matched
to Sleeper player_ids.

Backs the keeper-cost ADP-reset rule (`todo.md`,
`sleeper_client.draft.keeper_history`'s ADP branch): `latest_adp_snapshot`
reads the newest of these snapshots by filename — an ISO date, so
lexicographic order is chronological order — and `draft_tools.keepers`'s
`load_latest_adp` turns it into the `{sleeper_id: adp_pick}` lookup
`keeper_history` prices a traded/FA-pickup player's keeper cost from, instead
of the flat draft's-last-round fallback. Nothing here re-fetches
automatically; re-run `adp sync` whenever a live keeper/trade decision needs a
fresher number.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sleeper_agent.adp.draftsharks import AdpEntry, fetch_adp_html, parse_adp_html
from sleeper_agent.storage.parquet_store import read_table, write_table

ADP_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AdpSyncResult:
    retrieved_date: str
    total_rows: int
    matched_rows: int
    unmatched_names: list[str]


_SUFFIX_PATTERN = r"\s+(jr|sr|ii|iii|iv)$"


def _normalize_name(expr: pl.Expr) -> pl.Expr:
    """Lowercase, drop periods/apostrophes, and strip a trailing Jr/Sr/II-IV
    suffix. Sleeper's `players.parquet` names are already suffix-free (spot-
    checked: "Kenneth Walker", "Harold Fannin"), but DraftSharks keeps the
    suffix on `ln` (e.g. "Kenneth Walker III") — applying the same strip to
    both sides is a no-op for Sleeper and the fix for DraftSharks.
    """
    return (
        expr.str.to_lowercase()
        .str.replace_all(r"[.']", "", literal=False)
        .str.strip_chars()
        .str.replace_all(_SUFFIX_PATTERN, "", literal=False)
        .str.strip_chars()
    )


def match_entries_to_sleeper_ids(
    entries: list[AdpEntry], players_df: pl.DataFrame
) -> pl.DataFrame:
    """Left-join DraftSharks entries onto `data/sleeper/players.parquet` by
    normalized (full name, position) — same convention as
    `draft_tools/rookies.py::crosswalk_draft_picks_to_sleeper_ids`. Unmatched
    rows keep a null `sleeper_id` rather than being dropped or erroring:
    callers (`load_latest_adp`) already skip null-`sleeper_id` rows, and most
    unmatched names are deep-bench/practice-squad players with no
    keeper-relevant Sleeper record anyway.
    """
    entries_df = pl.DataFrame(
        {
            "ds_player_id": [e.ds_player_id for e in entries],
            "full_name": [f"{e.first_name} {e.last_name}" for e in entries],
            "team": [e.team for e in entries],
            "position": [e.position for e in entries],
            "adp_pick": [e.adp_pick for e in entries],
            "ds_rank": [e.ds_rank for e in entries],
            "pos_adp": [e.pos_adp for e in entries],
            "market_index": [e.market_index for e in entries],
        }
    )
    entries_normalized = entries_df.with_columns(
        _normalize_name(pl.col("full_name")).alias("_join_name"),
        pl.col("position").str.to_lowercase().alias("_join_position"),
    )
    players_normalized = players_df.with_columns(
        _normalize_name(pl.col("name")).alias("_join_name"),
        pl.col("position").str.to_lowercase().alias("_join_position"),
    ).select(["_join_name", "_join_position", "player_id"])

    joined = entries_normalized.join(
        players_normalized, on=["_join_name", "_join_position"], how="left"
    ).rename({"player_id": "sleeper_id"})
    return joined.drop(["_join_name", "_join_position"])


def sync_adp(
    adp_dir: Path,
    players_df: pl.DataFrame,
    *,
    retrieved_date: str,
    fetch_html: Callable[[], str] = fetch_adp_html,
) -> AdpSyncResult:
    html = fetch_html()
    entries = parse_adp_html(html)
    matched = match_entries_to_sleeper_ids(entries, players_df)
    df = matched.with_columns(pl.lit(retrieved_date).alias("retrieved_date"))

    write_table(
        df, adp_dir / f"{retrieved_date}.parquet", schema_version=ADP_SCHEMA_VERSION
    )

    unmatched_names = (
        df.filter(pl.col("sleeper_id").is_null()).get_column("full_name").to_list()
    )
    matched_rows = df.filter(pl.col("sleeper_id").is_not_null()).height
    return AdpSyncResult(
        retrieved_date=retrieved_date,
        total_rows=df.height,
        matched_rows=matched_rows,
        unmatched_names=unmatched_names,
    )


def latest_adp_snapshot(adp_dir: Path) -> tuple[str, pl.DataFrame] | None:
    """The most recently synced ADP snapshot, or None if `adp_dir` has none
    yet. Filenames are ISO dates (`YYYY-MM-DD.parquet`), so lexicographic max
    is also chronological max — no need to parse dates out to sort them.
    """
    if not adp_dir.exists():
        return None
    files = sorted(adp_dir.glob("*.parquet"))
    if not files:
        return None
    latest = files[-1]
    df = read_table(latest, expected_schema_version=ADP_SCHEMA_VERSION)
    return latest.stem, df
