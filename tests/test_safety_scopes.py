#!/usr/bin/env python3
"""Offline tests for safety snapshot scopes and time signature tools.

Asserts that take_snapshot resolves the new scopes correctly and maps them
to the correct backend command parameters.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import protocol, safety  # noqa: E402

_P = _F = 0


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []

    def call(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        # Return mock payload values so callers can read back
        if command == protocol.CMD_GET_TIME_SIG:
            return {"numerator": 3, "denominator": 4}
        if command == protocol.CMD_SET_TIME_SIG:
            return {"numerator": params.get("numerator"), "denominator": params.get("denominator")}
        if command == protocol.CMD_MIXER_GET_EQ:
            return {"track": params.get("track"), "bands": [{"band": 0, "gain": 0.5}]}
        if command == protocol.CMD_MIXER_GET_SLOT:
            return {"track": params.get("track"), "slot": params.get("slot"), "valid": True}
        if command == protocol.CMD_MIXER_GET_TRACK_SLOTS:
            return {"track": params.get("track"), "enabled": True}
        if command == protocol.CMD_CHANNEL_GET:
            return {"index": params.get("index"), "name": "Kick", "target_fx": 1}
        if command == protocol.CMD_PLAYLIST_GET_TRACK:
            return {"index": params.get("index"), "name": "Audio"}
        if command == protocol.CMD_PATTERN_GET:
            return {"index": params.get("index"), "name": "Pat1"}
        if command == protocol.CMD_PATTERN_SELECTED:
            return {"selected": 1}
        if command == protocol.CMD_CHANNEL_GET_STEPS:
            return {
                "channel": params.get("channel"),
                "pattern": params.get("pattern", 1),
                "grid": [1, 0],
            }
        return {"ok": True, "command": command, "params": params}


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    status = "PASS" if cond else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")


def main() -> int:
    bridge = FakeBridge()

    # 1. Test channel snapshot scope
    res = safety.take_snapshot(bridge, "channel:4")
    check(
        "channel scope queries CMD_CHANNEL_GET",
        bridge.calls[-1] == (protocol.CMD_CHANNEL_GET, {"index": 4}),
    )
    check("channel returns mock name", res["name"] == "Kick")

    # 2. Test channel_steps snapshot scope
    res = safety.take_snapshot(bridge, "channel_steps:0")
    check(
        "channel_steps scope queries CMD_CHANNEL_GET_STEPS",
        bridge.calls[-1] == (protocol.CMD_CHANNEL_GET_STEPS, {"channel": 0}),
    )
    check("channel_steps returns mock grid", res["grid"] == [1, 0])
    res = safety.take_snapshot(bridge, "channel_steps:0:7")
    check(
        "channel_steps pattern scope includes pattern",
        bridge.calls[-1] == (protocol.CMD_CHANNEL_GET_STEPS, {"channel": 0, "pattern": 7}),
    )

    # 3. Test pattern snapshot scope
    res = safety.take_snapshot(bridge, "pattern:1")
    check(
        "pattern scope queries CMD_PATTERN_GET",
        bridge.calls[-1] == (protocol.CMD_PATTERN_GET, {"index": 1}),
    )
    check("pattern returns mock name", res["name"] == "Pat1")

    # 4. Test patterns_selected snapshot scope
    res = safety.take_snapshot(bridge, "patterns_selected")
    check(
        "patterns_selected scope queries CMD_PATTERN_SELECTED",
        bridge.calls[-1] == (protocol.CMD_PATTERN_SELECTED, {}),
    )

    # 5. Test playlist_track snapshot scope
    res = safety.take_snapshot(bridge, "playlist_track:2")
    check(
        "playlist_track scope queries CMD_PLAYLIST_GET_TRACK",
        bridge.calls[-1] == (protocol.CMD_PLAYLIST_GET_TRACK, {"index": 2}),
    )

    # 6. Test mixer_eq snapshot scope
    res = safety.take_snapshot(bridge, "mixer_eq:3")
    check(
        "mixer_eq scope queries CMD_MIXER_GET_EQ",
        bridge.calls[-1] == (protocol.CMD_MIXER_GET_EQ, {"track": 3}),
    )

    # 7. Test effect_slot snapshot scope
    res = safety.take_snapshot(bridge, "effect_slot:4:5")
    check(
        "effect_slot scope queries CMD_MIXER_GET_SLOT",
        bridge.calls[-1] == (protocol.CMD_MIXER_GET_SLOT, {"track": 4, "slot": 5}),
    )

    # 8. Test track_slots snapshot scope
    res = safety.take_snapshot(bridge, "track_slots:6")
    check(
        "track_slots scope queries CMD_MIXER_GET_TRACK_SLOTS",
        bridge.calls[-1] == (protocol.CMD_MIXER_GET_TRACK_SLOTS, {"track": 6}),
    )

    # 9. Test time_signature snapshot scope
    res = safety.take_snapshot(bridge, "time_signature")
    check(
        "time_signature scope queries CMD_GET_TIME_SIG",
        bridge.calls[-1] == (protocol.CMD_GET_TIME_SIG, {}),
    )
    check(
        "time_signature returns mock time signature",
        res["numerator"] == 3 and res["denominator"] == 4,
    )

    # 10. Test set_time_signature rollback flow simulation
    # Simulate safety.safe_write using our FakeBridge and a lambda restore builder
    res_set = safety.safe_write(
        bridge,
        tool="set_time_signature",
        scope="time_signature",
        command=protocol.CMD_SET_TIME_SIG,
        params={"numerator": 3, "denominator": 4},
        build_restore=lambda b: {
            "command": protocol.CMD_SET_TIME_SIG,
            "params": {"numerator": b["numerator"], "denominator": b["denominator"]},
        },
    )
    check("safe_write returns ok", res_set["ok"] is True)
    check("safe_write captured before state", res_set["before"]["numerator"] == 3)

    # We rollback the change using safety layer
    rollback_res = safety.rollback_last_change(bridge)
    check("rollback last succeeds", rollback_res["ok"] is True)
    check(
        "rollback replayed CMD_SET_TIME_SIG",
        bridge.calls[-1] == (protocol.CMD_SET_TIME_SIG, {"numerator": 3, "denominator": 4}),
    )

    print(f"\n{_P} passed, {_F} failed")
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
