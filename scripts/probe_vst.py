#!/usr/bin/env python3
"""3rd-party VST probe (READ ONLY) -- does FL's wrapper expose names + units?

Auto-detects a FabFilter / Pro-C VST on any mixer track (by name), reports the
param count (4240 = VST-wrapper signature vs a real count), then pages indices
0..1024 via the existing plugin_get_params (which skips empty-name slots and
scan-caps 150/page, so the controller never stalls) and prints the filtered
real params. No writes, no setParamValue -- pure read.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/probe_vst.py [track] [slot]      # optional explicit target
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol                       # noqa: E402
from fl_studio_mcp.connection import get_bridge           # noqa: E402

MATCH = ("fabfilter", "pro-c", "pro c", "pro-q", "pro-l")
SCAN_CAP = 1024

# Comp params we care about for calibration feasibility (report these explicitly)
KEY = ("threshold", "ratio", "attack", "release", "knee", "range", "mix",
       "output", "gain", "makeup")


def find_plugin(bridge):
    st = bridge.call(protocol.CMD_GET_PROJECT_STATE)
    ntr = int(st.get("mixer_track_count", 30))
    for t in range(ntr + 1):
        try:
            sl = bridge.call(protocol.CMD_PLUGIN_LIST, {"track": t})
        except Exception:
            continue
        for s in sl.get("slots", []):
            if any(m in (s.get("name") or "").lower() for m in MATCH):
                return t, s["slot"], s["name"]
    return None, None, None


def main(argv) -> int:
    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive -- FL open? controller loaded? daemon up (tcp)?")
        return 1

    if len(argv) > 2:
        track, slot = int(argv[1]), int(argv[2])
        name = next((s["name"] for s in bridge.call(protocol.CMD_PLUGIN_LIST, {"track": track}).get("slots", [])
                     if s["slot"] == slot), "?")
    else:
        track, slot, name = find_plugin(bridge)
    if track is None:
        print("No FabFilter/Pro-* VST found on any mixer track. Load it, or run "
              "with explicit:  python scripts/probe_vst.py <track> <slot>")
        return 1
    print("Found %r at track %d slot %d" % (name, track, slot))

    first = bridge.call(protocol.CMD_PLUGIN_GET_PARAMS,
                        {"track": track, "slot": slot, "start": 0}, timeout=15.0)
    total = first.get("total")
    print("getParamCount (total) = %s   %s"
          % (total, "<- 4240 = VST-wrapper signature" if (total or 0) >= 4000
             else "<- looks like a REAL count"))

    collected, start, pages, capped = [], 0, 0, False
    while start < SCAN_CAP:
        page = bridge.call(protocol.CMD_PLUGIN_GET_PARAMS,
                           {"track": track, "slot": slot, "start": start}, timeout=15.0)
        collected.extend(page.get("params", []))
        pages += 1
        nxt = page.get("next_start")
        if nxt is None or nxt <= start:
            break
        start = nxt
    else:
        capped = True

    print("\nscanned to index ~%d in %d page(s)%s"
          % (min(start, SCAN_CAP), pages, "  (HIT 1024 CAP -- more may exist)" if capped else ""))
    print("real (non-empty-name) params found: %d\n" % len(collected))
    print("  idx | name                          | value  | value_string")
    print("  ----+-------------------------------+--------+--------------")
    for p in collected:
        print("  %4d | %-29s | %.4f | %s"
              % (p["i"], (p["name"] or "")[:29], p.get("v", 0.0), repr(p.get("s"))))

    # quick automatic read of the two make-or-break questions
    names_real = sum(1 for p in collected if (p["name"] or "").strip()
                     and not (p["name"] or "").lower().startswith("param"))
    strings_readable = sum(1 for p in collected if (p.get("s") or "").strip())
    key_hits = [p for p in collected if any(k in (p["name"] or "").lower() for k in KEY)]
    print("\n--- auto-summary ---")
    print("names look REAL (non-'Param N'): %d / %d" % (names_real, len(collected)))
    print("value_strings non-empty:         %d / %d" % (strings_readable, len(collected)))
    print("key comp-ish params seen:        %s"
          % [(p["i"], p["name"], p.get("s")) for p in key_hits][:20])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
