#!/usr/bin/env python3
"""Offline tests for dynamic mixer-track guards and read retries."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.connection import FLTimeout, fetch_all_pages  # noqa: E402
from fl_studio_mcp.tools import channels as channel_tools  # noqa: E402
from fl_studio_mcp.tools import plugin as plugin_tools  # noqa: E402
from fl_studio_mcp.tools import targets  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{' -- ' + detail if detail else ''}")


class DynamicBridge:
    def __init__(self, count=4):
        self.count = count
        self.calls = []
        self.timeouts = 0

    def call(self, command, params=None, **_kwargs):
        params = params or {}
        self.calls.append((command, params))
        if command == protocol.CMD_GET_PROJECT_STATE:
            return {"mixer_track_count": self.count}
        if command == protocol.CMD_MIXER_GET_ROUTING_ALL:
            return {
                "total": self.count,
                "start": 0,
                "next_start": None,
                "routing": [
                    {
                        "i": i,
                        "name": "Master" if i == 0 else f"Insert {i}",
                        "routes_to": [],
                    }
                    for i in range(self.count)
                ],
            }
        if command == protocol.CMD_CHANNEL_ROUTING_SUMMARY:
            return {"total": 0, "start": 0, "next_start": None, "channels": []}
        if command == protocol.CMD_PLUGIN_LIST:
            return {"track": params["track"], "slots": []}
        if command == protocol.CMD_PLUGIN_GET_PARAM:
            return {"name": "Gain", "v": 0.5, "s": "0.0dB"}
        if command == protocol.CMD_PLUGIN_GET_PARAMS:
            return {
                "total": 1,
                "start": params.get("start", 0),
                "next_start": None,
                "params": [{"i": 0, "name": "Gain", "v": 0.5, "s": "0.0dB"}],
            }
        return {}


class RetryBridge:
    def __init__(self):
        self.calls = 0

    def call(self, command, params=None, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            raise FLTimeout("late read")
        return {"total": 1, "start": 0, "next_start": None, "rows": [{"ok": True}]}


class MockMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, annotations=None):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def main() -> int:
    bridge = DynamicBridge(count=4)
    err = targets.mixer_track_error(bridge, 49, purpose="test")
    check(
        "out-of-range mixer track reports dynamic count",
        err is not None and err["mixer_track_count"] == 4,
    )
    check("in-range mixer track passes", targets.mixer_track_error(bridge, 3) is None)

    no_free = channel_tools.no_free_mixer_track_response(bridge, start_track=4)
    check(
        "no-free response marks mixer creation as probe-needed",
        no_free.get("probe_needed") is True,
    )

    mcp = MockMCP()
    channel_tools.register(mcp)
    plugin_tools.register(mcp)
    channel_tools.get_bridge = lambda: bridge
    plugin_tools.get_bridge = lambda: bridge

    out = mcp.tools["fl_set_channel_mixer_track"](0, 49)
    check(
        "channel target guard blocks missing dynamic track",
        out.get("ok") is False and out.get("dynamic_mixer_tracks") is True,
    )

    out = mcp.tools["fl_plugin_get_param"](49, 0, 0)
    check(
        "plugin param read guard blocks missing dynamic track",
        out.get("ok") is False and out.get("mixer_track_count") == 4,
    )

    retry_bridge = RetryBridge()
    paged = fetch_all_pages(retry_bridge, "slow_read", "rows", attempts=2)
    check(
        "read pagination retries a transient timeout",
        retry_bridge.calls == 2 and paged["rows"] == [{"ok": True}],
    )

    print(f"\n{_P} passed, {_F} failed")
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
