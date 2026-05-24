#!/usr/bin/env python3
"""Slice B test: eq_curves unit tests + EQ mixing intents end-to-end.

Unit tests are pure (no FL). The intent tests build the real FastMCP server
and call the registered tools (fl_apply_eq_intent, fl_plugin_get_params,
fl_rollback_last_change) in-process -- the same path Claude Desktop uses.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/test_mixing_intents.py

Target: mixer track 2, slot 0 (Fruity Parametric EQ 2 on VOX). Restores the
EQ via rollback at the end; asserts the full param dump matches pre-state.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol                       # noqa: E402
from fl_studio_mcp.connection import get_bridge           # noqa: E402
from fl_studio_mcp.music import eq_curves as eq           # noqa: E402
from fl_studio_mcp.music.eq_curves import (               # noqa: E402
    eq2_band_param_index, norm_to_db,
)
from fl_studio_mcp.server import build_server             # noqa: E402

# Target a track/slot holding a Fruity Parametric EQ 2. Override on the CLI:
#   python scripts/test_mixing_intents.py <track> <slot>
TRACK = int(sys.argv[1]) if len(sys.argv) > 1 else 2
SLOT = int(sys.argv[2]) if len(sys.argv) > 2 else 0
_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    if cond:
        _P += 1
    else:
        _F += 1
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", label,
                           ("  -- " + detail) if detail else ""))


def approx(a, b, tol):
    return a is not None and abs(a - b) <= tol


def unwrap(result):
    for attr in ("data", "structured_content", "structuredContent"):
        v = getattr(result, attr, None)
        if v is not None:
            return v
    return result


def _num(s):
    m = re.search(r"[-+]?\d*\.?\d+", str(s or ""))
    return float(m.group()) if m else None


def parse_hz(s):
    n = _num(s)
    if n is None:
        return None
    return n * 1000.0 if "khz" in str(s).lower() else n


def parse_db(s):
    return _num(s)


def unit_tests():
    print("[1] eq_curves unit tests (pure)")
    check("freq_to_norm(250) ~ 0.366", approx(eq.freq_to_norm(250), 0.3656, 0.001))
    check("norm_to_freq(0.5) ~ 632 Hz", approx(eq.norm_to_freq(0.5), 632.45, 1.0))
    check("db_to_norm(-3) ~ 0.4167", approx(eq.db_to_norm(-3), 0.41667, 0.0005))
    check("db_to_norm(0) = 0.5", approx(eq.db_to_norm(0), 0.5, 1e-9))
    check("norm_to_db(0.6167) ~ +4.2", approx(eq.norm_to_db(0.61667), 4.2, 0.01))
    check("db_to_norm clamps (+99 -> 1.0)", eq.db_to_norm(99) == 1.0)
    check("width_to_norm(40) = 0.4", approx(eq.width_to_norm(40), 0.4, 1e-9))
    check("TYPE_NORMS peaking = 6/7", approx(eq.TYPE_NORMS["peaking"], 6 / 7, 1e-9))
    check("TYPE_NORMS high_shelf = 1.0", approx(eq.TYPE_NORMS["high_shelf"], 1.0, 1e-9))
    check("band1 type idx = 21", eq2_band_param_index(1, "type") == 21)
    check("band3 freq idx = 9", eq2_band_param_index(3, "freq") == 9)
    check("band7 width idx = 20", eq2_band_param_index(7, "width") == 20)


def band_summary(bridge):
    out = {}
    for b in range(1, 8):
        t = bridge.call(protocol.CMD_PLUGIN_GET_PARAM,
                        {"track": TRACK, "slot": SLOT, "param": eq2_band_param_index(b, "type")})
        lv = bridge.call(protocol.CMD_PLUGIN_GET_PARAM,
                         {"track": TRACK, "slot": SLOT, "param": eq2_band_param_index(b, "level")})
        out[b] = (t.get("s"), round(norm_to_db(lv.get("v") if lv.get("v") is not None else 0.5), 1))
    return out


def main() -> int:
    unit_tests()

    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("\nBridge not alive -- FL open? controller loaded? daemon up (tcp)?")
        return 1

    m = build_server()

    def call(name, args):
        return unwrap(asyncio.run(m.call_tool(name, args)))

    pre_dump = call("fl_plugin_get_params", {"track": TRACK, "slot": SLOT})
    print("\n[2] EQ intents end-to-end (track %d slot %d)" % (TRACK, SLOT))
    print("  pre-state bands:", band_summary(bridge))

    # remove_mud @ 0.5 -> expect Peaking / ~250Hz / -3.0dB ---------------------
    r1 = call("fl_apply_eq_intent",
              {"track": TRACK, "slot": SLOT, "intent": "remove_mud", "intensity": 0.5})
    print("  remove_mud(0.5):", r1.get("band"), r1.get("set"), r1.get("readback"))
    b1, rb1 = r1.get("band"), r1.get("readback", {})
    check("remove_mud -> Peaking",
          (rb1.get("Band %d type" % b1) or "").strip().lower() == "peaking", str(rb1))
    check("remove_mud -> ~250 Hz", approx(parse_hz(rb1.get("Band %d freq" % b1)), 250, 8))
    check("remove_mud -> -3.0 dB", approx(parse_db(rb1.get("Band %d level" % b1)), -3.0, 0.15))

    # add_air @ 0.7 -> expect High shelf / ~12kHz / +4.2dB, different band ------
    r2 = call("fl_apply_eq_intent",
              {"track": TRACK, "slot": SLOT, "intent": "add_air", "intensity": 0.7})
    print("  add_air(0.7):", r2.get("band"), r2.get("set"), r2.get("readback"))
    b2, rb2 = r2.get("band"), r2.get("readback", {})
    check("add_air uses a different band", b2 != b1, "b1=%s b2=%s" % (b1, b2))
    check("add_air -> High shelf",
          (rb2.get("Band %d type" % b2) or "").strip().lower() == "high shelf", str(rb2))
    check("add_air -> ~12 kHz", approx(parse_hz(rb2.get("Band %d freq" % b2)), 12000, 400))
    check("add_air -> +4.2 dB", approx(parse_db(rb2.get("Band %d level" % b2)), 4.2, 0.15))

    print("  post-apply bands:", band_summary(bridge))

    # rollback both (LIFO: add_air first, then remove_mud) ---------------------
    rbk1 = call("fl_rollback_last_change", {})
    rbk2 = call("fl_rollback_last_change", {})
    print("  rollback1:", rbk1.get("rolled_back"), "| rollback2:", rbk2.get("rolled_back"))
    check("both rollbacks reverted apply_eq_intent",
          rbk1.get("rolled_back") == "apply_eq_intent" and rbk2.get("rolled_back") == "apply_eq_intent")

    post_dump = call("fl_plugin_get_params", {"track": TRACK, "slot": SLOT})
    print("  post-rollback bands:", band_summary(bridge))
    check("full EQ param dump restored to pre-state",
          post_dump.get("params") == pre_dump.get("params"))

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
