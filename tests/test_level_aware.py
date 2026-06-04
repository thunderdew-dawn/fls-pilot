#!/usr/bin/env python3
"""Level-awareness Slice 2 test: fl_get_track_level + level-aware compression.

Exercises BOTH compressors via the real MCP tools, then rolls back:
  - Fruity Limiter on track 9 (heavy_vocal_compression)
  - FabFilter Pro-C on track 8 (glue_drums, with Style)
Passes in either transport state: PLAYING -> threshold level-matched
(peak - offset); STOPPED -> preset fallback + note.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/test_level_aware.py
Run once STOPPED (fallback) and once PLAYING (level-matched).
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.connection import get_bridge  # noqa: E402
from fl_studio_mcp.server import build_server  # noqa: E402
from fl_studio_mcp.tools.mixing import _named_params  # noqa: E402

LIM_TRACK, LIM_SLOT = 9, 4
PROC_TRACK, PROC_SLOT = 8, 4
LIM_PARAMS = ["Comp ratio", "Comp threshold", "Comp attack time", "Comp release time", "Gain"]
PROC_PARAMS = ["Ratio", "Threshold", "Attack", "Release", "Output Level", "Style", "Auto Gain"]
_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    if cond:
        _P += 1
    else:
        _F += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


def approx(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def unwrap(result):
    for attr in ("data", "structured_content", "structuredContent"):
        v = getattr(result, attr, None)
        if v is not None:
            return v
    return result


def _num(s):
    m = re.search(r"[-+]?\d*\.?\d+", str(s or ""))
    return float(m.group()) if m else None


def param_strings(bridge, track, slot, names):
    P = _named_params(bridge, track, slot, max_index=256)
    out = {}
    for nm in names:
        if nm in P:
            out[nm] = bridge.call(
                protocol.CMD_PLUGIN_GET_PARAM, {"track": track, "slot": slot, "param": P[nm]["i"]}
            ).get("s")
    return out


def check_apply(tag, r, offset):
    """Common assertions for an apply result (matched or fallback)."""
    lv = r.get("level", {})
    print(
        "  {}: matched={} measured={} chosen_thr={} | set={}".format(
            tag, lv.get("matched"), lv.get("measured"), lv.get("chosen_threshold_db"), r.get("set")
        )
    )
    if lv.get("matched"):
        peak = (lv.get("measured") or {}).get("peak_db")
        check(
            f"{tag} level-matched: chosen ~= peak - {offset:g}",
            approx(lv.get("chosen_threshold_db"), (peak or 0) - offset, 1.0),
            f"peak={peak} chosen={lv.get('chosen_threshold_db')}",
        )
    else:
        check(f"{tag} preset fallback note present", bool(r.get("note")), str(r.get("note")))


def main() -> int:
    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive.")
        return 1
    m = build_server()

    def call(name, args):
        return unwrap(asyncio.run(m.call_tool(name, args)))

    # 0. standalone level tool
    print("[1] fl_get_track_level")
    l9 = call("fl_get_track_level", {"track": LIM_TRACK})
    l8 = call("fl_get_track_level", {"track": PROC_TRACK})
    print("  track %d: %s" % (LIM_TRACK, l9))
    print("  track %d: %s" % (PROC_TRACK, l8))
    check("level tool returns playing flag", "playing" in l9 and "playing" in l8)

    # capture originals of the params each intent touches
    pre9 = param_strings(bridge, LIM_TRACK, LIM_SLOT, LIM_PARAMS)
    pre8 = param_strings(bridge, PROC_TRACK, PROC_SLOT, PROC_PARAMS)

    print("\n[2] level-aware compression (Limiter t9 + Pro-C t8)")
    r9 = call(
        "fl_apply_compression_intent",
        {
            "track": LIM_TRACK,
            "slot": LIM_SLOT,
            "intent": "heavy_vocal_compression",
            "intensity": 0.6,
            "level_aware": True,
        },
    )
    check("Limiter plugin matched", "limiter" in (r9.get("plugin") or "").lower(), r9.get("plugin"))
    check_apply("Limiter", r9, offset=12.0)

    r8 = call(
        "fl_apply_compression_intent",
        {
            "track": PROC_TRACK,
            "slot": PROC_SLOT,
            "intent": "glue_drums",
            "intensity": 0.5,
            "level_aware": True,
        },
    )
    check("Pro-C plugin matched", "pro-c" in (r8.get("plugin") or "").lower(), r8.get("plugin"))
    check(
        "Pro-C Style set to Bus",
        (r8.get("readback", {}).get("Style") or "").strip().lower() == "bus",
        r8.get("readback", {}).get("Style"),
    )
    check_apply("Pro-C", r8, offset=8.0)

    # 3. rollback both, verify restore
    print("\n[3] rollback x2 + restore check")
    rb1 = call("fl_rollback_last_change", {}).get("rolled_back")
    rb2 = call("fl_rollback_last_change", {}).get("rolled_back")
    check(
        "both rollbacks reverted compression",
        rb1 == "apply_compression_intent" and rb2 == "apply_compression_intent",
        f"{rb1} {rb2}",
    )
    post9 = param_strings(bridge, LIM_TRACK, LIM_SLOT, LIM_PARAMS)
    post8 = param_strings(bridge, PROC_TRACK, PROC_SLOT, PROC_PARAMS)
    check("Limiter params restored", post9 == pre9, f"pre={pre9} post={post9}")
    check("Pro-C params restored", post8 == pre8, f"pre={pre8} post={post8}")

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
