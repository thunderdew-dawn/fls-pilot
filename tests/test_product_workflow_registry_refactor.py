#!/usr/bin/env python3
"""Focused tests for product workflow registry-backed write preparation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.tools import mix_doctor, routing  # noqa: E402


class MockMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, annotations=None):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


class MixFixBridge:
    def __init__(self) -> None:
        self.track = {"index": 4, "name": "Lead", "vol_norm": 0.75, "vol_db": -1.0}
        self.calls: list[tuple[str, dict]] = []

    def call(self, command: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        self.calls.append((command, params))
        if command == protocol.CMD_MIXER_GET_TRACK:
            return dict(self.track)
        if command == protocol.CMD_MIXER_SET_VOLUME:
            assert params["track"] == 4
            self.track["vol_db"] = float(params["value"])
            self.track["vol_norm"] = 0.5
            return dict(self.track)
        raise AssertionError(f"unexpected command: {command!r} params={params!r}")


def test_routing_write_entries_are_registry_prepared() -> None:
    route = routing._route_write_entry(2, 0, False)
    assert route["snap_scope"] == "route:2:0"
    assert route["read_scope"] == "route:2:0"
    assert route["command"] == protocol.CMD_MIXER_SET_ROUTE
    assert route["params"] == {"src": 2, "dst": 0, "enabled": False}
    assert route["verify"] == ("enabled", False)
    assert route["restore"]({"enabled": True}) == {
        "command": protocol.CMD_MIXER_SET_ROUTE,
        "params": {"src": 2, "dst": 0, "enabled": True},
    }

    rename = routing._bus_rename_entry(8, "DRUM_BUS")
    assert rename["snap_scope"] == "mixer_track:8"
    assert rename["read_scope"] == "mixer_track:8"
    assert rename["command"] == protocol.CMD_MIXER_SET_NAME
    assert rename["params"] == {"track": 8, "name": "DRUM_BUS"}
    assert rename["verify"] is None
    assert rename["restore"]({"name": "Insert 8"}) == {
        "command": protocol.CMD_MIXER_SET_NAME,
        "params": {"track": 8, "name": "Insert 8"},
    }


def test_mix_doctor_trim_volume_uses_registry_safe_write(monkeypatch, tmp_path) -> None:
    bridge = MixFixBridge()
    mcp = MockMCP()
    mix_doctor.register(mcp)
    monkeypatch.setattr(mix_doctor, "get_bridge", lambda: bridge)
    monkeypatch.setattr(safety, "_log", safety.ChangeLog(tmp_path / "changes.jsonl"))

    result = mcp.tools["fl_apply_mix_fix"]("trim_volume", track=4, target_db=-3.0)

    assert result["ok"] is True
    assert result["kind"] == "trim_volume"
    assert result["track"] == 4
    assert result["before_db"] == -1.0
    assert result["after_db"] == -3.0
    assert result["applied"] is True
    assert (protocol.CMD_MIXER_SET_VOLUME, {"track": 4, "value": -3.0, "unit": "db"}) in bridge.calls
