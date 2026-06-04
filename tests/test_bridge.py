#!/usr/bin/env python3
"""Standalone bridge tester.

Run this BEFORE wiring up the MCP Client to confirm the file-queue bridge works:

    python scripts/test_bridge.py

Prerequisites:
    1. FL Studio is open.
    2. The FLStudioMCP controller script is installed and selected.

The script will:
    - Ping the controller
    - Read the current tempo
    - Bump tempo by +5 BPM, then put it back
    - Play for 1 second, then stop
    - Report any failures

Exits non-zero if any step fails.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow running from a checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.connection import (  # noqa: E402
    FLBridge,
    FLCommandFailed,
    FLNotRunning,
    FLPortMissing,
    FLTimeout,
)
from fl_studio_mcp.protocol import (  # noqa: E402
    CMD_GET_PLAY_STATE,
    CMD_GET_SONG_POS,
    CMD_GET_TEMPO,
    CMD_PING,
    CMD_PLAY,
    CMD_RECORD,
    CMD_SET_SONG_POS,
    CMD_SET_TEMPO,
    CMD_STOP,
    CMD_TOGGLE_PLAY,
)


def step(label: str, fn):
    sys.stdout.write(f"  {label:.<48} ")
    sys.stdout.flush()
    try:
        result = fn()
    except (FLNotRunning, FLPortMissing, FLTimeout, FLCommandFailed) as e:
        print(f"FAIL\n      {e}")
        return None, False
    print("ok")
    if result is not None:
        print(f"      {result}")
    return result, True


def main() -> int:
    from fl_studio_mcp.protocol import port_from_fl_name, port_to_fl_name

    bridge = FLBridge()
    print(f"Port to FL:   {port_to_fl_name()}")
    print(f"Port from FL: {port_from_fl_name()}")
    bridge.open()
    bridge.wait_for_heartbeat()
    print(f"Heartbeat age: {bridge.heartbeat_age()}")
    print()

    all_ok = True

    info, ok = step("ping", lambda: bridge.call(CMD_PING))
    all_ok &= ok
    if not ok:
        return 1

    tempo, ok = step("get_tempo", lambda: bridge.call(CMD_GET_TEMPO))
    all_ok &= ok
    if not ok:
        return 1
    original_bpm = tempo["bpm"]

    _, ok = step(
        f"set_tempo to {original_bpm + 5:.1f}",
        lambda: bridge.call(CMD_SET_TEMPO, {"bpm": original_bpm + 5}),
    )
    all_ok &= ok

    time.sleep(0.2)

    _, ok = step(
        f"restore tempo to {original_bpm:.1f}",
        lambda: bridge.call(CMD_SET_TEMPO, {"bpm": original_bpm}),
    )
    all_ok &= ok

    _, ok = step("play", lambda: bridge.call(CMD_PLAY))
    all_ok &= ok

    time.sleep(1.0)

    _, ok = step("get_play_state (mid-play)", lambda: bridge.call(CMD_GET_PLAY_STATE))
    all_ok &= ok

    _, ok = step("stop", lambda: bridge.call(CMD_STOP))
    all_ok &= ok

    # ----- extended: remaining Phase-0 tools -----
    print()
    print("Extended checks (toggle_play / record / song position):")

    tg1, ok = step("toggle_play (1st)", lambda: bridge.call(CMD_TOGGLE_PLAY))
    all_ok &= ok
    time.sleep(0.3)
    tg2, ok = step("toggle_play (2nd)", lambda: bridge.call(CMD_TOGGLE_PLAY))
    all_ok &= ok
    if tg1 is not None and tg2 is not None:
        flipped = bool(tg1.get("playing")) != bool(tg2.get("playing"))
        print(
            "      play state {} -> {} (flipped={})".format(
                tg1.get("playing"), tg2.get("playing"), flipped
            )
        )

    _, ok = step("get_song_position", lambda: bridge.call(CMD_GET_SONG_POS))
    all_ok &= ok

    _, ok = step(
        "set_song_position beats=4.0", lambda: bridge.call(CMD_SET_SONG_POS, {"beats": 4.0})
    )
    all_ok &= ok
    pos, ok = step("get_song_position (after move)", lambda: bridge.call(CMD_GET_SONG_POS))
    all_ok &= ok
    if pos is not None:
        print(f"      position_beats now: {pos.get('position_beats')}")

    # record LAST: transport.record() can pop FL's modal "What would you like
    # to record?" dialog, which blocks the script thread and freezes the
    # bridge. Run it after everything else so the other checks always finish.
    rec1, ok = step("record (1st -> arm)", lambda: bridge.call(CMD_RECORD))
    all_ok &= ok
    if rec1 is not None:
        print(f"      after 1st record: {rec1}")
    rec2, ok = step("record (2nd -> disarm)", lambda: bridge.call(CMD_RECORD))
    all_ok &= ok
    if rec2 is not None:
        print(f"      after 2nd record: {rec2}")

    # ----- cleanup: never leave playback running or record armed -----
    try:
        bridge.call(CMD_STOP)
        state = bridge.call(CMD_GET_PLAY_STATE)
        if state.get("recording"):
            bridge.call(CMD_RECORD)
            state = bridge.call(CMD_GET_PLAY_STATE)
        bridge.call(CMD_SET_SONG_POS, {"beats": 0.0})
        print(f"  cleanup (stopped / disarmed / pos reset): {state}")
    except Exception as e:  # pragma: no cover
        print(f"  cleanup warning: {e}")

    print()
    print("All checks passed." if all_ok else "Some checks failed.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
