#!/usr/bin/env python3
"""Offline tests for channel organizer planning helpers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.tools import channels as channel_tools  # noqa: E402

_P = _F = 0


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []

    def call(self, command, params=None):
        self.calls.append((command, params or {}))
        if command == protocol.CMD_PLUGIN_LIST:
            return {"track": params["track"], "slots": []}
        return {}


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    status = "PASS" if cond else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")


def main() -> int:
    check("master-routed channel can be treated as assignment candidate",
          channel_tools._needs_assignment({"target_fx_track": 0}, include_master=True))
    check("master-routed channel can be excluded",
          not channel_tools._needs_assignment({"target_fx_track": 0}, include_master=False))
    check("unknown target needs assignment",
          channel_tools._needs_assignment({"target_fx_track": None}, include_master=False))
    check("normal mixer target does not need assignment",
          not channel_tools._needs_assignment({"target_fx_track": 5}, include_master=True))

    restore = channel_tools._target_restore(3, {"target_fx_track": 7})
    check("target restore uses prior mixer target",
          restore == {
              "command": protocol.CMD_CHANNEL_SET_TARGET,
              "params": {"channel": 3, "track": 7},
          })

    original_fetch = channel_tools.fetch_all_pages
    try:
        def fake_fetch(_bridge, command, _key):
            if command == protocol.CMD_MIXER_GET_ROUTING_ALL:
                return {"routing": [
                    {"i": 0, "name": "Master", "routes_to": []},
                    {"i": 1, "name": "Insert 1", "routes_to": [{"dst": 0}]},
                    {"i": 2, "name": "Insert 2", "routes_to": []},
                    {"i": 3, "name": "Drum Bus", "routes_to": []},
                ]}
            if command == protocol.CMD_CHANNEL_ROUTING_SUMMARY:
                return {"channels": [{"channel": 0, "target_mixer_track": 1}]}
            raise AssertionError(command)

        channel_tools.fetch_all_pages = fake_fetch
        bridge = FakeBridge()
        check("free mixer finder skips targeted track and named bus",
              channel_tools._find_free_mixer_track(bridge, start_track=1) == 2)
        check("plugin list checked for candidate", bridge.calls[-1] == (
            protocol.CMD_PLUGIN_LIST, {"track": 2}))
    finally:
        channel_tools.fetch_all_pages = original_fetch

    print(f"\n{_P} passed, {_F} failed")
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
