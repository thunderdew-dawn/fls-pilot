#!/usr/bin/env python3
"""Offline tests for project doctor reports and dry-run fix plan."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.tools import project_doctor as pd  # noqa: E402

_P = _F = 0


class FakeBridge:
    def call(self, command, params=None):
        params = params or {}
        if command == protocol.CMD_GET_PROJECT_STATE:
            return {"playing": False, "tempo": 140.0}
        if command == protocol.CMD_CHANNEL_GET:
            idx = int(params.get("index", 0))
            return {
                "i": idx,
                "name": "" if idx == 2 else f"Chan {idx}",
                "target_fx_track": 0 if idx == 0 else 1,
            }
        raise RuntimeError(f"unexpected call: {command}")


def _fake_fetch_all_pages(_bridge, command, key):
    if command == protocol.CMD_CHANNEL_LIST and key == "channels":
        return {"channels": [{"i": 0, "name": "Kick"}, {"i": 2, "name": ""}]}
    if command == protocol.CMD_PATTERN_LIST and key == "patterns":
        return {
            "patterns": [
                {"index": 1, "name": "Lead", "length": 16},
                {"index": 2, "name": "Lead", "length": 16},
                {"index": 3, "name": "", "length": 8},
            ]
        }
    if command == protocol.CMD_PLAYLIST_LIST_TRACKS and key == "tracks":
        return {"tracks": [{"index": 1, "name": "PL1", "mute": True}]}
    if command == protocol.CMD_MIXER_LIST_TRACKS and key == "tracks":
        return {"tracks": [{"i": 1, "name": "Bus A"}, {"i": 2, "name": "Bus A"}]}
    raise RuntimeError(f"unexpected fetch: {command}/{key}")


class MockMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, annotations=None):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


def check(label, cond):
    global _P, _F
    if cond:
        _P += 1
        print(f"[PASS] {label}")
    else:
        _F += 1
        print(f"[FAIL] {label}")


def main() -> int:
    mcp = MockMCP()
    pd.register(mcp)
    pd.get_bridge = lambda: FakeBridge()
    pd.fetch_all_pages = _fake_fetch_all_pages

    report = mcp.tools["fl_project_health_report"]()
    check("health report ok", report.get("ok") is True)
    check("health report has findings", report.get("summary", {}).get("findings", 0) >= 1)

    readiness = mcp.tools["fl_export_readiness_report"]()
    check("readiness report ok", readiness.get("ok") is True)
    check("readiness marks project not ready", readiness.get("ready") is False)

    plan = mcp.tools["fl_project_dry_run_fix_plan"]()
    check("dry-run fix plan ok", plan.get("ok") is True)
    check("dry-run flag true", plan.get("dry_run") is True)
    check("has planned actions", len(plan.get("plan", [])) > 0)
    check(
        "contains rollback-safe channel assignment action",
        any(a.get("tool") == "fl_assign_channel_to_free_mixer_track" for a in plan.get("plan", [])),
    )

    print(f"\nProject doctor offline tests: {_P} passed, {_F} failed.")
    return 1 if _F else 0


if __name__ == "__main__":
    raise SystemExit(main())
