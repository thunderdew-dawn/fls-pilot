#!/usr/bin/env python3
"""Serum preset-navigation probe -- can FL step/read Serum's presets?

Serum is a channel-rack generator (channel 10, slot -1). Steps the preset a few
times reading the name after each, then steps back to RESTORE the original.
Decides: can we do preset-recall ("vintage bass" -> load a real preset), or is
Serum's library walled off from FL?

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/probe_serum_presets.py [channel]    # default 10
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol                       # noqa: E402
from fl_studio_mcp.connection import get_bridge           # noqa: E402

CH = int(sys.argv[1]) if len(sys.argv) > 1 else 10
SLOT = -1
STEPS = 5
_NAME_KEYS = ("plugin_name", "name_f3", "name_f6")


def call(b, op):
    return b.call(protocol.CMD_PLUGIN_PRESET, {"track": CH, "slot": SLOT, "op": op}, timeout=20.0)


def names(d):
    return {k: (d.get(k) or "").strip() if isinstance(d.get(k), str) else d.get(k) for k in _NAME_KEYS}


def main() -> int:
    b = get_bridge()
    b.open()
    if not b.is_alive():
        print("Bridge not alive -- FL open? controller (slice-preset-v7) loaded? daemon up?")
        return 1

    start = call(b, "info")
    print("preset_count   = %s" % start.get("preset_count"))
    if start.get("count_error"):
        print("count_error    = %s" % start.get("count_error"))
    if start.get("nav_error"):
        print("nav_error      = %s" % start.get("nav_error"))
    start_names = names(start)
    print("start names    = %s" % start_names)

    print("\nstep | nextPreset -> current names")
    changed_any = False
    for i in range(1, STEPS + 1):
        d = call(b, "next")
        nm = names(d)
        if d.get("nav_error"):
            print("  %d | NAV ERROR: %s" % (i, d.get("nav_error")))
            break
        print("  %d | %s" % (i, nm))
        if nm != start_names:
            changed_any = True
        time.sleep(0.25)

    print("\nrestoring via prevPreset x%d ..." % STEPS)
    last = None
    for _ in range(STEPS):
        last = call(b, "prev")
        time.sleep(0.25)
    end_names = names(last) if last else None
    print("after restore  = %s" % end_names)
    restored = end_names == start_names
    print("restored to start preset? %s" % restored)

    print("\n--- verdict ---")
    cnt = start.get("preset_count")
    print("preset_count real? %s" % ("YES (%s)" % cnt if isinstance(cnt, int) and cnt > 1 else "NO / walled off (%s)" % cnt))
    print("preset name CHANGED on step? %s" % ("YES" if changed_any else "NO (no change / not readable)"))
    if not restored:
        print("WARNING: original preset NOT restored -- check Serum (prev may not exactly reverse).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
