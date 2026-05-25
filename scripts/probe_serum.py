#!/usr/bin/env python3
"""Serum 2 probe -- GENERATOR path (channel rack, slotIndex = -1). READ ONLY.

Generators are addressed as plugins.<fn>(.., channelIndex, slotIndex=-1). Our
existing plugin_get_params handler already calls getParamName(i, track, slot),
so passing track=<channel>, slot=-1 IS the generator form. The MCP tool blocks
slot<0, but this probe calls the controller command directly to test it.

Scans channels for a Serum generator, then pages its params 0..1024 (Serum has
many params -- this MUST paginate; one-shot would stall/drop).

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/probe_serum.py [channel]      # optional explicit channel
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol                       # noqa: E402
from fl_studio_mcp.connection import get_bridge           # noqa: E402

MATCH = ("serum",)
SCAN_CAP = 1024


def gen_page(bridge, channel, start):
    """plugin_get_params in GENERATOR form (slot = -1) via the existing handler."""
    return bridge.call(protocol.CMD_PLUGIN_GET_PARAMS,
                       {"track": channel, "slot": -1, "start": start}, timeout=15.0)


def main(argv) -> int:
    b = get_bridge()
    b.open()
    if not b.is_alive():
        print("Bridge not alive -- FL open? controller loaded? daemon up?")
        return 1

    if len(argv) > 1:
        channel = int(argv[1])
    else:
        st = b.call(protocol.CMD_GET_PROJECT_STATE)
        nch = int(st.get("channel_count", 0))
        print("channels: %d. Scanning generators (slot=-1) for Serum..." % nch)
        channel = None
        for c in range(nch):
            try:
                pg = gen_page(b, c, 0)
            except Exception as e:
                print("  ch %2d: slot=-1 ERRORED -> %s" % (c, e))
                continue
            pname = pg.get("plugin")
            try:
                cname = b.call(protocol.CMD_CHANNEL_GET, {"index": c}).get("name")
            except Exception:
                cname = "?"
            print("  ch %2d: generator=%r  total=%s  (channel=%r)"
                  % (c, pname, pg.get("total"), cname))
            if pname and any(m in pname.lower() for m in MATCH):
                channel = c
        if channel is None:
            print("\nNo Serum generator found (generator slot=-1 read tested above).")
            return 1

    print("\nSerum on channel %d" % channel)
    first = gen_page(b, channel, 0)
    total = first.get("total")
    print("getPluginName = %r" % first.get("plugin"))
    print("getParamCount (total) = %s   %s"
          % (total, "<- >=4000 VST-wrapper signature" if (total or 0) >= 4000 else "<- real count"))

    collected, start, pages, capped = [], 0, 0, False
    while start < SCAN_CAP:
        pg = gen_page(b, channel, start)
        collected.extend(pg.get("params", []))
        pages += 1
        nxt = pg.get("next_start")
        if nxt is None or nxt <= start:
            break
        start = nxt
    else:
        capped = True

    print("scanned to ~%d in %d page(s)%s -- real named params: %d"
          % (min(start, SCAN_CAP), pages, "  (HIT 1024 CAP -- more exist)" if capped else "", len(collected)))

    print("\nfirst 60 named params:")
    print("  idx | name                         | value  | value_string")
    print("  ----+------------------------------+--------+-------------")
    for p in collected[:60]:
        print("  %4d | %-28s | %.4f | %s" % (p["i"], (p["name"] or "")[:28], p.get("v", 0.0), repr(p.get("s"))))

    names_real = sum(1 for p in collected if (p["name"] or "").strip()
                     and not (p["name"] or "").lower().startswith("param"))
    strings_readable = sum(1 for p in collected if (p.get("s") or "").strip())
    print("\n--- summary ---")
    print("generator slot=-1 read: WORKED")
    print("names real (non-'Param N'): %d / %d" % (names_real, len(collected)))
    print("value_strings non-empty:    %d / %d" % (strings_readable, len(collected)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
