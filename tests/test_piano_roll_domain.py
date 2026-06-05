#!/usr/bin/env python3
"""Focused tests for the consolidated Piano Roll domain tool (Slice 10)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.tools import pianoroll as pianoroll_tools  # noqa: E402


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.last_notes = None
        self.last_mode = None
        self.last_quantize = None
        self.last_snap = None
        self.last_transpose = None
        self.last_marker_add = None
        self.last_channel = None
        self.last_pattern = None

    def call(self, command: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        self.calls.append((command, params))
        if command == protocol.CMD_ENSURE_PIANO_ROLL:
            return {"ok": True, "retargeted": bool(params), **params}
        if command == protocol.CMD_GENERAL_UNDO:
            return {"ok": True, "undid": True}
        raise AssertionError(f"unexpected command: {command!r} params={params!r}")

    def apply_notes(
        self,
        notes,
        mode="replace",
        trigger=True,
        quantize=None,
        snap_ends=False,
        transpose=None,
        duplicate_bars=None,
        velocity_ramp=None,
        marker_add=None,
        marker_clear=False,
        channel=None,
        pattern=None,
    ):
        self.last_notes = notes
        self.last_mode = mode
        self.last_quantize = quantize
        self.last_snap = snap_ends
        self.last_transpose = transpose
        self.last_marker_add = marker_add
        self.last_channel = channel
        self.last_pattern = pattern
        return {
            "ok": True,
            "count": len(notes),
            "triggered": trigger,
            "action": "apply_notes",
            "marker_clear": marker_clear,
        }


def _unwrap(result):
    for attr in ("data", "structured_content", "structuredContent"):
        value = getattr(result, attr, None)
        if value is not None:
            return value
    if isinstance(result, (list, tuple)) and result:
        first = result[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            return json.loads(text)
        return _unwrap(first)
    return result


@pytest.fixture
def piano_roll_mcp(monkeypatch, tmp_path):
    bridge = FakeBridge()
    monkeypatch.setattr(pianoroll_tools, "get_bridge", lambda: bridge)
    safety._log = safety.ChangeLog(tmp_path / "changes.jsonl")
    mcp = FastMCP(name="piano-roll-test")
    pianoroll_tools.register(mcp)
    return mcp, bridge


def _call(mcp: FastMCP, action: str, params: dict | None = None):
    args = {"action": action}
    if params is not None:
        args["params"] = params
    return _unwrap(asyncio.run(mcp.call_tool("fl_piano_roll", args)))


def test_piano_roll_domain_writes_notes_with_undo_backing(piano_roll_mcp) -> None:
    mcp, bridge = piano_roll_mcp

    result = _call(
        mcp,
        "write_notes",
        {
            "notes": [{"pitch": 60, "time_bars": 0.13, "length_bars": 0.25, "velocity": 0.8}],
            "mode": "append",
            "quantize": 0.125,
            "channel": 2,
            "pattern": 3,
        },
    )

    assert result["ok"] is True
    assert result["before"] == {"undo_backed": True, "note_readback_available": False}
    assert bridge.calls == [(protocol.CMD_ENSURE_PIANO_ROLL, {"channel": 2, "pattern": 3})]
    assert bridge.last_mode == "append"
    assert bridge.last_notes == [
        {"pitch": 60, "time_bars": 0.125, "length_bars": 0.25, "velocity": 0.8}
    ]
    assert bridge.last_channel == 2
    assert bridge.last_pattern == 3


def test_piano_roll_domain_transform_action(piano_roll_mcp) -> None:
    mcp, bridge = piano_roll_mcp

    result = _call(mcp, "transpose", {"semitones": -2})

    assert result["ok"] is True
    assert bridge.calls == [(protocol.CMD_ENSURE_PIANO_ROLL, {})]
    assert bridge.last_transpose == -2


def test_piano_roll_domain_marker_action(piano_roll_mcp) -> None:
    mcp, bridge = piano_roll_mcp

    result = _call(mcp, "add_marker", {"time_bars": 2.0, "name": "Verse", "mode": 0})

    assert result["ok"] is True
    assert bridge.calls == [(protocol.CMD_ENSURE_PIANO_ROLL, {})]
    assert bridge.last_marker_add == {"time_bars": 2.0, "name": "Verse", "mode": 0}


def test_piano_roll_domain_rejects_invalid_action(piano_roll_mcp) -> None:
    mcp, _bridge = piano_roll_mcp

    with pytest.raises(Exception, match="unknown piano roll action"):
        _call(mcp, "delete_selected", {})


def test_piano_roll_domain_rejects_invalid_parameters(piano_roll_mcp) -> None:
    mcp, _bridge = piano_roll_mcp

    with pytest.raises(Exception, match="notes must be a list"):
        _call(mcp, "write_notes", {"notes": "C5"})

    with pytest.raises(Exception, match="start must be <= 1.0"):
        _call(mcp, "velocity_ramp", {"start": 1.2, "end": 0.8})


def test_piano_roll_domain_reports_readback_limit(piano_roll_mcp) -> None:
    mcp, bridge = piano_roll_mcp

    result = _call(mcp, "get_notes")
    probe = _call(mcp, "probe_return_channel")

    assert result["ok"] is False
    assert result["status"] == "api-limited"
    assert result["readback_available"] is False
    assert probe["ok"] is True
    assert probe["status"] == "api-limited"
    assert bridge.calls == []
