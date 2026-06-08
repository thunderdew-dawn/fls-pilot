#!/usr/bin/env python3
"""Compression Slice 1: calibrate the COMP section of Fruity Limiter.

Auto-detects the Fruity Limiter slot on the target track (matches by name --
no hardcoded slot), then sweeps its COMP params (+ the global makeup Gain)
across normalized 0.0..1.0, reads back FL's display string, parses it, and
PRINTS the raw curves. Pure data collection -- NO conversion fns, NO intents.

Safety: every swept param is snapshotted via the safety layer FIRST and
restored in a finally block, so the Limiter is left exactly as set.

    set FLS_PILOT_TRANSPORT=tcp
    python scripts/calibrate_limiter.py [track]      # default track 9
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from fls_pilot import protocol, safety  # noqa: E402
from fls_pilot.connection import fetch_all_pages, get_bridge  # noqa: E402

STEPS = [round(i * 0.05, 4) for i in range(21)]
_NUM = re.compile(r"[-+]?\d*\.?\d+")


def _num(s):
    m = _NUM.search(str(s or ""))
    return float(m.group()) if m else None


def p_db(s):
    return _num(s) if "db" in str(s).lower() else None  # "-INFdB" -> None (raw shown)


def p_ms(s):
    return _num(s) if "ms" in str(s).lower() else None


def p_pct(s):
    return _num(s) if "%" in str(s) else None


def p_ratio(s):
    """'1:1.0' -> 1.0, '1:4.0' -> 4.0 (second/first); raw also printed."""
    t = str(s)
    if ":" in t:
        a, _, b = t.partition(":")
        na, nb = _num(a), _num(b)
        if na:
            return round(nb / na, 3) if nb is not None else None
    return _num(s)


def p_raw(_s):
    return None


# COMP params to calibrate (+ global makeup Gain). Names resolved live.
COMP_PARAMS = [
    ("Comp threshold", p_db, "dB"),
    ("Comp ratio", p_ratio, "ratio(2nd/1st)"),
    ("Comp knee", p_pct, "%"),
    ("Comp attack time", p_ms, "ms"),
    ("Comp release time", p_ms, "ms"),
    ("Comp RMS window", p_ms, "ms"),
    ("Comp curve", p_raw, "raw"),
    ("Gain", p_db, "dB (makeup)"),
]


def sweep_and_print(bridge, track, slot, idx, name, parser, unit, restores):
    snap = safety.take_snapshot(bridge, "plugin_param:%d:%d:%d" % (track, slot, idx))
    restores.append((slot, idx, snap["v"]))
    print("\n=== %s  (idx %d)   orig=%s [%s] ===" % (name, idx, snap["v"], snap.get("s")))
    print(f"  set_norm  raw_string            parsed ({unit})")
    print("  --------  -------------------  ----------------")
    for norm in STEPS:
        res = bridge.call(
            protocol.CMD_PLUGIN_SET_PARAM,
            {"track": track, "slot": slot, "param": idx, "value": norm},
        )
        s = res.get("s", "")
        parsed = parser(s)
        ps = "" if parsed is None else (f"{parsed:g}")
        print(f"  {norm:8.2f}  {repr(s):19}  {ps}")


def main(argv) -> int:
    track = int(argv[1]) if len(argv) > 1 else 9

    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive -- FL open? controller loaded? daemon up (tcp)?")
        return 1
    print("Heartbeat age:", bridge.heartbeat_age())

    listing = bridge.call(protocol.CMD_PLUGIN_LIST, {"track": track})
    slot = next(
        (s["slot"] for s in listing.get("slots", []) if "limiter" in (s["name"] or "").lower()),
        None,
    )
    if slot is None:
        print("No Fruity Limiter found on track %d: %s" % (track, listing.get("slots")))
        return 1
    print("Fruity Limiter on track %d slot %d" % (track, slot))

    dump = fetch_all_pages(
        bridge, protocol.CMD_PLUGIN_GET_PARAMS, "params", {"track": track, "slot": slot}
    )
    name_to_idx = {p["name"]: p["i"] for p in dump.get("params", [])}

    # COMP-inert-by-default check (the silent-fail risk)
    thr = next((p for p in dump["params"] if p["name"] == "Comp threshold"), None)
    rat = next((p for p in dump["params"] if p["name"] == "Comp ratio"), None)
    print(
        "\nCOMP default state: ratio={!r} threshold={!r}  -> {}".format(
            rat and rat["s"],
            thr and thr["s"],
            "INERT (ratio 1:1) -- intent must set ratio>1 AND lower threshold"
            if rat and rat["s"] in ("1:1.0", "1:1")
            else "check",
        )
    )

    restores = []
    try:
        for name, parser, unit in COMP_PARAMS:
            idx = name_to_idx.get(name)
            if idx is None:
                print(f"\n  -- {name!r} not found, skipping --")
                continue
            sweep_and_print(bridge, track, slot, idx, name, parser, unit, restores)
    finally:
        print(f"\n--- restoring {len(restores)} params to originals ---")
        for slot_, idx, orig in restores:
            bridge.call(
                protocol.CMD_PLUGIN_SET_PARAM,
                {"track": track, "slot": slot_, "param": idx, "value": orig},
            )
        for slot_, idx, orig in restores:
            got = bridge.call(
                protocol.CMD_PLUGIN_GET_PARAM, {"track": track, "slot": slot_, "param": idx}
            )
            gv = got.get("v")
            ok = gv is not None and abs(gv - orig) < 0.005
            print(
                "  idx %2d -> v=%s s=%r (orig %s)  %s"
                % (idx, gv, got.get("s"), orig, "OK" if ok else "!! MISMATCH")
            )

    print("\nDone -- calibration data above, Limiter restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
