#!/usr/bin/env python3
"""Offline tests for Phase 2 Mixer Pack tools.

Asserts that mixer tools generate correct commands, snapshots,
and build accurate restore payloads.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import safety  # noqa: E402
from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.tools import phase1  # noqa: E402

_P = _F = 0


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []
        self.mock_selected_track = 3
        self.mock_track_data = {
            "i": 5,
            "name": "Insert 5",
            "pan": 0.0,
            "mute": False,
            "solo": False,
            "color": 0x808080,
            "dock_side": 1,
            "stereo_sep": 0.0,
            "vol_norm": 0.8,
            "vol_db": 0.0,
        }
        self.mock_routes = {
            "track": 5,
            "name": "Insert 5",
            "routes_to": [
                {"dst": 0, "dst_name": "Master", "level": 1.0},
                {"dst": 10, "dst_name": "Insert 10", "level": 0.5},
            ],
        }
        self.mock_peaks = {
            "track": 5,
            "peak_l": 0.5,
            "peak_r": 0.5,
            "peak_max": 0.5,
        }

    def call(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command == protocol.CMD_MIXER_SELECTED:
            return {"track": self.mock_selected_track}
        if command == protocol.CMD_MIXER_GET_TRACK:
            return self.mock_track_data
        if command == protocol.CMD_MIXER_GET_ROUTING:
            return self.mock_routes
        if command == protocol.CMD_MIXER_GET_PEAKS:
            return self.mock_peaks
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

    # Setup connection mock injection
    from fl_studio_mcp import connection
    orig_get_bridge = connection.get_bridge
    connection.get_bridge = lambda: bridge

    try:
        # 1. Test take_snapshot for mixer_selection
        res_sel = safety.take_snapshot(bridge, "mixer_selection")
        check(
            "take_snapshot queries CMD_MIXER_SELECTED",
            bridge.calls[-1] == (protocol.CMD_MIXER_SELECTED, {}),
        )
        check("take_snapshot returned selected track index", res_sel["track"] == 3)

        # 2. Test take_snapshot for mixer_track
        res_track = safety.take_snapshot(bridge, "mixer_track:5")
        check(
            "take_snapshot queries CMD_MIXER_GET_TRACK",
            bridge.calls[-1] == (protocol.CMD_MIXER_GET_TRACK, {"index": 5}),
        )
        check("take_snapshot returned track name", res_track["name"] == "Insert 5")
        check("take_snapshot returned dock_side", res_track["dock_side"] == 1)

        # 3. Test take_snapshot for route
        res_route = safety.take_snapshot(bridge, "route:5:10")
        check(
            "take_snapshot queries CMD_MIXER_GET_ROUTING",
            bridge.calls[-1] == (protocol.CMD_MIXER_GET_ROUTING, {"track": 5}),
        )
        check("take_snapshot returned route enabled is True", res_route["enabled"] is True)

        # 4. Test safe_write with mixer_select_track
        res_write_sel = safety.safe_write(
            bridge,
            tool="mixer_select_track",
            scope="mixer_selection",
            command=protocol.CMD_MIXER_SELECT_TRACK,
            params={"track": 7},
            verify=("track", 7),
            build_restore=lambda b: {
                "command": protocol.CMD_MIXER_SELECT_TRACK,
                "params": {"track": b["track"]},
            },
        )
        check("safe_write select track returned ok", res_write_sel["ok"] is True)
        check("safe_write captured before selection", res_write_sel["before"]["track"] == 3)

        # Rollback selection
        res_rollback_sel = safety.rollback_last_change(bridge)
        check("rollback select track returned ok", res_rollback_sel["ok"] is True)
        check(
            "rollback replayed CMD_MIXER_SELECT_TRACK with pre-change track index 3",
            bridge.calls[-1] == (protocol.CMD_MIXER_SELECT_TRACK, {"track": 3}),
        )

        # 5. Test safe_write with mixer_set_route
        res_write_route = safety.safe_write(
            bridge,
            tool="mixer_set_route",
            scope="route:5:10",
            command=protocol.CMD_MIXER_SET_ROUTE,
            params={"src": 5, "dst": 10, "enabled": False},
            verify=("enabled", False),
            build_restore=lambda b: {
                "command": protocol.CMD_MIXER_SET_ROUTE,
                "params": {"src": 5, "dst": 10, "enabled": b["enabled"]},
            },
        )
        check("safe_write set route returned ok", res_write_route["ok"] is True)
        check("safe_write captured before route enabled is True", res_write_route["before"]["enabled"] is True)

        # Rollback route
        res_rollback_route = safety.rollback_last_change(bridge)
        check("rollback set route returned ok", res_rollback_route["ok"] is True)
        check(
            "rollback replayed CMD_MIXER_SET_ROUTE with pre-change enabled status True",
            bridge.calls[-1] == (protocol.CMD_MIXER_SET_ROUTE, {"src": 5, "dst": 10, "enabled": True}),
        )

        # 5.5 Test safe_write with fl_mixer_set_stereo_separation
        res_write_sep = safety.safe_write(
            bridge,
            tool="mixer_set_stereo_separation",
            scope="mixer_track:5",
            command=protocol.CMD_MIXER_SET_STEREO_SEP,
            params={"track": 5, "value": 0.5},
            build_restore=lambda b: {
                "command": protocol.CMD_MIXER_SET_STEREO_SEP,
                "params": {"track": 5, "value": b["stereo_sep"]},
            },
        )
        check("safe_write set stereo separation returned ok", res_write_sep["ok"] is True)
        check("safe_write captured before stereo_sep is 0.0", res_write_sep["before"]["stereo_sep"] == 0.0)

        # Rollback stereo sep
        res_rollback_sep = safety.rollback_last_change(bridge)
        check("rollback set stereo separation returned ok", res_rollback_sep["ok"] is True)
        check(
            "rollback replayed CMD_MIXER_SET_STEREO_SEP with pre-change separation 0.0",
            bridge.calls[-1] == (protocol.CMD_MIXER_SET_STEREO_SEP, {"track": 5, "value": 0.0}),
        )

        # 6. Test fl_mixer_get_levels sampling
        from fl_studio_mcp.music import levels
        res_levels = levels.measure_track_level(bridge, 5, samples=2, interval_ms=1)
        check("measure_track_level returned playing is True", res_levels["playing"] is True)
        check("measure_track_level returned avg_db", res_levels["avg_db"] == -6.02)
        check("measure_track_level returned peak_db", res_levels["peak_db"] == -6.02)

    finally:
        connection.get_bridge = orig_get_bridge

    print(f"\n{_P} passed, {_F} failed")
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
