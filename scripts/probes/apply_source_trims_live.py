#!/usr/bin/env python3
"""LIVE: Apply source-only gain trims as ONE rollback unit.

This is intended for fixing Master headroom by trimming hot SOURCES, not buses.
All changes are grouped into one safety.safe_write_group entry so a single
fl_rollback_last_change restores all faders.

Defaults are based on the most recent drop-loop watch run in this session:
- Kick (1):        -1.6 -> -6.9 dB
- Bass low (21):    0.0 -> -5.7 dB
- Bass (22):        0.0 -> -5.7 dB
- Sub mix (48):     0.0 -> -6.0 dB

Override via env:
  FL_SOURCE_TRIMS="1:-6.9,21:-5.7,22:-5.7,48:-6.0"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("FLS_PILOT_TRANSPORT", "tcp")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import protocol, safety  # noqa: E402
from fls_pilot.connection import get_bridge  # noqa: E402


def _parse_trims(spec: str) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        a, b = part.split(":", 1)
        out.append((int(a.strip()), float(b.strip())))
    return out


def main() -> int:
    b = get_bridge()
    pong = b.call(protocol.CMD_PING, {})
    print(f"FL: {pong.get('fl_version')} | build={pong.get('build')}")

    spec = os.environ.get("FL_SOURCE_TRIMS", "1:-6.9,21:-5.7,22:-5.7,48:-6.0")
    trims = _parse_trims(spec)
    if not trims:
        print("[FAIL] No trims specified.")
        return 2

    writes = []
    for track, target_db in trims:
        writes.append(
            {
                "snap_scope": f"mixer_track:{track}",
                "command": protocol.CMD_MIXER_SET_VOLUME,
                "params": {"track": track, "value": float(target_db), "unit": "db"},
                "restore": (
                    lambda before, track=track: {
                        "command": protocol.CMD_MIXER_SET_VOLUME,
                        "params": {
                            "track": track,
                            "value": before["vol_norm"],
                            "unit": "normalized",
                        },
                    }
                ),
            }
        )

    res = safety.safe_write_group(
        b, tool="gain_stage_sources", scope="mixer:gain_stage_sources", writes=writes
    )
    if not res.get("ok"):
        print("[FAIL] write failed:", res)
        return 1

    print("[OK] Applied source trims as one rollback unit.")
    print("change_id:", res.get("change_id"))
    print("undo: fl_rollback_last_change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
