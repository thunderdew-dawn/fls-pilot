#!/usr/bin/env python3
"""Phase 1b plugin-parameter tester.

Targets a REAL mixer track that already has plugins loaded (we never load
new plugin instances -- the FL API can't). Default target is mixer track 2
(the user's VOX track: Fruity Parametric EQ 2 + Fruity Reeverb 2).

What it does:
  1. plugin_list(track)            -> discover which effect SLOTS are filled
                                      (FL slots are 0-9; we don't assume).
  2. plugin_get_params(track,slot) -> dump EVERY param (paginated) for each
                                      filled slot. Prints `total` so you can
                                      see real-count vs the 4240-slot VST
                                      wrapper behaviour, and every param NAME
                                      so you can judge real-names vs "Param N".
  3. plugin_set_param on the EQ    -> read current, nudge, read back, then
                                      ROLL BACK to the original value.

    python scripts/test_phase1b.py            # track 2
    python scripts/test_phase1b.py 4          # some other track

Prereqs: FL open, FLStudioMCP controller loaded (with the plugin handlers),
loopMIDI RX/TX up. Honours FLSTUDIO_MCP_TRANSPORT: set it to "tcp" to route
through a running daemon (no need to stop it); leave it unset for a direct
FLBridge (needs the TX port free -- stop the daemon first).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.connection import (  # noqa: E402
    get_bridge,
    FLNotRunning,
    FLPortMissing,
    FLTimeout,
    FLCommandFailed,
    fetch_all_pages,
)
from fl_studio_mcp.protocol import (  # noqa: E402
    CMD_PLUGIN_LIST,
    CMD_PLUGIN_GET_PARAMS,
    CMD_PLUGIN_SET_PARAM,
)


def dump_slot(bridge, track, slot):
    """Fetch + print every param for one plugin slot. Returns the param list."""
    # First page also tells us the plugin name + raw total.
    first = bridge.call(CMD_PLUGIN_GET_PARAMS, {"track": track, "slot": slot, "start": 0})
    name = first.get("plugin")
    total = first.get("total")
    print("\n--- track %d slot %d : %r ---" % (track, slot, name))
    print("    reported param total = %s" % total)

    full = fetch_all_pages(
        bridge, CMD_PLUGIN_GET_PARAMS, "params", {"track": track, "slot": slot}
    )
    params = full["params"]
    print("    named params returned = %d" % len(params))
    for prm in params:
        sval = prm.get("s") or ""
        sval = ("  [%s]" % sval) if sval else ""
        print("      [%4d] %-30s = %s%s" % (prm["i"], prm["name"], prm["v"], sval))
    return params


def main(argv) -> int:
    track = int(argv[1]) if len(argv) > 1 else 2

    bridge = get_bridge()
    bridge.open()
    if hasattr(bridge, "wait_for_heartbeat"):
        bridge.wait_for_heartbeat()
    if not bridge.is_alive():
        print("Bridge not alive -- check FL open, controller loaded, and "
              "(if FLSTUDIO_MCP_TRANSPORT=tcp) the daemon is running.")
        return 1
    print("Heartbeat age:", bridge.heartbeat_age())

    # 1. discover filled slots ------------------------------------------------
    try:
        listing = bridge.call(CMD_PLUGIN_LIST, {"track": track})
    except (FLNotRunning, FLPortMissing, FLTimeout, FLCommandFailed) as e:
        print("plugin_list FAILED: %s" % e)
        return 1
    slots = listing.get("slots", [])
    print("\nplugin_list(track=%d): %d filled slot(s)" % (track, len(slots)))
    for s in slots:
        print("    slot %d -> %r" % (s["slot"], s["name"]))
    if not slots:
        print("No plugins on track %d -- nothing to dump." % track)
        return 1

    # 2. dump every param for each filled slot --------------------------------
    dumped = {}
    for s in slots:
        try:
            dumped[s["slot"]] = dump_slot(bridge, track, s["slot"])
        except (FLNotRunning, FLPortMissing, FLTimeout, FLCommandFailed) as e:
            print("    dump FAILED for slot %d: %s" % (s["slot"], e))

    # 3. set -> readback -> rollback on an EQ slot ----------------------------
    eq_slots = [s["slot"] for s in slots if "eq" in (s["name"] or "").lower()]
    target_slot = eq_slots[0] if eq_slots else slots[0]["slot"]
    params = dumped.get(target_slot) or []
    if not params:
        print("\nNo named params on slot %d -- skipping set/rollback." % target_slot)
        return 0

    prm = params[0]                      # first named param is fine for a round-trip
    idx = prm["i"]
    original = prm["v"]
    # nudge within [0,1] -- plugin params are normalised on the FL API.
    target = round(original + 0.1, 4) if original <= 0.5 else round(original - 0.1, 4)
    target = max(0.0, min(1.0, target))

    print("\n=== set/readback/rollback : slot %d param [%d] %r ==="
          % (target_slot, idx, prm["name"]))
    print("    original value      = %s" % original)

    setres = bridge.call(CMD_PLUGIN_SET_PARAM,
                         {"track": track, "slot": target_slot, "param": idx, "value": target})
    print("    after set(%s)        = %s  [%s]" % (target, setres["v"], setres.get("s") or ""))

    moved = abs(setres["v"] - target) < 0.02
    print("    set landed on target = %s" % ("YES" if moved else "NO (param may be stepped/locked)"))

    rb = bridge.call(CMD_PLUGIN_SET_PARAM,
                    {"track": track, "slot": target_slot, "param": idx, "value": original})
    print("    after rollback       = %s  [%s]" % (rb["v"], rb.get("s") or ""))
    restored = abs(rb["v"] - original) < 0.02
    print("    rolled back cleanly  = %s" % ("YES" if restored else "NO"))

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
