#!/usr/bin/env python3
"""Arrangement / playlist / patterns API probe.

Decides what 'arrangement' can realistically be in FL via the API: can we PLACE
pattern clips on the playlist, or only add markers + prep patterns?

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/probe_arrangement.py            # info: dir() + ppq (READ ONLY)
    python scripts/probe_arrangement.py markers    # add TEST_INTRO@bar1, TEST_DROP@bar16
    python scripts/probe_arrangement.py clean       # undo (remove the test markers)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol                       # noqa: E402
from fl_studio_mcp.connection import get_bridge           # noqa: E402

# keywords that would indicate real clip-placement on the playlist
PLACE_HINTS = ("clip", "addclip", "placeclip", "block", "addpattern", "insert", "place")


def probe(b, op, **kw):
    return b.call(protocol.CMD_API_PROBE, dict(op=op, **kw), timeout=15.0)


def dir_of(b, module):
    names, start = [], 0
    while True:
        r = probe(b, "dir", module=module, start=start)
        names.extend(r.get("names", []))
        nxt = r.get("next_start")
        if nxt is None or int(nxt) <= start:
            break
        start = int(nxt)
    return names


def main(argv) -> int:
    b = get_bridge()
    b.open()
    if not b.is_alive():
        print("Bridge not alive -- FL open? controller (slice-arrange-v8) loaded? daemon up?")
        return 1

    mode = argv[1] if len(argv) > 1 else "info"

    if mode == "info":
        for mod in ("playlist", "arrangement", "patterns", "general", "transport"):
            names = dir_of(b, mod)
            print("\n=== %s (%d) ===" % (mod, len(names)))
            print("  " + ", ".join(names))
        # make-or-break scan on playlist names
        pl = [n.lower() for n in dir_of(b, "playlist")]
        hits = [n for n in pl if any(h in n for h in PLACE_HINTS)]
        print("\n--- playlist clip-placement candidates: %s" % (hits or "NONE"))
        info = probe(b, "ppq")
        print("ppq/pattern info: %s" % info)
        return 0

    if mode == "markers":
        info = probe(b, "ppq")
        ppq = info.get("ppq")
        if not isinstance(ppq, (int, float)):
            print("could not read ppq: %s -- using 96 as a guess" % info)
            ppq = 96
        bar = int(4 * ppq)                       # 4/4 bar in ticks
        r1 = probe(b, "marker_add", time=0, name="TEST_INTRO")          # bar 1
        r16 = probe(b, "marker_add", time=15 * bar, name="TEST_DROP")   # bar 16
        print("ppq=%s  bar_ticks=%s" % (ppq, bar))
        print("add TEST_INTRO @bar1 (t=0):    %s" % r1)
        print("add TEST_DROP  @bar16 (t=%d): %s" % (15 * bar, r16))
        print("\n-> Check FL's playlist/arrangement for TEST_INTRO + TEST_DROP markers.")
        print("   Then run:  python scripts/probe_arrangement.py clean")
        return 0

    if mode == "clean":
        print("undoing (removing test markers via undoUp x3)...")
        for _ in range(3):
            print("  ", probe(b, "undo"))
        print("-> check the markers are gone; if not, Ctrl+Z in FL.")
        return 0

    print("unknown mode %r" % mode)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
