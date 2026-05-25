#!/usr/bin/env python3
"""3rd-party Slice 2: calibrate FabFilter Pro-C 3 COMP params.

Auto-detects the Pro-C slot (by name), builds a name->index map from a capped
low-index scan (the real params live at idx 0..99, so no need to page all 4240),
then sweeps the CORE comp params -- addressed BY NAME -- across norm 0..1,
reads back the value-string, parses it, and prints the curves. Also maps the
discrete Style param and reports Auto Gain / Auto Release. Pure data collection.

Safety: every swept param is snapshotted via the safety layer FIRST and restored
in a finally block, so Pro-C is left exactly as set.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/calibrate_proc3.py [track] [slot]   # default auto-detect / 8,4
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from fl_studio_mcp import protocol, safety              # noqa: E402
from fl_studio_mcp.connection import get_bridge           # noqa: E402

STEPS = [round(i * 0.05, 4) for i in range(21)]
MATCH = ("pro-c", "pro c", "fabfilter")
_NUM = re.compile(r"[-+]?\d*\.?\d+")


def _num(s):
    m = _NUM.search(str(s or ""))
    return float(m.group()) if m else None


def p_db(s):
    return _num(s) if "db" in str(s).lower() else None     # "-INF dB" -> None (raw shown)


def p_ms(s):
    return _num(s) if "ms" in str(s).lower() else None


def p_pct(s):
    return _num(s) if "%" in str(s) else None


def p_ratio(s):
    t = str(s)
    return _num(t.partition(":")[0]) if ":" in t else _num(s)   # X in "X:1"


def p_raw(_s):
    return None


CORE = [
    ("Threshold", p_db, "dB"),
    ("Ratio", p_ratio, "X:1"),
    ("Knee", p_db, "dB"),
    ("Range", p_db, "dB"),
    ("Attack", p_ms, "ms"),
    ("Release", p_ms, "ms"),
    ("Output Level", p_db, "dB (makeup)"),
    ("Mix", p_pct, "%"),
]


def build_name_map(bridge, track, slot, cap=256):
    m, start = {}, 0
    while start < cap:
        page = bridge.call(protocol.CMD_PLUGIN_GET_PARAMS,
                           {"track": track, "slot": slot, "start": start}, timeout=15.0)
        for p in page.get("params", []):
            m.setdefault(p["name"], p["i"])
        nxt = page.get("next_start")
        if nxt is None or nxt <= start:
            break
        start = nxt
    return m


def sweep_and_print(bridge, track, slot, idx, name, parser, unit, restores):
    snap = safety.take_snapshot(bridge, "plugin_param:%d:%d:%d" % (track, slot, idx))
    restores.append((idx, snap["v"]))
    print("\n=== %s  (idx %d)   orig=%s [%s] ==="
          % (name, idx, snap["v"], (snap.get("s") or "").strip()))
    print("  set_norm  raw_string            parsed (%s)" % unit)
    print("  --------  -------------------  ----------------")
    rows = []
    for norm in STEPS:
        res = bridge.call(protocol.CMD_PLUGIN_SET_PARAM,
                          {"track": track, "slot": slot, "param": idx, "value": norm})
        s = (res.get("s") or "").strip()
        parsed = parser(s)
        rows.append((norm, s, parsed))
        print("  %8.2f  %-19s  %s" % (norm, repr(s), "" if parsed is None else "%g" % parsed))
    return rows


def print_style_groups(rows):
    print("\n  norm->style ranges:")
    cur, lo, hi = None, None, None
    for norm, s, _ in rows:
        if s != cur:
            if cur is not None:
                print("    %.2f .. %.2f  ->  %r" % (lo, hi, cur))
            cur, lo = s, norm
        hi = norm
    if cur is not None:
        print("    %.2f .. %.2f  ->  %r" % (lo, hi, cur))


def main(argv) -> int:
    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive -- FL open? controller loaded? daemon up (tcp)?")
        return 1

    if len(argv) > 2:
        track, slot = int(argv[1]), int(argv[2])
    else:
        track = slot = None
        st = bridge.call(protocol.CMD_GET_PROJECT_STATE)
        for t in range(int(st.get("mixer_track_count", 30)) + 1):
            sl = bridge.call(protocol.CMD_PLUGIN_LIST, {"track": t})
            hit = next((s for s in sl.get("slots", [])
                        if any(m in (s["name"] or "").lower() for m in MATCH)), None)
            if hit:
                track, slot = t, hit["slot"]
                break
        if track is None:
            print("No Pro-C found. Pass explicit track slot.")
            return 1
    print("Pro-C at track %d slot %d" % (track, slot))

    nmap = build_name_map(bridge, track, slot)

    # Auto Gain / Auto Release state (booleans that interact with manual gain/release)
    for nm in ("Auto Gain", "Auto Release", "Auto Threshold"):
        i = nmap.get(nm)
        if i is not None:
            g = bridge.call(protocol.CMD_PLUGIN_GET_PARAM, {"track": track, "slot": slot, "param": i})
            print("  %-16s (idx %d) = %r" % (nm, i, (g.get("s") or "").strip()))

    restores = []
    try:
        for name, parser, unit in CORE:
            idx = nmap.get(name)
            if idx is None:
                print("\n  -- %r not found, skipping --" % name)
                continue
            sweep_and_print(bridge, track, slot, idx, name, parser, unit, restores)

        if "Style" in nmap:
            rows = sweep_and_print(bridge, track, slot, nmap["Style"], "Style", p_raw, "raw", restores)
            print_style_groups(rows)
    finally:
        print("\n--- restoring %d params to originals ---" % len(restores))
        for idx, orig in restores:
            bridge.call(protocol.CMD_PLUGIN_SET_PARAM,
                        {"track": track, "slot": slot, "param": idx, "value": orig})
        bad = 0
        for idx, orig in restores:
            gv = bridge.call(protocol.CMD_PLUGIN_GET_PARAM,
                             {"track": track, "slot": slot, "param": idx}).get("v")
            if not (gv is not None and abs(gv - orig) < 0.005):
                bad += 1
                print("  !! idx %d not restored (v=%s orig=%s)" % (idx, gv, orig))
        print("  restored OK" if bad == 0 else "  %d param(s) MISMATCH" % bad)

    print("\nDone -- calibration data above, Pro-C restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
