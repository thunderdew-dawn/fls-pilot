#!/usr/bin/env python3
"""Phase 1a read-surface tester (read-only).

Exercises the new project / mixer / channel state-read commands added in
Phase 1. Read-only -- changes nothing in FL Studio.

    python scripts/test_phase1a.py

Prerequisites: FL Studio open, FLStudioMCP controller loaded, loopMIDI RX/TX
ports up. Run with NO other process holding the TX port (stop the daemon
first), since this opens the bridge directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from a checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.connection import (  # noqa: E402
    FLBridge,
    FLNotRunning,
    FLPortMissing,
    FLTimeout,
    FLCommandFailed,
    fetch_all_pages,
)
from fl_studio_mcp.protocol import (  # noqa: E402
    CMD_GET_PROJECT_STATE,
    CMD_MIXER_LIST_TRACKS,
    CMD_MIXER_GET_TRACK,
    CMD_CHANNEL_LIST,
    CMD_CHANNEL_GET,
)


def step(label, fn):
    sys.stdout.write("  %-44s " % label)
    sys.stdout.flush()
    try:
        result = fn()
    except (FLNotRunning, FLPortMissing, FLTimeout, FLCommandFailed) as e:
        print("FAIL\n      %s" % e)
        return None, False
    print("ok")
    if result is not None:
        print("      %s" % (result,))
    return result, True


def main() -> int:
    bridge = FLBridge()
    bridge.open()
    bridge.wait_for_heartbeat()
    print("Heartbeat age:", bridge.heartbeat_age())
    print()

    all_ok = True

    _, ok = step("get_project_state", lambda: bridge.call(CMD_GET_PROJECT_STATE))
    all_ok &= ok

    _, ok = step("mixer_list_tracks (ALL pages)",
                 lambda: fetch_all_pages(bridge, CMD_MIXER_LIST_TRACKS, "tracks"))
    all_ok &= ok

    for t in (0, 1, 6):
        _, ok = step("mixer_get_track index=%d" % t,
                     lambda t=t: bridge.call(CMD_MIXER_GET_TRACK, {"index": t}))
        all_ok &= ok

    _, ok = step("channel_list (ALL pages)",
                 lambda: fetch_all_pages(bridge, CMD_CHANNEL_LIST, "channels"))
    all_ok &= ok

    _, ok = step("channel_get index=0",
                 lambda: bridge.call(CMD_CHANNEL_GET, {"index": 0}))
    all_ok &= ok

    print()
    print("All read checks passed." if all_ok else "Some checks failed.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
