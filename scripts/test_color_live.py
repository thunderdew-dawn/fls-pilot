#!/usr/bin/env python3
"""LIVE color check -- talks to FL through the running daemon (TCP).

Run AFTER restarting FL with the updated controller (build marker color-v14):

    python scripts/test_color_live.py            # probe + color mixer track 1 red
    python scripts/test_color_live.py 3          # ... track 3 instead
    python scripts/test_color_live.py 3 4283782  # restore: set track 3 to this exact int

It (1) confirms mixer.setTrackColor / getTrackColor (and the channel pair)
actually exist on this FL build, and (2) sets a known color and reads it back so
we can see FL's native int + hex -- then leaves the track colored for a visual
check. The printed 'restore' int re-applies the original.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Force the TCP transport so we go through the daemon (which owns MIDI) rather
# than trying to grab the loopMIDI port ourselves.
os.environ.setdefault("FLSTUDIO_MCP_TRANSPORT", "tcp")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.connection import get_bridge  # noqa: E402


def _dir_names(bridge, module):
    """All public names of an FL module via api_probe 'dir' (paginated)."""
    names, start = [], 0
    while True:
        r = bridge.call("api_probe", {"op": "dir", "module": module, "start": start})
        names.extend(r.get("names", []))
        start = r.get("next_start")
        if not start:
            break
    return names


def main() -> int:
    track = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = get_bridge()

    pong = b.call("ping", {})
    print("FL: %s | build=%s (want color-v14)" % (pong.get("fl_version"), pong.get("build")))
    if pong.get("build") != "color-v14":
        print("  !! controller not reloaded yet -- restart FL after deploying the new controller.")

    # ---- restore mode -------------------------------------------------------
    if len(sys.argv) > 2:
        want = int(sys.argv[2])
        res = b.call("mixer_set_color", {"track": track, "color": want})
        print("restored track %d -> %s" % (track, res.get("color")))
        return 0

    # ---- 1. confirm the API actually exists --------------------------------
    mix = _dir_names(b, "mixer")
    chan = _dir_names(b, "channels")
    need_mix = [n for n in ("setTrackColor", "getTrackColor") if n in mix]
    need_chan = [n for n in ("setChannelColor", "getChannelColor") if n in chan]
    print("mixer color fns present:   %s" % need_mix)
    print("channel color fns present: %s" % need_chan)
    if len(need_mix) < 2:
        print("  !! mixer.setTrackColor/getTrackColor missing on this build -- stop.")
        return 1

    # ---- 2. read current, set RED, read back -------------------------------
    before = b.call("mixer_get_color", {"track": track}).get("color", {})
    print("\ntrack %d BEFORE: %s" % (track, before))

    after = b.call("mixer_set_color", {"track": track, "r": 255, "g": 0, "b": 0}).get("color", {})
    print("track %d set RED (255,0,0) -> readback: %s" % (track, after))
    print("  format check: hex should read #FF0000 if FL is 0xRRGGBB -> got %s" % after.get("hex"))

    print("\n>> LOOK AT FL: mixer track %d should now be RED." % track)
    print(">> restore original with:  python scripts/test_color_live.py %d %s"
          % (track, before.get("int", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
