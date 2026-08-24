"""Wargame mock Sleeper server — a real HTTP server for autonomous draft tests.

Replicates the Sleeper endpoints the CLI consumes (league, draft, picks) plus
a write endpoint standing in for the human clicking in the UI:

    POST /v1/draft/<draft_id>/picks   {"roster_id": ..., "player_id": ...}

Bot teams auto-pick on a ticker thread whenever a bot persona is on the clock;
the draft pauses indefinitely when the wargame roster is on the clock, waiting
for a POST. Binds to localhost only. State lives in-process.

Usage:
    uv run python scripts/wargame_server.py \
        --seed scripts/wargame_seed.json --port 8321
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from sleeper_agent.wargame.state import (
    BotPersona,
    DraftConfig,
    DraftState,
    DraftVoided,
    NotYourTurn,
    PlayerUnavailable,
    SelectionMade,
    WargamePlayer,
)

STATE: DraftState | None = None
LOCK = threading.Lock()
HUMAN_ROSTER_ID = 5
PICK_CLOCK_SECONDS = 60.0
_on_clock_since: float | None = None
STARTED = False


def build_state(seed: dict) -> DraftState:
    config = DraftConfig(
        league_id=seed["league_id"],
        draft_id=seed["draft_id"],
        num_teams=seed["num_teams"],
        rounds=seed["rounds"],
        slot_to_roster_id={int(k): v for k, v in seed["slot_to_roster_id"].items()},
    )
    board = {p["player_id"]: WargamePlayer(**p) for p in seed["board"]}
    personas = {
        int(roster_id): BotPersona(**persona)
        for roster_id, persona in seed["personas"].items()
    }
    state = DraftState(config=config, board=board, personas=personas)
    state.seed_keepers(
        [
            (int(k["slot"]), int(k["cost_round"]), k["player_id"])
            for k in seed["keepers"]
        ]
    )
    return state


def _now() -> str:
    import datetime

    return datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S")


def pick_payload(pick) -> dict:
    first, _, *rest = pick.player_name.partition(" ")
    return {
        "draft_id": STATE.config.draft_id if STATE else "",
        "round": pick.round,
        "pick_no": pick.pick_no,
        "draft_slot": pick.draft_slot,
        "roster_id": pick.roster_id,
        "player_id": pick.player_id,
        "picked_by": f"u{pick.roster_id}",
        "is_keeper": pick.is_keeper,
        "metadata": {
            "first_name": first,
            "last_name": " ".join(rest),
            "position": pick.position,
        },
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # quieter logs
        pass

    def _json(self, code: int, body) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # http.server API
        with LOCK:
            assert STATE is not None
            if STATE.void_reason:
                status = "voided_pick_clock"
            elif not STARTED:
                status = "pre_draft"
            else:
                status = "drafting"
            if self.path == f"/v1/league/{STATE.config.league_id}":
                self._json(
                    200,
                    {
                        "league_id": STATE.config.league_id,
                        "name": "Wargame League",
                        "season": "2026",
                        "status": status,
                        "draft_id": STATE.config.draft_id,
                        "settings": {
                            "num_teams": STATE.config.num_teams,
                            "draft_rounds": STATE.config.rounds,
                            "waiver_budget": 100,
                            "waiver_type": 2,
                            "max_keepers": 2,
                            "best_ball": 1,
                            "trade_deadline": 11,
                            "playoff_week_start": 14,
                        },
                        "scoring_settings": {"rec": 1.0},
                        "roster_positions": [
                            "QB",
                            "RB",
                            "RB",
                            "WR",
                            "WR",
                            "TE",
                            "FLEX",
                            "FLEX",
                            "DEF",
                            "BN",
                            "BN",
                            "BN",
                            "BN",
                            "BN",
                            "BN",
                        ],
                    },
                )
            elif self.path == f"/v1/draft/{STATE.config.draft_id}":
                self._json(
                    200,
                    {
                        "draft_id": STATE.config.draft_id,
                        "league_id": STATE.config.league_id,
                        "season": "2026",
                        "type": "snake",
                        "status": status,
                        "start_time": None,
                        "settings": {
                            "rounds": STATE.config.rounds,
                            "teams": STATE.config.num_teams,
                            "slots_qb": 1,
                            "slots_rb": 2,
                            "slots_wr": 2,
                            "slots_te": 1,
                            "slots_flex": 2,
                            "slots_def": 1,
                        },
                        "slot_to_roster_id": {
                            str(k): v for k, v in STATE.config.slot_to_roster_id.items()
                        },
                    },
                )
            elif self.path == f"/v1/draft/{STATE.config.draft_id}/picks":
                visible = STATE.picks if STARTED else []
                self._json(
                    200,
                    [pick_payload(p) for p in sorted(visible, key=lambda p: p.pick_no)],
                )
            else:
                self._json(404, {"error": f"unknown path {self.path}"})

    def do_POST(self) -> None:  # http.server API
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        with LOCK:
            assert STATE is not None
            if self.path == f"/v1/draft/{STATE.config.draft_id}/start":
                global STARTED
                if STARTED:
                    self._json(200, {"ok": True, "note": "already started"})
                else:
                    STARTED = True
                    print("[draft] STARTED — keeper picks inserted", flush=True)
                self._json(200, {"ok": True})
                return
            expected_path = f"/v1/draft/{STATE.config.draft_id}/picks"
            if self.path != expected_path:
                self._json(404, {"error": f"unknown path {self.path}"})
                return
            if not STARTED:
                self._json(
                    409,
                    {
                        "error": "DraftNotStarted",
                        "detail": "draft has not been started",
                    },
                )
                return
            result = STATE.make_selection(
                int(body["roster_id"]), str(body["player_id"])
            )
            if isinstance(result, SelectionMade):
                _reset_human_clock()
                pick = result.pick
                print(
                    f"[pick] ts={_now()} #{pick.pick_no} (R{pick.round}) roster "
                    f"{pick.roster_id}: {pick.player_name} ({pick.position})",
                    flush=True,
                )
                self._json(200, {"ok": True, "pick": pick_payload(result.pick)})
            elif isinstance(result, DraftVoided):
                self._json(410, {"error": "DraftVoided", "detail": result.reason})
            else:
                # Rich rejection payloads so a stale-retrying client can tell
                # whether its earlier click actually landed.
                kind = type(result).__name__
                detail: dict[str, Any] = {
                    "next_pick_no": STATE.next_pick_no(),
                    "on_clock_roster_id": STATE.on_clock_roster_id(),
                }
                if isinstance(result, NotYourTurn):
                    detail["on_clock_roster_id"] = result.on_clock_roster_id
                if isinstance(result, PlayerUnavailable):
                    prior = next(
                        (p for p in STATE.picks if p.player_id == result.player_id),
                        None,
                    )
                    detail["player_id"] = result.player_id
                    if prior is not None:
                        detail["taken_by_pick_no"] = prior.pick_no
                        detail["taken_by_roster_id"] = prior.roster_id
                    else:
                        detail["reason"] = "not on the draft board"
                print(
                    f"[reject] ts={_now()} roster {body.get('roster_id')} -> player "
                    f"{body.get('player_id')}: {kind} {detail}",
                    flush=True,
                )
                self._json(409, {"error": kind, "detail": detail})


def _reset_human_clock() -> None:
    global _on_clock_since
    _on_clock_since = None


def ticker(poll_seconds: float, grace_seconds: float) -> None:
    """Advance bot picks when a bot is on the clock; enforce the human pick
    clock (after the grace period). Expiry voids the entire exercise."""
    import time

    global _on_clock_since
    started_at = time.monotonic()
    while True:
        time.sleep(poll_seconds)
        with LOCK:
            assert STATE is not None
            if STATE.void_reason is not None:
                return
            if not STARTED:
                continue
            on_clock = STATE.on_clock_roster_id()
            if on_clock is not None and on_clock in STATE.personas:
                STATE._run_bots()
                continue
            if (
                on_clock == HUMAN_ROSTER_ID
                and time.monotonic() - started_at > grace_seconds
            ):
                now = time.monotonic()
                if _on_clock_since is None:
                    _on_clock_since = now
                elif now - _on_clock_since > PICK_CLOCK_SECONDS:
                    reason = (
                        f"pick clock expired ({PICK_CLOCK_SECONDS:.0f}s) "
                        f"before roster {HUMAN_ROSTER_ID} selection at pick "
                        f"{STATE.next_pick_no()}"
                    )
                    print(f"HARD FAIL ts={_now()}: {reason}", flush=True)
                    STATE.void_reason = reason
                    return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8321)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument(
        "--grace-seconds",
        type=float,
        default=90.0,
        help=(
            "Cold-start allowance before the human pick clock arms (LLM "
            "drafter boot time). Set 0 for no mercy."
        ),
    )
    args = parser.parse_args()

    global STATE
    with open(args.seed) as fh:
        seed = json.load(fh)
    STATE = build_state(seed)
    print(
        f"wargame draft {STATE.config.draft_id}: {len(STATE.picks)} keepers seeded, "
        f"{len(STATE.available_players())} available; pick clock arms after "
        f"{args.grace_seconds:.0f}s grace; humans wait at roster_id={HUMAN_ROSTER_ID}",
        flush=True,
    )
    threading.Thread(
        target=ticker, args=(args.poll_seconds, args.grace_seconds), daemon=True
    ).start()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
