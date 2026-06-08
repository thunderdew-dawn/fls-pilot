#!/usr/bin/env python3
"""Offline tests for step sequencer tools.

Asserts that step sequencer tools generate correct commands, snapshots,
and build accurate restore payloads.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import protocol, safety  # noqa: E402
from fls_pilot.tools import channels  # noqa: E402

_P = _F = 0


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []
        self.mock_grid = [True, False, True, False]
        self.mock_vel = [0.8, 0.5, 0.9, 0.1]
        self.mock_pan = [0.0, -0.5, 0.5, 0.0]
        self.mock_shift = [0.0, 0.1, 0.0, 0.2]
        self.mock_rep = [0, 1, 0, 2]

    def call(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command == protocol.CMD_CHANNEL_GET_STEPS:
            return {
                "channel": params.get("channel"),
                "pattern": params.get("pattern", 1),
                "grid": self.mock_grid,
                "vel": self.mock_vel,
                "pan": self.mock_pan,
                "shift": self.mock_shift,
                "rep": self.mock_rep,
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

    # 1. Test take_snapshot for channel_steps
    res = safety.take_snapshot(bridge, "channel_steps:2")
    check(
        "take_snapshot queries CMD_CHANNEL_GET_STEPS",
        bridge.calls[-1] == (protocol.CMD_CHANNEL_GET_STEPS, {"channel": 2}),
    )
    check("take_snapshot returned grid", res["grid"] == [True, False, True, False])
    check("take_snapshot returned vel", res["vel"] == [0.8, 0.5, 0.9, 0.1])

    res_pat = safety.take_snapshot(bridge, "channel_steps:2:5")
    check(
        "pattern-scoped take_snapshot passes pattern",
        bridge.calls[-1] == (protocol.CMD_CHANNEL_GET_STEPS, {"channel": 2, "pattern": 5}),
    )
    check("pattern-scoped snapshot records pattern", res_pat["pattern"] == 5)

    # 2. Test _steps_restore helper logic
    restore_val = channels._steps_restore(2, res)
    check(
        "restore cmd is CMD_CHANNEL_SET_STEPS",
        restore_val["command"] == protocol.CMD_CHANNEL_SET_STEPS,
    )
    check("restore target channel is 2", restore_val["params"]["channel"] == 2)
    check("restore keeps original pattern", restore_val["params"]["pattern"] == 1)
    check("restore step 0 value is True", restore_val["params"]["steps"][0]["value"] is True)
    check("restore step 0 velocity is 0.8", restore_val["params"]["steps"][0]["velocity"] == 0.8)
    check("restore step 1 value is False", restore_val["params"]["steps"][1]["value"] is False)
    check("restore step 1 pan is -0.5", restore_val["params"]["steps"][1]["pan"] == -0.5)

    # 3. Test safe_write with channel_set_steps
    # Simulate writing steps 1 and 3 on channel 2
    res_write = safety.safe_write(
        bridge,
        tool="channel_set_steps",
        scope="channel_steps:2:1",
        command=protocol.CMD_CHANNEL_SET_STEPS,
        params={
            "channel": 2,
            "pattern": 1,
            "steps": [
                {"step": 1, "value": True, "velocity": 1.0},
                {"step": 3, "value": True, "pan": 0.0},
            ],
        },
        build_restore=lambda b: channels._steps_restore(2, b),
    )
    check("safe_write returned ok", res_write["ok"] is True)
    check(
        "safe_write captured before state",
        res_write["before"]["grid"] == [True, False, True, False],
    )

    # Replay rollback
    res_rollback = safety.rollback_last_change(bridge)
    check("rollback last returned ok", res_rollback["ok"] is True)
    check(
        "rollback replayed CMD_CHANNEL_SET_STEPS with all elements restored",
        bridge.calls[-1][0] == protocol.CMD_CHANNEL_SET_STEPS
        and len(bridge.calls[-1][1]["steps"]) == 4,
    )

    print(f"\n{_P} passed, {_F} failed")
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
