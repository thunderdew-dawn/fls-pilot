#!/usr/bin/env python3
"""Slice C-2 test: reverb/delay curve unit tests + intents end-to-end.

Unit tests are pure. The intent tests build the real FastMCP server and call
the registered tools in-process (same path an MCP client uses), then roll
everything back and assert both plugins' full param dumps match pre-state.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/test_reverb_delay_intents.py [track]   # default 2

Auto-detects the reverb + delay slots by name on the target track.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.connection import get_bridge  # noqa: E402
from fl_studio_mcp.music import reverb_delay_curves as rd  # noqa: E402
from fl_studio_mcp.server import build_server  # noqa: E402

TRACK = int(sys.argv[1]) if len(sys.argv) > 1 else 2
_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    if cond:
        _P += 1
    else:
        _F += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


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


def p_hz(s):
    n = _num(s)
    return (n * 1000.0 if "khz" in str(s).lower() else n) if n is not None else None


def unit_tests():
    print("[1] reverb_delay_curves unit tests (pure)")
    check("decay_to_norm(1.5) ~ 0.0704", approx(rd.decay_to_norm(1.5), 0.0704, 0.001))
    check("norm_to_decay(0.0704) ~ 1.5", approx(rd.norm_to_decay(0.0704), 1.5, 0.05))
    check("wet_to_norm(50) = 0.4", approx(rd.wet_to_norm(50), 0.4, 1e-9))
    check("norm_to_wet(0.8) = 100", approx(rd.norm_to_wet(0.8), 100, 1e-9))
    check("roomsize_to_norm(50) ~ 0.4949", approx(rd.roomsize_to_norm(50), 0.4949, 0.001))
    check("highcut_to_norm(4000) ~ 0.162", approx(rd.highcut_to_norm(4000), 0.1622, 0.001))
    check("norm_to_highcut_hz(1.0) is None (OFF)", rd.norm_to_highcut_hz(1.0) is None)
    check("norm_to_highcut_hz(0.162) ~ 4000", approx(rd.norm_to_highcut_hz(0.1622), 4000, 30))
    check("norm_to_lowcut_hz(0.0) is None (OFF)", rd.norm_to_lowcut_hz(0.0) is None)
    check("lowcut_to_norm(75) collapses to 0.05", approx(rd.lowcut_to_norm(75), 0.05, 1e-9))
    check("delay_pct_to_norm(100) = 1.0", approx(rd.delay_pct_to_norm(100), 1.0, 1e-9))
    check("feedback_to_norm(100) = 0.8", approx(rd.feedback_to_norm(100), 0.8, 1e-9))
    check("feedback_to_norm(120) clamps to 0.8", approx(rd.feedback_to_norm(120), 0.8, 1e-9))
    check("feedback_to_norm(120, allow) = 0.96", approx(rd.feedback_to_norm(120, True), 0.96, 1e-9))
    check("cutoff norm 0.0 = 270 Hz", approx(rd.norm_to_cutoff_hz(0.0), 270, 1))
    check("cutoff norm 1.0 = 21985 Hz", approx(rd.norm_to_cutoff_hz(1.0), 21985, 1))
    check("cutoff norm 0.5 ~ 1299.6", approx(rd.norm_to_cutoff_hz(0.5), 1299.6, 1))
    check(
        "cutoff_hz_to_norm(1299.6) ~ 0.5 (round-trip)",
        approx(rd.cutoff_hz_to_norm(1299.6), 0.5, 0.002),
    )
    check("division_norm('1/4') = 0.25", approx(rd.division_norm("1/4"), 0.25, 1e-9))
    check(
        "nearest_division(0.249) = 1/4", rd.DIVISIONS[rd.nearest_division_index(0.249)][0] == "1/4"
    )
    check("step_division(0.25,+1) = 1/2", rd.step_division(0.25, 1) == ("1/2", 0.5))
    check("step_division(1.0,+1) clamps to 1/1", rd.step_division(1.0, 1)[0] == "1/1")


def main() -> int:
    unit_tests()

    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("\nBridge not alive -- FL open? controller loaded? daemon up (tcp)?")
        return 1

    listing = bridge.call(protocol.CMD_PLUGIN_LIST, {"track": TRACK})
    slots = {s["slot"]: s["name"] for s in listing.get("slots", [])}
    rev_slot = next(
        (sl for sl, nm in slots.items() if "reeverb" in nm.lower() or "reverb" in nm.lower()), None
    )
    dly_slot = next((sl for sl, nm in slots.items() if "delay" in nm.lower()), None)
    print(
        "\n[2] intents end-to-end -- track %d: reverb slot=%s, delay slot=%s"
        % (TRACK, rev_slot, dly_slot)
    )
    if rev_slot is None or dly_slot is None:
        print("  Need both a reverb and a delay on track %d." % TRACK)
        return 1

    m = build_server()

    def call(name, args):
        return unwrap(asyncio.run(m.call_tool(name, args)))

    def dump(slot):
        return call("fl_plugin_get_params", {"track": TRACK, "slot": slot})

    pre_rev, pre_dly = dump(rev_slot), dump(dly_slot)

    # --- reverb ---
    r = call(
        "fl_apply_reverb_intent",
        {"track": TRACK, "slot": rev_slot, "intent": "more_space", "intensity": 0.6},
    )
    print("  more_space(0.6):", r.get("set"), r.get("readback"))
    dsec = _num(r.get("readback", {}).get("Decay time"))
    wet = _num(r.get("readback", {}).get("Wet level"))
    check("more_space decay longer (3-5s)", approx(dsec, 4.0, 1.0), f"decay={dsec}")
    check("more_space wet up (>50%)", wet is not None and wet > 50, f"wet={wet}")

    r = call(
        "fl_apply_reverb_intent",
        {"track": TRACK, "slot": rev_slot, "intent": "tighten_reverb", "intensity": 0.5},
    )
    print("  tighten_reverb(0.5):", r.get("set"), r.get("readback"))
    dsec = _num(r.get("readback", {}).get("Decay time"))
    check("tighten decay shorter (<1.5s)", dsec is not None and dsec < 1.5, f"decay={dsec}")

    r = call(
        "fl_apply_reverb_intent",
        {"track": TRACK, "slot": rev_slot, "intent": "darker_reverb", "intensity": 0.5},
    )
    print("  darker_reverb(0.5):", r.get("set"), r.get("readback"))
    hc = r.get("readback", {}).get("High cut")
    check(
        "darker high-cut is a real Hz, not Off",
        "off" not in str(hc).lower() and p_hz(hc) is not None,
        f"hc={hc!r}",
    )
    check("darker high-cut moved DOWN (<4000 Hz)", approx(p_hz(hc), 3000, 1200), f"hc={hc!r}")

    # --- delay ---
    r = call("fl_apply_delay_intent", {"track": TRACK, "slot": dly_slot, "intent": "longer_delay"})
    print("  longer_delay:", r.get("set"), r.get("readback"))
    check(
        "longer_delay stepped 1/4 -> 1/2",
        r.get("set", {}).get("division_before") == "1/4"
        and r.get("set", {}).get("division_after") == "1/2",
        str(r.get("set")),
    )

    r = call(
        "fl_apply_delay_intent",
        {"track": TRACK, "slot": dly_slot, "intent": "more_feedback", "intensity": 0.5},
    )
    print("  more_feedback(0.5):", r.get("set"), r.get("readback"), "warn=", r.get("warning"))
    fb = _num(r.get("readback", {}).get("Feedback level"))
    check("more_feedback up (>62.5%) and <=100%", fb is not None and 62.5 < fb <= 100.0, f"fb={fb}")
    check("no self-oscillation warning at intensity 0.5", r.get("warning") is None)

    # --- rollback all 5, verify both plugins restored ---
    rolled = [call("fl_rollback_last_change", {}).get("rolled_back") for _ in range(5)]
    print("  rollbacks (LIFO):", rolled)
    check(
        "5 rollbacks all reverted intents",
        rolled
        == [
            "apply_delay_intent",
            "apply_delay_intent",
            "apply_reverb_intent",
            "apply_reverb_intent",
            "apply_reverb_intent",
        ],
        str(rolled),
    )

    post_rev, post_dly = dump(rev_slot), dump(dly_slot)
    check("reverb full dump restored to pre-state", post_rev.get("params") == pre_rev.get("params"))
    check("delay full dump restored to pre-state", post_dly.get("params") == pre_dly.get("params"))

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
