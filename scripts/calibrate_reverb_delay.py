#!/usr/bin/env python3
"""Slice C-1: calibrate Fruity Reeverb 2 + Fruity Delay (norm <-> real units).

Auto-detects which slot holds the reverb and which holds the delay on the
target track (matches by plugin name -- no hardcoded slots), dumps each, then
sweeps the musically-useful params across normalized 0.0..1.0 (21 steps),
reads back FL's display string, parses it, and PRINTS the raw curves.

Pure data collection -- NO conversion functions, NO intents (that's C-2).

Safety: every swept param is snapshotted via the safety layer FIRST and
restored in a finally block, so both plugins are left exactly as the user set
them, even if the run errors.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/calibrate_reverb_delay.py [track]      # default track 2
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety              # noqa: E402
from fl_studio_mcp.connection import fetch_all_pages, get_bridge  # noqa: E402

STEPS = [round(i * 0.05, 4) for i in range(21)]
_NUM = re.compile(r"[-+]?\d*\.?\d+")


def _num(s):
    m = _NUM.search(str(s or ""))
    return float(m.group()) if m else None


def p_hz(s):
    n = _num(s)
    if n is None:
        return None
    t = str(s).lower()
    if "khz" in t:
        return n * 1000.0
    if "hz" in t:
        return n
    return None


def p_pct(s):
    return _num(s) if "%" in str(s) else None


def p_sec(s):
    return _num(s) if "sec" in str(s).lower() else None


def p_ms(s):
    t = str(s).lower()
    return _num(t) if ("ms" in t and "sec" not in t) else None


def p_num(s):
    return _num(s)


def p_raw(_s):
    return None                       # discrete / musical -> show raw only


# (param name, parser, unit label). Names resolved against the live dump.
REVERB_PARAMS = [
    ("Decay time", p_sec, "sec"),
    ("Wet level", p_pct, "%"),
    ("Room size", p_num, "num"),
    ("High cut", p_hz, "Hz"),
    ("Low cut", p_hz, "Hz"),
    ("Predelay", p_ms, "ms"),
]
DELAY_PARAMS = [
    ("Time", p_raw, "raw(musical)"),
    ("Feedback level", p_pct, "%"),
    ("Output wet", p_pct, "%"),
    ("Output dry", p_pct, "%"),
    ("Feedback cutoff", p_hz, "Hz"),
    ("Stereo spread", p_pct, "%"),
]


def _restores():
    """Mutable list of (slot, idx, orig_norm) to undo at the end."""
    return []


def sweep_and_print(bridge, track, slot, idx, name, parser, unit, restores):
    """Snapshot, sweep idx across STEPS (using set's own readback string),
    print a table, and register the restore. Returns rows."""
    snap = safety.take_snapshot(bridge, "plugin_param:%d:%d:%d" % (track, slot, idx))
    restores.append((slot, idx, snap["v"]))

    print("\n=== %s  (slot %d, idx %d)   orig=%s [%s] ==="
          % (name, slot, idx, snap["v"], snap.get("s")))
    print("  set_norm  raw_string            parsed (%s)" % unit)
    print("  --------  -------------------  ----------------")
    rows = []
    for norm in STEPS:
        res = bridge.call(protocol.CMD_PLUGIN_SET_PARAM,
                          {"track": track, "slot": slot, "param": idx, "value": norm})
        s = res.get("s", "")
        parsed = parser(s)
        rows.append((norm, s, parsed))
        ps = "" if parsed is None else ("%g" % parsed)
        print("  %8.2f  %-19s  %s" % (norm, repr(s), ps))
    return rows


def calibrate_plugin(bridge, track, slot, label, targets, restores):
    dump = fetch_all_pages(bridge, protocol.CMD_PLUGIN_GET_PARAMS, "params",
                           {"track": track, "slot": slot})
    name_to_idx = {p["name"]: p["i"] for p in dump.get("params", [])}
    print("\n##################  %s  (slot %d, %d params)  ##################"
          % (label, slot, dump.get("total")))
    for name, parser, unit in targets:
        idx = name_to_idx.get(name)
        if idx is None:
            print("\n  -- %r not found on this plugin, skipping --" % name)
            continue
        sweep_and_print(bridge, track, slot, idx, name, parser, unit, restores)


def main(argv) -> int:
    track = int(argv[1]) if len(argv) > 1 else 2

    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive -- FL open? controller loaded? daemon up (tcp)?")
        return 1
    print("Heartbeat age:", bridge.heartbeat_age())

    # detect slots by plugin name (don't assume) ------------------------------
    listing = bridge.call(protocol.CMD_PLUGIN_LIST, {"track": track})
    slots = {s["slot"]: s["name"] for s in listing.get("slots", [])}
    print("track %d layout: %s" % (track, slots))

    def find(*matches):
        for sl, nm in slots.items():
            low = nm.lower()
            if any(m in low for m in matches):
                return sl, nm
        return None, None

    rev_slot, rev_name = find("reeverb", "reverb")
    dly_slot, dly_name = find("delay")

    restores = _restores()
    try:
        if rev_slot is not None:
            calibrate_plugin(bridge, track, rev_slot, rev_name, REVERB_PARAMS, restores)
        else:
            print("\nNo reverb found on track %d." % track)
        if dly_slot is not None:
            calibrate_plugin(bridge, track, dly_slot, dly_name, DELAY_PARAMS, restores)
        else:
            print("\nNo delay found on track %d." % track)
    finally:
        print("\n--- restoring %d params to originals ---" % len(restores))
        for slot, idx, orig in restores:
            bridge.call(protocol.CMD_PLUGIN_SET_PARAM,
                        {"track": track, "slot": slot, "param": idx, "value": orig})
        for slot, idx, orig in restores:
            got = bridge.call(protocol.CMD_PLUGIN_GET_PARAM,
                              {"track": track, "slot": slot, "param": idx})
            gv = got.get("v")
            ok = gv is not None and abs(gv - orig) < 0.005
            print("  slot %d idx %2d -> v=%s s=%r (orig %s)  %s"
                  % (slot, idx, got.get("v"), got.get("s"), orig, "OK" if ok else "!! MISMATCH"))

    print("\nDone -- calibration data above, both plugins restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
