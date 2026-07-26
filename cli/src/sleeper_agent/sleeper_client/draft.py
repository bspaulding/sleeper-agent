"""Draft object + picks (public, no auth) — live board polling and keeper history."""

from __future__ import annotations

from typing import cast

from sleeper_agent.models.sleeper import (
    Draft,
    DraftPick,
    DraftRaw,
    parse_draft,
    parse_draft_pick,
    raw_json_dict,
)
from sleeper_agent.sleeper_client.http import SLEEPER_BASE_URL, get_json


def fetch_draft(draft_id: str, *, base_url: str = SLEEPER_BASE_URL) -> Draft:
    raw = raw_json_dict(get_json(f"{base_url}/draft/{draft_id}"))
    return parse_draft(cast(DraftRaw, raw))


def fetch_draft_picks(
    draft_id: str, *, base_url: str = SLEEPER_BASE_URL
) -> list[DraftPick]:
    raw = get_json(f"{base_url}/draft/{draft_id}/picks")
    return [parse_draft_pick(item) for item in raw or []]
