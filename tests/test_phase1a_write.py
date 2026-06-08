#!/usr/bin/env python3
"""Phase 1A WRITE tester -- mixer/channel writes through the safety layer.

Drives safety.safe_write / take_snapshot / rollback_last_change / set_dry_run
directly with an FLBridge (the exact code path the MCP tools use). Includes an
EXPLICIT dB-conversion assertion: if -6 dB doesn't land near 0.8*10**(-6/20),
the controller is using 1.0 as unity instead of 0.8 -- flagged loudly.

Run with the daemon STOPPED (opens the bridge directly).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import safety  # noqa: E402
from fls_pilot.connection import FLBridge  # noqa: E402
from fls_pilot.protocol import (  # noqa: E402
    CMD_MIXER_GET_TRACK,
    CMD_MIXER_SET_MUTE,
    CMD_MIXER_SET_PAN,
    CMD_MIXER_SET_VOLUME,
)

PASS = True


def check(label, cond, detail=""):
    global PASS
    if not cond:
        PASS = False
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label} {detail}")


def _vol_restore(track):
    # unified volume field is "vol_norm" (0..1) on every response
    return lambda b: {
        "command": CMD_MIXER_SET_VOLUME,
        "params": {"track": track, "value": b["vol_norm"], "unit": "normalized"},
    }


def main() -> int:
    bridge = FLBridge()
    bridge.open()
    bridge.wait_for_heartbeat()
    print("Heartbeat age:", bridge.heartbeat_age())
    safety.set_dry_run(False)

    base = safety.take_snapshot(bridge, "mixer_track:1")
    base_norm, base_pan = base["vol_norm"], base["pan"]
    print("baseline track 1:", base)
    print(f"  (baseline norm {base_norm:.4f} -- expected ~0.6205 if unchanged)\n")

    # 1. set -6 dB, EXPLICIT dB-conversion assertion -------------------------
    expected = 0.8 * (10 ** (-6 / 20.0))  # 0.8-unity -> ~0.4009
    naive_1p0 = 1.0 * (10 ** (-6 / 20.0))  # what a 1.0-unity bug gives (~0.5012)
    res = safety.safe_write(
        bridge,
        tool="mixer_set_volume",
        scope="mixer_track:1",
        command=CMD_MIXER_SET_VOLUME,
        params={"track": 1, "value": -6, "unit": "db"},
        build_restore=_vol_restore(1),
    )
    actual = res["after"]["vol_norm"]
    print("set track1 = -6 dB")
    print(
        "    expected vol_norm = {:.4f}   |"
        "   actual vol_norm = {:.4f}   |"
        "   vol_db = {:.2f}".format(expected, actual, res["after"]["vol_db"])
    )
    if abs(actual - expected) <= 0.001:
        check("dB conversion (0.8 = unity)", True, "(within 0.001)")
    else:
        check(
            "dB conversion (0.8 = unity)",
            False,
            f"\n      !!!! MISMATCH -- actual {actual:.4f} != expected {expected:.4f}. "
            f"If actual ~= {naive_1p0:.4f} the controller is using 1.0 as unity, NOT 0.8 !!!!",
        )

    rb = safety.rollback_last_change(bridge)
    rnorm = rb["restored"]["vol_norm"]
    print(f"rollback volume -> restored norm {rnorm:.4f} (baseline {base_norm:.4f})")
    check("volume rollback == baseline", abs(rnorm - base_norm) <= 0.001)
    print()

    # 2. pan +0.5, rollback --------------------------------------------------
    res = safety.safe_write(
        bridge,
        tool="mixer_set_pan",
        scope="mixer_track:1",
        command=CMD_MIXER_SET_PAN,
        params={"track": 1, "value": 0.5},
        build_restore=lambda b: {
            "command": CMD_MIXER_SET_PAN,
            "params": {"track": 1, "value": b["pan"]},
        },
    )
    print(f"set track1 pan = +0.5 -> actual {res['after']['pan']:.4f}")
    check("pan set ~= 0.5", abs(res["after"]["pan"] - 0.5) <= 0.01)
    rb = safety.rollback_last_change(bridge)
    print(f"rollback pan -> {rb['restored']['pan']:.4f} (baseline {base_pan:.4f})")
    check("pan rollback == baseline", abs(rb["restored"]["pan"] - base_pan) <= 0.01)
    print()

    # 3. mute track 2, rollback ---------------------------------------------
    base_mute = safety.take_snapshot(bridge, "mixer_track:2")["mute"]
    res = safety.safe_write(
        bridge,
        tool="mixer_set_mute",
        scope="mixer_track:2",
        command=CMD_MIXER_SET_MUTE,
        params={"track": 2, "state": True},
        verify=("mute", True),
        build_restore=lambda b: {
            "command": CMD_MIXER_SET_MUTE,
            "params": {"track": 2, "state": b["mute"]},
        },
    )
    print(f"mute track2 -> {res['after']['mute']}")
    check("track 2 muted", res["after"]["mute"] is True)
    rb = safety.rollback_last_change(bridge)
    print(f"rollback mute -> {rb['restored']['mute']} (baseline {base_mute})")
    check("mute rollback == baseline", rb["restored"]["mute"] == base_mute)
    print()

    # 4. dry-run: returns planned, FL unchanged ------------------------------
    safety.set_dry_run(True)
    before_dry = bridge.call(CMD_MIXER_GET_TRACK, {"index": 1})["vol_norm"]
    res = safety.safe_write(
        bridge,
        tool="mixer_set_volume",
        scope="mixer_track:1",
        command=CMD_MIXER_SET_VOLUME,
        params={"track": 1, "value": -20, "unit": "db"},
        build_restore=_vol_restore(1),
    )
    after_dry = bridge.call(CMD_MIXER_GET_TRACK, {"index": 1})["vol_norm"]
    print("dry_run write returned:", res)
    print(f"FL norm before {before_dry:.4f} | after {after_dry:.4f}")
    check("dry_run returns planned-only", res.get("dry_run") is True and "planned" in res)
    check("dry_run did NOT change FL", abs(before_dry - after_dry) <= 0.0001)
    safety.set_dry_run(False)
    print()

    print("PHASE 1A WRITE: ALL PASSED" if PASS else "PHASE 1A WRITE: FAILURES ABOVE")
    return 0 if PASS else 1


if __name__ == "__main__":
    sys.exit(main())
