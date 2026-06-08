#!/usr/bin/env python3
"""Arrangement Slice 1 -- prove the MULTI-pattern create+fill+mark mechanic.

Make-or-break: does the note bridge write into the SELECTED pattern (so each
section gets its OWN notes), or always dump into one pattern?

Flow:
  new INTRO  -> fill C major (C E G)
  new VERSE  -> fill A minor (A C E)
  clone VERSE -> VERSE2 (should copy the A minor notes)
  marker bar1 "INTRO", marker bar5 "VERSE"

CREATES patterns/markers -- SAVE your project or use a throwaway one first.
Also: open the Piano roll and run 'MCP_Apply' once from its Scripting menu so
Ctrl+Alt+Y targets the note bridge.

    set FLS_PILOT_TRANSPORT=tcp
    python scripts/test_arrange_mechanic.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import protocol  # noqa: E402
from fls_pilot.connection import get_bridge  # noqa: E402

C_MAJOR = [
    {"pitch": p, "time_bars": 0.0, "length_bars": 1.0, "velocity": 0.787} for p in (60, 64, 67)
]  # C E G
A_MINOR = [
    {"pitch": p, "time_bars": 0.0, "length_bars": 1.0, "velocity": 0.787} for p in (57, 60, 64)
]  # A C E
SETTLE = 1.5  # let the note bridge finish before next jump


def main() -> int:
    b = get_bridge()
    b.open()
    if not b.is_alive():
        print("Bridge not alive -- FL open? controller (slice-arrange-v10) loaded? daemon up?")
        return 1

    print("[1] new INTRO + fill C major")
    p1 = b.call(protocol.CMD_ARRANGE_NEW_PATTERN, {"name": "ARRTEST_INTRO"})
    print("   ", p1)
    fill1 = b.apply_notes(C_MAJOR, "replace")
    print("    fill:", fill1)
    time.sleep(SETTLE)

    print("\n[2] new VERSE + fill A minor")
    p2 = b.call(protocol.CMD_ARRANGE_NEW_PATTERN, {"name": "ARRTEST_VERSE"})
    print("   ", p2)
    fill2 = b.apply_notes(A_MINOR, "replace")
    print("    fill:", fill2)
    time.sleep(SETTLE)

    print("\n[3] clone VERSE -> VERSE2 (should copy A minor)")
    p3 = b.call(
        protocol.CMD_ARRANGE_CLONE_PATTERN, {"src": p2.get("index"), "new_name": "ARRTEST_VERSE2"}
    )
    print("   ", p3)

    print("\n[4] markers")
    m1 = b.call(protocol.CMD_ARRANGE_ADD_MARKER, {"bar": 1, "name": "ARRTEST_INTRO"})
    m2 = b.call(protocol.CMD_ARRANGE_ADD_MARKER, {"bar": 5, "name": "ARRTEST_VERSE"})
    print("   ", m1)
    print("   ", m2)

    print("\n--- result ---")
    print(
        "patterns created: INTRO={} VERSE={} VERSE2={}".format(
            p1.get("index"), p2.get("index"), p3.get("new_index")
        )
    )
    print(f"markers: {m1.get('ok') and 'INTRO'} @bar1, {m2.get('ok') and 'VERSE'} @bar5")
    print("\nWATCH FL + report:")
    print("  - 3 distinct named patterns (ARRTEST_INTRO / VERSE / VERSE2)?")
    print("  - INTRO has C-E-G, VERSE has A-C-E (DIFFERENT notes per pattern)?")
    print("    -> if yes: note bridge targets the SELECTED pattern (make-or-break PASS)")
    print("    -> if both same / all in one pattern: bridge ignores selection (FAIL)")
    print("  - VERSE2 copied VERSE's A-C-E notes?")
    print("  - markers INTRO@bar1 + VERSE@bar5 on the timeline?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
