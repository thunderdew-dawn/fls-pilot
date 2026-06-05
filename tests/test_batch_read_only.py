#!/usr/bin/env python3
"""Focused tests for read-only fl_batch (Slice 11)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.tools import batch as batch_tools  # noqa: E402


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.tempo = 120.0
        self.tracks = {
            1: {"index": 1, "name": "Kick", "vol_norm": 0.8},
            2: {"index": 2, "name": "Snare", "vol_norm": 0.7},
        }

    def call(self, command: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        self.calls.append((command, params))
        if command == protocol.CMD_GET_TEMPO:
            return {"bpm": self.tempo}
        if command == protocol.CMD_MIXER_GET_TRACK:
            track = params["index"]
            if track == 99:
                raise RuntimeError("track 99 unavailable")
            return dict(self.tracks[track])
        if command == protocol.CMD_CHANNEL_SELECTED:
            return {"selected": 3}
        raise AssertionError(f"unexpected command: {command!r} params={params!r}")


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
def batch_mcp(monkeypatch):
    bridge = FakeBridge()
    monkeypatch.setattr(batch_tools, "get_bridge", lambda: bridge)
    mcp = FastMCP(name="batch-test")
    batch_tools.register(mcp)
    return mcp, bridge


def _call(mcp: FastMCP, operations: list[dict], continue_on_error: bool = False):
    return _unwrap(
        asyncio.run(
            mcp.call_tool(
                "fl_batch",
                {"operations": operations, "continue_on_error": continue_on_error},
            )
        )
    )


def test_batch_read_only_success(batch_mcp) -> None:
    mcp, bridge = batch_mcp

    result = _call(
        mcp,
        [
            {"domain": "transport", "action": "get_tempo"},
            {"domain": "mixer", "action": "get", "params": {"track": 1}},
            {"domain": "channel", "action": "get_selected"},
        ],
    )

    assert result["ok"] is True
    assert result["count"] == 3
    assert result["completed"] == 3
    assert [row["result"] for row in result["results"]] == [
        {"bpm": 120.0},
        {"index": 1, "name": "Kick", "vol_norm": 0.8},
        {"selected": 3},
    ]
    assert bridge.calls == [
        (protocol.CMD_GET_TEMPO, {}),
        (protocol.CMD_MIXER_GET_TRACK, {"index": 1}),
        (protocol.CMD_CHANNEL_SELECTED, {}),
    ]


def test_batch_rejects_max_operation_count(batch_mcp) -> None:
    mcp, bridge = batch_mcp
    too_many = [{"domain": "transport", "action": "get_tempo"}] * 51

    with pytest.raises(Exception, match="operations length must be <= 50"):
        _call(mcp, too_many)

    assert bridge.calls == []


def test_batch_rejects_raw_protocol_or_script_fields(batch_mcp) -> None:
    mcp, bridge = batch_mcp

    with pytest.raises(Exception, match="unsupported raw/script field"):
        _call(mcp, [{"command": protocol.CMD_GET_TEMPO, "params": {}}])

    with pytest.raises(Exception, match="unsupported raw/script field"):
        _call(mcp, [{"domain": "transport", "action": "get_tempo", "script_text": "print(1)"}])

    assert bridge.calls == []


def test_batch_rejects_mixed_reads_and_writes_before_execution(batch_mcp) -> None:
    mcp, bridge = batch_mcp

    with pytest.raises(Exception, match="cannot mix read-only operations with persistent writes"):
        _call(
            mcp,
            [
                {"domain": "transport", "action": "get_tempo"},
                {"domain": "transport", "action": "set_tempo", "params": {"bpm": 128}},
            ],
        )

    assert bridge.calls == []


def test_batch_continue_on_error(batch_mcp) -> None:
    mcp, bridge = batch_mcp

    stopped = _call(
        mcp,
        [
            {"domain": "mixer", "action": "get", "params": {"track": 99}},
            {"domain": "transport", "action": "get_tempo"},
        ],
    )
    assert stopped["ok"] is False
    assert stopped["failed_index"] == 0
    assert stopped["completed"] == 0
    assert len(stopped["results"]) == 1

    bridge.calls.clear()
    continued = _call(
        mcp,
        [
            {"domain": "mixer", "action": "get", "params": {"track": 99}},
            {"domain": "transport", "action": "get_tempo"},
        ],
        continue_on_error=True,
    )
    assert continued["ok"] is False
    assert continued["completed"] == 1
    assert [row["ok"] for row in continued["results"]] == [False, True]
    assert continued["results"][1]["result"] == {"bpm": 120.0}
    assert bridge.calls == [
        (protocol.CMD_MIXER_GET_TRACK, {"index": 99}),
        (protocol.CMD_GET_TEMPO, {}),
    ]
