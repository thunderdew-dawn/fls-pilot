#!/usr/bin/env python3
"""Offline unit tests for Phase 5 Plugin Params Pack.

Asserts that parameter resolution, param value retrieval, and preset navigation
limits are surfaced safely.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.tools import plugin as pl_tools  # noqa: E402

_P = _F = 0


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []
        self.mock_params = {
            "params": [
                {"i": 0, "name": "Mix Level", "v": 1.0, "s": "100%"},
                {"i": 1, "name": "Decay Time", "v": 0.5, "s": "3.5s"},
                {"i": 2, "name": "Bypass State", "v": 0.0, "s": "Off"},
            ]
        }
        self.mock_preset = {
            "plugin_name": "Fruity Reeverb 2",
            "name_f3": "Default Large Room",
            "name_f6": "Default Large Room",
            "preset_count": 12,
        }

    def call(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command == protocol.CMD_PLUGIN_GET_PARAMS:
            return self.mock_params
        if command == protocol.CMD_PLUGIN_GET_PARAM:
            idx = params.get("param", 0)
            for p in self.mock_params["params"]:
                if p["i"] == idx:
                    return p
            return {"i": idx, "name": "Unknown", "v": 0.0, "s": ""}
        if command in (protocol.CMD_PLUGIN_PRESET, protocol.CMD_PLUGIN_GET_PRESET_NAME):
            return self.mock_preset
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

    # Inject mock bridge
    from fl_studio_mcp import connection

    orig_get_bridge = connection.get_bridge
    connection.get_bridge = lambda: bridge
    pl_tools.get_bridge = lambda: bridge

    class MockMCP:
        def __init__(self):
            self.tools = {}

        def tool(self, annotations=None):
            def decorator(func):
                self.tools[func.__name__] = func
                return func

            return decorator

    mcp = MockMCP()
    pl_tools.register(mcp)
    fl_plugin_list_params = mcp.tools["fl_plugin_list_params"]
    fl_plugin_get_param = mcp.tools["fl_plugin_get_param"]
    fl_plugin_get_preset_name = mcp.tools["fl_plugin_get_preset_name"]
    fl_plugin_next_preset = mcp.tools["fl_plugin_next_preset"]
    fl_plugin_prev_preset = mcp.tools["fl_plugin_prev_preset"]

    try:
        print("Testing Parameter Resolution...")

        # Exact Index
        idx, name = pl_tools.resolve_param_index(bridge, 0, 0, 1)
        check("Exact index 1 resolved", idx == 1 and name == "Decay Time")

        # String Index
        idx, name = pl_tools.resolve_param_index(bridge, 0, 0, "1")
        check("String index '1' resolved", idx == 1 and name == "Decay Time")

        # Exact Name match (case-insensitive & stripped)
        idx, name = pl_tools.resolve_param_index(bridge, 0, 0, "decay time")
        check("Exact name 'decay time' resolved", idx == 1 and name == "Decay Time")

        # Substring Match
        idx, name = pl_tools.resolve_param_index(bridge, 0, 0, "decay")
        check("Substring 'decay' resolved to Decay Time", idx == 1 and name == "Decay Time")

        # Ambiguous Match
        try:
            pl_tools.resolve_param_index(bridge, 0, 0, "state")  # mix or bypass?
            # Wait, our mock has: "Mix Level", "Decay Time", "Bypass State"
            # "state" matches "Bypass State" (unique!)
            # Add a fake param to make "decay" ambiguous.
            bridge.mock_params["params"].append({"i": 3, "name": "Decay Size", "v": 0.5, "s": ""})
            pl_tools.resolve_param_index(bridge, 0, 0, "decay")  # Decay Time or Decay Size?
            check("Ambiguous 'decay' throws ParamNotFound", False)
        except pl_tools.ParamNotFound:
            check("Ambiguous 'decay' throws ParamNotFound", True)

        # Cleanup mock
        bridge.mock_params["params"].pop()

        # Not found
        try:
            pl_tools.resolve_param_index(bridge, 0, 0, "nonexistent")
            check("Nonexistent name throws ParamNotFound", False)
        except pl_tools.ParamNotFound:
            check("Nonexistent name throws ParamNotFound", True)

        print("\nTesting Get Parameter & Preset info...")

        # Test fl_plugin_list_params
        res_list = fl_plugin_list_params(0, 0)
        check("fl_plugin_list_params returned params list", "params" in res_list)

        # Test fl_plugin_get_param
        res_get = fl_plugin_get_param(0, 0, "decay")
        check("fl_plugin_get_param returned ok", res_get.get("ok") is True)
        check("param index is 1", res_get.get("param_index") == 1)
        check("param value is 0.5", res_get.get("value") == 0.5)

        # Test fl_plugin_get_preset_name
        res_preset = fl_plugin_get_preset_name(0, 0)
        check("fl_plugin_get_preset_name returned ok", res_preset.get("ok") is True)
        check("preset name is correct", res_preset.get("preset_name") == "Default Large Room")

        print("\nTesting Preset navigation safety limits...")

        # Clean recent changelog
        changelog = safety.get_changelog()
        while changelog.pop_last() is not None:
            pass

        res_next = fl_plugin_next_preset(0, 0)
        check("fl_plugin_next_preset is blocked", res_next.get("ok") is False)
        check("fl_plugin_next_preset is api-limited", res_next.get("api_limited") is True)
        check("fl_plugin_next_preset provides manual action", "manual_action" in res_next)

        res_prev = fl_plugin_prev_preset(0, 0)
        check("fl_plugin_prev_preset is blocked", res_prev.get("ok") is False)
        check("fl_plugin_prev_preset is api-limited", res_prev.get("api_limited") is True)

        rb_res = safety.rollback_last_change(bridge)
        check(
            "Blocked preset navigation does not create changelog entry",
            rb_res.get("ok") is False and rb_res.get("error") == "changelog is empty",
        )

    finally:
        connection.get_bridge = orig_get_bridge

    print(f"\nPhase 5 Offline test results: {_P} passed, {_F} failed.")
    return 1 if _F > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
