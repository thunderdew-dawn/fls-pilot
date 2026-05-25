#!/usr/bin/env python3
"""Slice A: empirically calibrate Fruity Parametric EQ 2 (norm <-> Hz/dB/...).

Drives FL via the bridge: sweeps Band 1's freq / level / type / width params
across normalized 0.0..1.0 (21 steps of 0.05), reads back FL's display string
at each step, parses it, and PRINTS the raw curves. Pure data collection --
NO conversion functions, NO mixing intents (those are Slice B).

Safety: Band 1's four params are snapshotted via the safety layer FIRST and
restored in a finally block at the end, so the EQ is never left swept even if
the run errors.

    set FLSTUDIO_MCP_TRANSPORT=tcp        # route through the running daemon
    python scripts/calibrate_eq.py

Target: mixer track 2, slot 0 (Fruity Parametric EQ 2 on VOX).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from fl_studio_mcp import protocol, safety              # noqa: E402
from fl_studio_mcp.connection import get_bridge          # noqa: E402
from fl_studio_mcp.tools.plugin import resolve_param_index  # noqa: E402

TRACK = 2
SLOT = 0
STEPS = [round(i * 0.05, 4) for i in range(21)]          # 0.00 .. 1.00

_NUM = re.compile(r"[-+]?\d*\.?\d+")


def _num(s):
    """First numeric token in a string, as float, or None."""
    if not s:
        return None
    m = _NUM.search(str(s))
    return float(m.group()) if m else None


def parse_hz(s):
    """'63Hz'->63, '1363Hz'->1363, '4.0kHz'->4000. None if it doesn't parse."""
    n = _num(s)
    if n is None:
        return None
    t = str(s).lower().replace(" ", "")
    if "khz" in t:
        return n * 1000.0
    if "hz" in t:
        return n
    return None


def parse_db(s):
    """'0.0dB'->0.0, '-5.4dB'->-5.4. Just the number (defensive)."""
    return _num(s)


def parse_pct(s):
    """'61%'->61. Just the number."""
    return _num(s)


def sweep(bridge, idx, parser):
    """Set idx across STEPS, read back string each time. Returns rows of
    (set_norm, readback_v, raw_string, parsed)."""
    rows = []
    for norm in STEPS:
        bridge.call(protocol.CMD_PLUGIN_SET_PARAM,
                    {"track": TRACK, "slot": SLOT, "param": idx, "value": norm})
        got = bridge.call(protocol.CMD_PLUGIN_GET_PARAM,
                          {"track": TRACK, "slot": SLOT, "param": idx})
        s = got.get("s", "")
        rows.append((norm, got.get("v"), s, parser(s) if parser else None))
    return rows


def print_table(title, rows, parsed_label):
    print("\n=== %s ===" % title)
    print("  set_norm  readback_v  raw_string          %s" % parsed_label)
    print("  --------  ----------  ------------------  --------")
    for norm, v, s, parsed in rows:
        vs = "%.4f" % v if isinstance(v, (int, float)) else "?"
        ps = "" if parsed is None else ("%g" % parsed)
        print("  %8.2f  %10s  %-18s  %s" % (norm, vs, repr(s), ps))


def print_type_groups(rows):
    """Collapse the type sweep into contiguous norm ranges per type string."""
    print("\n  norm->type ranges:")
    cur = None
    lo = hi = None
    for norm, _v, s, _p in rows:
        if s != cur:
            if cur is not None:
                print("    %.2f .. %.2f  ->  %r" % (lo, hi, cur))
            cur, lo = s, norm
        hi = norm
    if cur is not None:
        print("    %.2f .. %.2f  ->  %r" % (lo, hi, cur))


def main() -> int:
    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive -- FL open? controller loaded? daemon up (tcp)?")
        return 1
    print("Heartbeat age:", bridge.heartbeat_age())

    names = {"freq": "Band 1 freq", "level": "Band 1 level",
             "type": "Band 1 type", "width": "Band 1 width"}
    idx = {}
    for key, nm in names.items():
        i, resolved = resolve_param_index(bridge, TRACK, SLOT, nm)
        idx[key] = i
        print("  resolved %-12r -> idx %d (%r)" % (nm, i, resolved))

    # snapshot originals via the safety layer (so restore is exact) ----------
    orig = {}
    for key, i in idx.items():
        snap = safety.take_snapshot(bridge, "plugin_param:%d:%d:%d" % (TRACK, SLOT, i))
        orig[key] = snap["v"]
    print("\noriginals (normalized):", {k: orig[k] for k in idx})

    try:
        print_table("Band 1 FREQ (idx %d)" % idx["freq"],
                    sweep(bridge, idx["freq"], parse_hz), "parsed_Hz")
        print_table("Band 1 LEVEL (idx %d)" % idx["level"],
                    sweep(bridge, idx["level"], parse_db), "parsed_dB")
        type_rows = sweep(bridge, idx["type"], None)
        print_table("Band 1 TYPE (idx %d)" % idx["type"], type_rows, "(raw)")
        print_type_groups(type_rows)
        print_table("Band 1 WIDTH (idx %d)" % idx["width"],
                    sweep(bridge, idx["width"], parse_pct), "parsed")
    finally:
        # ALWAYS restore Band 1 to its captured originals.
        print("\n--- restoring Band 1 to originals ---")
        for key, i in idx.items():
            bridge.call(protocol.CMD_PLUGIN_SET_PARAM,
                        {"track": TRACK, "slot": SLOT, "param": i, "value": orig[key]})
        for key, i in idx.items():
            got = bridge.call(protocol.CMD_PLUGIN_GET_PARAM,
                              {"track": TRACK, "slot": SLOT, "param": i})
            gv = got.get("v")
            ok = gv is not None and abs(gv - orig[key]) < 0.005
            print("  %-6s idx %2d -> v=%s s=%r  (orig %s)  %s"
                  % (key, i, got.get("v"), got.get("s"), orig[key],
                     "OK" if ok else "!! MISMATCH"))

    print("\nDone -- calibration data above, Band 1 restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
