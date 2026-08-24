"""Publish a wargame pick recommendation into the single-slot IPC contract.

The LLM drafter's job is the DECISION; this script owns the bookkeeping that
the drafter repeatedly botched under clock pressure (writing recs.jsonl but
not current_rec.json, stale overwrites, hallucinated timestamps). Calling it
atomically does: write /tmp/wargame/current_rec.json (the only file the
Human role reads) + append one audit line to recs.jsonl.

Usage:
    uv run --project cli python scripts/wargame_publish_rec.py \\
        --pick 17 --player 5850 --name "Josh Jacobs" --position RB \\
        --rationale "tier-1 RB, RB 0/2 need"
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

REC_SLOT = Path("/tmp/wargame/current_rec.json")
AUDIT_LOG = Path("/tmp/wargame/recs.jsonl")


def publish(
    pick_no: int,
    player_id: str,
    name: str,
    position: str,
    rationale: str,
) -> dict:
    record = {
        "ts": datetime.datetime.now(datetime.UTC).isoformat(),
        "on_clock_pick_no": pick_no,
        "player_id": player_id,
        "player_name": name,
        "position": position,
        "rationale": rationale,
    }
    REC_SLOT.parent.mkdir(parents=True, exist_ok=True)
    REC_SLOT.write_text(json.dumps(record))
    with AUDIT_LOG.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pick", type=int, required=True)
    parser.add_argument("--player", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--position", required=True)
    parser.add_argument("--rationale", required=True)
    args = parser.parse_args()
    record = publish(args.pick, args.player, args.name, args.position, args.rationale)
    print(
        f"published rec for pick {record['on_clock_pick_no']}: {record['player_name']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
