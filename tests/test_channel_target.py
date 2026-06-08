#!/usr/bin/env python3
"""Slice 2 make-or-break: does selecting a channel retarget the note bridge?

In ONE pattern, write a mid chord to channel A and a low bass to channel B.
If channel A ends with the chord and channel B with the bass (not both piled
into one channel), channel targeting works -> multi-instrument arrangement is
unlocked.

Prereq: note-bridge set up (Piano roll open + MCP_Apply run once this session).
Pick two MELODIC/synth channels (not audio-sample channels).

    set FLS_PILOT_TRANSPORT=tcp
    python scripts/test_channel_target.py [chA] [chB]    # default 10 4
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import protocol  # noqa: E402
from fls_pilot.connection import fetch_all_pages, get_bridge  # noqa: E402

CH_A = int(sys.argv[1]) if len(sys.argv) > 1 else 10  # e.g. Serum
CH_B = int(sys.argv[2]) if len(sys.argv) > 2 else 4  # e.g. a FLEX
CHORD = [
    {"pitch": p, "time_bars": 0.0, "length_bars": 1.0, "velocity": 0.787} for p in (60, 64, 67)
]  # C-E-G (mid)
BASS = [
    {"pitch": p, "time_bars": 0.0, "length_bars": 1.0, "velocity": 0.787} for p in (36, 43)
]  # C2-G2 (low)
SETTLE = 1.5


def main() -> int:
    b = get_bridge()
    b.open()
    if not b.is_alive():
        print("Bridge not alive -- FL open? controller (slice-chan-v11) loaded? daemon up?")
        return 1

    chans = fetch_all_pages(b, protocol.CMD_CHANNEL_LIST, "channels")
    print("channels:")
    for c in chans.get("channels", []):
        mark = "  <-- A" if c["i"] == CH_A else ("  <-- B" if c["i"] == CH_B else "")
        print("  %2d  %s%s" % (c["i"], c["name"], mark))

    print("\nnew pattern CHANTEST")
    p = b.call(protocol.CMD_ARRANGE_NEW_PATTERN, {"name": "CHANTEST"})
    print("   ", p)

    print("\nselect ch %d (A) -> write mid chord C-E-G" % CH_A)
    print("   ", b.call(protocol.CMD_CHANNEL_SELECT, {"channel": CH_A}))
    time.sleep(0.4)
    print("    fill:", b.apply_notes(CHORD, "replace", channel=CH_A))
    time.sleep(SETTLE)

    print("\nselect ch %d (B) -> write low bass C2-G2" % CH_B)
    print("   ", b.call(protocol.CMD_CHANNEL_SELECT, {"channel": CH_B}))
    time.sleep(0.4)
    print("    fill:", b.apply_notes(BASS, "replace", channel=CH_B))
    time.sleep(SETTLE)

    print("\nWATCH FL (pattern CHANTEST) + report:")
    print("  - channel %d (A) piano roll: C-E-G (mid chord)?" % CH_A)
    print("  - channel %d (B) piano roll: C2-G2 (low bass)?" % CH_B)
    print("    -> if each channel has its OWN notes: channel targeting WORKS (PASS)")
    print("    -> if both notes landed in ONE channel: select doesn't retarget (FAIL)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
