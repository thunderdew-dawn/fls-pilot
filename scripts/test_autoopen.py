#!/usr/bin/env python3
"""Fresh-session note-bridge test: does auto-open work, and is arm the floor?

Writes one note via the bridge with ZERO manual setup. Expect:
  - piano_roll_ensured.ok = True  (controller auto-opened the piano roll)
  - if NOT armed this session -> note won't appear, 'setup' note explains the
    one manual step (run MCP Apply once).

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/test_autoopen.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.connection import get_bridge           # noqa: E402

_PITCH = int(sys.argv[1]) if len(sys.argv) > 1 else 60
NOTE = [{"pitch": _PITCH, "time_bars": 0.0, "length_bars": 1.0, "velocity": 0.787}]


def main() -> int:
    b = get_bridge()
    b.open()
    if not b.is_alive():
        print("Bridge not alive -- daemon restarted? FL open?")
        return 1
    print("writing one note (C5) with zero manual setup...\n")
    r = b.apply_notes(NOTE, "replace")
    print(json.dumps(r, indent=2))
    print("\nWatch FL: did C5 appear in the piano roll?")
    print("  piano_roll_ensured.ok == True  -> auto-open worked (step 1 gone)")
    print("  note appeared                  -> fully automatic (was already armed)")
    print("  note did NOT appear            -> arm MCP Apply once = the one floor step")
    return 0


if __name__ == "__main__":
    sys.exit(main())
