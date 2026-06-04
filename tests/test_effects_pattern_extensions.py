#!/usr/bin/env python3
"""Offline tests for pattern extensions + effect slot/EQ tools.

Covers command mapping and rollback payload generation through safety.safe_write.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402

_P = _F = 0


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []
        self.pattern = {
            "index": 4,
            "name": "Lead",
            "color": {"int": 255, "hex": "#0000FF", "r": 0, "g": 0, "b": 255},
            "length": 16,
        }
        self.slot = {
            "track": 5,
            "slot": 2,
            "valid": True,
            "name": "Fruity EQ 2",
            "mix": 0.65,
            "enabled": True,
        }
        self.track_slots = {"track": 5, "enabled": True}
        self.eq = {
            "track": 5,
            "bands": [
                {"band": 0, "gain": 0.1, "frequency": 0.3, "bandwidth": 1.0, "type": 0},
                {"band": 1, "gain": 0.0, "frequency": 0.5, "bandwidth": 1.0, "type": 0},
                {"band": 2, "gain": -0.1, "frequency": 0.8, "bandwidth": 1.2, "type": 0},
            ],
        }

    def call(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command == protocol.CMD_PATTERN_GET:
            return dict(self.pattern)
        if command == protocol.CMD_PATTERN_FIND_EMPTY:
            return {"index": 12, "pattern_count": 11}
        if command == protocol.CMD_PATTERN_SET_COLOR and "color" in params:
            self.pattern["color"]["int"] = int(params["color"])
            return dict(self.pattern)
        if command == protocol.CMD_PATTERN_SET_LENGTH:
            self.pattern["length"] = float(params["beats"])
            return {
                "index": self.pattern["index"],
                "beats": self.pattern["length"],
                "steps": int(self.pattern["length"] * 4),
            }
        if command == protocol.CMD_MIXER_GET_SLOT:
            return dict(self.slot)
        if command == protocol.CMD_MIXER_SET_SLOT_MIX:
            self.slot["mix"] = float(params["mix"])
            return dict(self.slot)
        if command == protocol.CMD_MIXER_GET_TRACK_SLOTS:
            return dict(self.track_slots)
        if command == protocol.CMD_MIXER_SET_TRACK_SLOTS:
            self.track_slots["enabled"] = bool(params["enabled"])
            return dict(self.track_slots)
        if command == protocol.CMD_MIXER_SET_SLOT_ENABLED:
            self.slot["enabled"] = bool(params["enabled"])
            return dict(self.slot)
        if command == protocol.CMD_MIXER_GET_EQ:
            return dict(self.eq)
        if command == protocol.CMD_MIXER_SET_EQ:
            b = int(params["band"])
            for row in self.eq["bands"]:
                if row["band"] == b:
                    row.update(
                        gain=float(params.get("gain", row["gain"])),
                        frequency=float(params.get("frequency", row["frequency"])),
                        bandwidth=float(params.get("bandwidth", row["bandwidth"])),
                        type=int(params.get("type", row["type"])),
                    )
            return dict(self.eq)
        return {"ok": True}


def check(label, cond):
    global _P, _F
    if cond:
        _P += 1
        print(f"[PASS] {label}")
    else:
        _F += 1
        print(f"[FAIL] {label}")


def main() -> int:
    b = FakeBridge()

    # Pattern color rollback payload
    res = safety.safe_write(
        b,
        tool="pattern_set_color",
        scope="pattern:4",
        command=protocol.CMD_PATTERN_SET_COLOR,
        params={"index": 4, "color": 12345},
        build_restore=lambda before: {
            "command": protocol.CMD_PATTERN_SET_COLOR,
            "params": {"index": 4, "color": before["color"]["int"]},
        },
    )
    check("pattern_set_color safe_write ok", res.get("ok") is True)
    rb = safety.rollback_last_change(b)
    check("pattern_set_color rollback ok", rb.get("ok") is True)

    # Slot mix rollback payload
    res = safety.safe_write(
        b,
        tool="effect_set_slot_mix",
        scope="effect_slot:5:2",
        command=protocol.CMD_MIXER_SET_SLOT_MIX,
        params={"track": 5, "slot": 2, "mix": 0.2},
        build_restore=lambda before: {
            "command": protocol.CMD_MIXER_SET_SLOT_MIX,
            "params": {"track": 5, "slot": 2, "mix": before["mix"]},
        },
    )
    check("effect_set_slot_mix safe_write ok", res.get("ok") is True)
    rb = safety.rollback_last_change(b)
    check("effect_set_slot_mix rollback ok", rb.get("ok") is True)

    # Track slots enable rollback payload
    res = safety.safe_write(
        b,
        tool="effect_set_track_slots_enabled",
        scope="track_slots:5",
        command=protocol.CMD_MIXER_SET_TRACK_SLOTS,
        params={"track": 5, "enabled": False},
        build_restore=lambda before: {
            "command": protocol.CMD_MIXER_SET_TRACK_SLOTS,
            "params": {"track": 5, "enabled": before["enabled"]},
        },
    )
    check("effect_set_track_slots_enabled safe_write ok", res.get("ok") is True)
    rb = safety.rollback_last_change(b)
    check("effect_set_track_slots_enabled rollback ok", rb.get("ok") is True)

    print(f"\nResults: {_P} passed, {_F} failed")
    return 1 if _F else 0


if __name__ == "__main__":
    raise SystemExit(main())
