"""DraftSharks Sleeper/PPR/12-team ADP page: fetch + parse.

The keeper-cost ADP-reset rule (`todo.md`, decisions/2026/2026-08-23-keeper-
diggs-r7-darnold-r14.md) needs a current ADP number for traded/FA-pickup
players. `draftsharks.com`'s ADP page *looks* JS-rendered (the raw markup is
full of Vue mustache templates with no data in them), but the actual table
data ships inline as a `vueAppData = {...}` JS-object-literal assignment in a
`<script>` tag, and that literal turns out to be strict JSON — quoted keys,
quoted strings, no JS expressions inside it. Confirmed live: a plain HTTP GET
(no browser, no JS execution) returns it, and `json.loads` parses the
extracted blob with no errors.

`seed.players` is a dict of DraftSharks' own player id -> `{fn, ln, tm, pos,
fp, bday}`. `seed.adpSets` has exactly one entry for this URL's fixed
scoring/platform/team-size selection: a flat list of `{id, pick, dsRank,
posAdp, marketIndex}` rows, joined to `players` by `id`. DraftSharks ids are
*not* Sleeper player_ids — spot-checked live, DraftSharks id 9963 is Sam
Darnold, whose real Sleeper player_id is 4943 — so matching to Sleeper
happens downstream in `adp/sync.py` via a name+position join, the same
convention `draft_tools/rookies.py::crosswalk_draft_picks_to_sleeper_ids`
already uses for the nflverse rookie crosswalk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import requests

DRAFTSHARKS_ADP_URL = "https://www.draftsharks.com/adp/ppr/sleeper/12"
_VUE_APP_DATA_VAR = "vueAppData"
_USER_AGENT = "Mozilla/5.0"


class AdpBlobNotFoundError(Exception):
    def __init__(self, var_name: str) -> None:
        self.var_name = var_name
        super().__init__(
            f"{var_name!r} assignment not found in fetched HTML — DraftSharks "
            "may have changed the page's markup"
        )


class AdpBlobShapeError(Exception):
    pass


@dataclass(frozen=True)
class AdpEntry:
    ds_player_id: int
    first_name: str
    last_name: str
    team: str | None
    position: str | None
    adp_pick: int
    ds_rank: int | None
    pos_adp: int | None
    market_index: int | None


def fetch_adp_html(
    url: str = DRAFTSHARKS_ADP_URL,
) -> str:  # pragma: no cover - live web call
    response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.text


def _extract_json_object(html: str, var_name: str) -> str:
    """Brace-match the object literal assigned to `var_name`.

    String-aware (tracks quotes/escapes) so a `}` inside a quoted player name
    or bio field doesn't end the match early.
    """
    marker = html.find(var_name)
    if marker == -1:
        raise AdpBlobNotFoundError(var_name)
    start = html.find("{", marker)
    if start == -1:
        raise AdpBlobNotFoundError(var_name)

    depth = 0
    in_string = False
    string_char = ""
    escape = False
    index = start
    while index < len(html):
        char = html[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == string_char:
                in_string = False
        else:
            if char in ('"', "'"):
                in_string = True
                string_char = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return html[start : index + 1]
        index += 1
    raise AdpBlobShapeError(f"unterminated {var_name!r} object literal")


def parse_adp_html(html: str) -> list[AdpEntry]:
    """Pure parse: raw page HTML -> ADP entries. No network access."""
    blob = _extract_json_object(html, _VUE_APP_DATA_VAR)
    data = json.loads(blob)

    try:
        seed = data["seed"]
        players = seed["players"]
        adp_sets = seed["adpSets"]
    except KeyError as exc:
        raise AdpBlobShapeError(f"missing expected key: {exc}") from exc

    if len(adp_sets) != 1:
        raise AdpBlobShapeError(
            "expected exactly one adpSets entry for this fixed-selection URL, "
            f"found {len(adp_sets)}: {list(adp_sets.keys())}"
        )
    rows = next(iter(adp_sets.values()))

    entries: list[AdpEntry] = []
    for row in rows:
        player = players.get(str(row["id"]))
        if player is None:
            # Row references a player id absent from this page's own player
            # dict — skip rather than error, same skip-not-error convention
            # as the nflverse rookie crosswalk.
            continue
        entries.append(
            AdpEntry(
                ds_player_id=row["id"],
                first_name=player["fn"],
                last_name=player["ln"],
                team=player.get("tm"),
                position=player.get("pos"),
                adp_pick=row["pick"],
                ds_rank=row.get("dsRank"),
                pos_adp=row.get("posAdp"),
                market_index=row.get("marketIndex"),
            )
        )
    return entries
