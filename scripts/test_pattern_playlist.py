#!/usr/bin/env python3
"""Offline unit tests for Phase 3 Patterns & Playlist Pack.

Asserts that pattern and playlist tools generate correct commands,
snapshots, and build accurate restore payloads.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import safety  # noqa: E402
from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.tools import phase3  # noqa: E402

_P = _F = 0


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []
        self.mock_selected_pattern = 1
        self.mock_pattern_data = {
            "index": 2,
            "name": "Kick Pattern",
            "color": {"int": 16711680, "hex": "#FF0000", "r": 255, "g": 0, "b": 0},
            "length": 16,
        }
        self.mock_playlist_track = {
            "index": 3,
            "name": "Synth Track",
            "color": {"int": 65280, "hex": "#00FF00", "r": 0, "g": 255, "b": 0},
            "mute": True,
            "solo": False,
            "selected": True,
        }

    def call(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command == protocol.CMD_PATTERN_SELECTED:
            return {"selected": self.mock_selected_pattern}
        if command == protocol.CMD_PATTERN_GET:
            return self.mock_pattern_data
        if command == protocol.CMD_PLAYLIST_GET_TRACK:
            return self.mock_playlist_track
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

    # Inject connection mock
    from fl_studio_mcp import connection
    orig_get_bridge = connection.get_bridge
    connection.get_bridge = lambda: bridge

    try:
        print("Starting offline tests for Phase 3 Patterns & Playlist...")

        # 1. Snapshot validation
        res_pat_sel = safety.take_snapshot(bridge, "patterns_selected")
        check(
            "take_snapshot queries CMD_PATTERN_SELECTED",
            bridge.calls[-1] == (protocol.CMD_PATTERN_SELECTED, {}),
        )
        check("take_snapshot returned selected pattern index", res_pat_sel["selected"] == 1)

        res_pat = safety.take_snapshot(bridge, "pattern:2")
        check(
            "take_snapshot queries CMD_PATTERN_GET",
            bridge.calls[-1] == (protocol.CMD_PATTERN_GET, {"index": 2}),
        )
        check("take_snapshot pattern name match", res_pat["name"] == "Kick Pattern")

        res_play = safety.take_snapshot(bridge, "playlist_track:3")
        check(
            "take_snapshot queries CMD_PLAYLIST_GET_TRACK",
            bridge.calls[-1] == (protocol.CMD_PLAYLIST_GET_TRACK, {"index": 3}),
        )
        check("take_snapshot playlist track name match", res_play["name"] == "Synth Track")
        check("take_snapshot playlist track mute is True", res_play["mute"] is True)

        # 2. Test safe_write with pattern select
        res_write_pat_sel = safety.safe_write(
            bridge,
            tool="pattern_select",
            scope="patterns_selected",
            command=protocol.CMD_PATTERN_SELECT,
            params={"index": 4},
            build_restore=lambda b: {
                "command": protocol.CMD_PATTERN_SELECT,
                "params": {"index": b["selected"]},
            },
        )
        check("safe_write pattern_select returned ok", res_write_pat_sel["ok"] is True)
        check("safe_write captured previous pattern selection", res_write_pat_sel["before"]["selected"] == 1)

        # Rollback selection
        res_rollback_pat_sel = safety.rollback_last_change(bridge)
        check("rollback pattern_select returned ok", res_rollback_pat_sel["ok"] is True)
        check(
            "rollback replayed CMD_PATTERN_SELECT with pre-change pattern 1",
            bridge.calls[-1] == (protocol.CMD_PATTERN_SELECT, {"index": 1}),
        )

        # 3. Test safe_write with pattern rename
        res_write_pat_rename = safety.safe_write(
            bridge,
            tool="pattern_rename",
            scope="pattern:2",
            command=protocol.CMD_PATTERN_RENAME,
            params={"index": 2, "name": "New Pattern Name"},
            build_restore=lambda b: {
                "command": protocol.CMD_PATTERN_RENAME,
                "params": {"index": 2, "name": b["name"]},
            },
        )
        check("safe_write pattern_rename returned ok", res_write_pat_rename["ok"] is True)
        check("safe_write captured pre-change pattern name", res_write_pat_rename["before"]["name"] == "Kick Pattern")

        # Rollback rename
        res_rollback_pat_rename = safety.rollback_last_change(bridge)
        check("rollback pattern_rename returned ok", res_rollback_pat_rename["ok"] is True)
        check(
            "rollback replayed CMD_PATTERN_RENAME with pre-change name 'Kick Pattern'",
            bridge.calls[-1] == (protocol.CMD_PATTERN_RENAME, {"index": 2, "name": "Kick Pattern"}),
        )

        # 4. Test safe_write with playlist track mute
        res_write_mute = safety.safe_write(
            bridge,
            tool="playlist_set_mute",
            scope="playlist_track:3",
            command=protocol.CMD_PLAYLIST_SET_MUTE,
            params={"index": 3, "state": False},
            verify=("mute", False),
            build_restore=lambda b: {
                "command": protocol.CMD_PLAYLIST_SET_MUTE,
                "params": {"index": 3, "state": b["mute"]},
            },
        )
        check("safe_write set_mute returned ok", res_write_mute["ok"] is True)
        check("safe_write captured pre-change mute state", res_write_mute["before"]["mute"] is True)

        # Rollback mute
        res_rollback_mute = safety.rollback_last_change(bridge)
        check("rollback set_mute returned ok", res_rollback_mute["ok"] is True)
        check(
            "rollback replayed CMD_PLAYLIST_SET_MUTE with state True",
            bridge.calls[-1] == (protocol.CMD_PLAYLIST_SET_MUTE, {"index": 3, "state": True}),
        )

        # 5. Test safe_write with playlist track color
        res_write_color = safety.safe_write(
            bridge,
            tool="playlist_set_color",
            scope="playlist_track:3",
            command=protocol.CMD_PLAYLIST_SET_COLOR,
            params={"index": 3, "r": 255, "g": 0, "b": 0},
            build_restore=lambda b: {
                "command": protocol.CMD_PLAYLIST_SET_COLOR,
                "params": {"index": 3, "color": b["color"]["int"]},
            },
        )
        check("safe_write set_color returned ok", res_write_color["ok"] is True)
        check("safe_write captured pre-change color int", res_write_color["before"]["color"]["int"] == 65280)

        # Rollback color
        res_rollback_color = safety.rollback_last_change(bridge)
        check("rollback set_color returned ok", res_rollback_color["ok"] is True)
        check(
            "rollback replayed CMD_PLAYLIST_SET_COLOR with pre-change color 65280",
            bridge.calls[-1] == (protocol.CMD_PLAYLIST_SET_COLOR, {"index": 3, "color": 65280}),
        )

    finally:
        connection.get_bridge = orig_get_bridge

    print(f"\nPhase 3 Offline test results: {_P} passed, {_F} failed.")
    return 1 if _F > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
