#!/usr/bin/env python3
"""Focused tests for persistent-write fl_batch (Slice 12)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.tools import batch as batch_tools  # noqa: E402


class WriteBatchBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.tracks = {
            1: {"index": 1, "mute": False, "solo": False, "name": "Insert 1"},
            2: {"index": 2, "mute": False, "solo": False, "name": "Insert 2"},
        }
        self.fail_set_track: int | None = None
        self.mutate_then_fail_set_track: int | None = None

    def call(self, command: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        self.calls.append((command, params))
        if command == protocol.CMD_MIXER_GET_TRACK:
            return dict(self.tracks[int(params["index"])])
        if command == protocol.CMD_MIXER_SET_MUTE:
            track = int(params["track"])
            if self.mutate_then_fail_set_track == track and params["state"] is True:
                self.tracks[track]["mute"] = bool(params["state"])
                raise RuntimeError(f"set failed after mutating track {track}")
            if self.fail_set_track == track and params["state"] is True:
                raise RuntimeError(f"set failed for track {track}")
            self.tracks[track]["mute"] = bool(params["state"])
            return {"track": track, "mute": self.tracks[track]["mute"]}
        if command == protocol.CMD_GET_TEMPO:
            return {"bpm": 120.0}
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


@pytest.fixture()
def isolated_safety_log(tmp_path):
    original_log = safety._log
    original_dry_run = safety.is_dry_run()
    safety._log = safety.ChangeLog(path=tmp_path / "changelog.jsonl", max_entries=20)
    safety.set_dry_run(False)
    try:
        yield safety._log
    finally:
        safety._log = original_log
        safety.set_dry_run(original_dry_run)


@pytest.fixture
def batch_mcp(monkeypatch, isolated_safety_log):
    bridge = WriteBatchBridge()
    monkeypatch.setattr(batch_tools, "get_bridge", lambda: bridge)
    mcp = FastMCP(name="batch-write-test")
    batch_tools.register(mcp)
    return mcp, bridge, isolated_safety_log


def _call(mcp: FastMCP, operations: list[dict], continue_on_error: bool = False):
    return _unwrap(
        asyncio.run(
            mcp.call_tool(
                "fl_batch",
                {"operations": operations, "continue_on_error": continue_on_error},
            )
        )
    )


def _mute_op(track: int, state: bool) -> dict:
    return {"domain": "mixer", "action": "set_mute", "params": {"track": track, "state": state}}


def test_batch_persistent_write_success(batch_mcp) -> None:
    mcp, bridge, log = batch_mcp

    result = _call(mcp, [_mute_op(1, True), _mute_op(2, True)])

    assert result["ok"] is True
    assert result["count"] == 2
    assert result["completed"] == 2
    assert [row["action"] for row in result["results"]] == ["set_mute", "set_mute"]
    assert [row["after"]["mute"] for row in result["results"]] == [True, True]
    assert bridge.tracks[1]["mute"] is True
    assert bridge.tracks[2]["mute"] is True
    summary = log.recent(1)[0]
    assert summary["tool"] == "fl_batch"
    assert summary["rollback_unit"] == "fl_batch_persistent"
    assert summary["group"] is True


def test_batch_invalid_write_validation_does_not_mutate(batch_mcp) -> None:
    mcp, bridge, log = batch_mcp

    with pytest.raises(Exception, match="state must be a boolean"):
        _call(mcp, [_mute_op(1, True), _mute_op(2, 1)])

    assert bridge.calls == []
    assert bridge.tracks[1]["mute"] is False
    assert bridge.tracks[2]["mute"] is False
    assert log.recent(10, include_payload=True) == []


def test_batch_mixed_read_and_write_rejected_before_execution(batch_mcp) -> None:
    mcp, bridge, log = batch_mcp

    with pytest.raises(Exception, match="cannot mix read-only operations with persistent writes"):
        _call(mcp, [{"domain": "transport", "action": "get_tempo"}, _mute_op(1, True)])

    assert bridge.calls == []
    assert log.recent(10, include_payload=True) == []


def test_batch_continue_on_error_rejected_for_writes(batch_mcp) -> None:
    mcp, bridge, log = batch_mcp

    with pytest.raises(Exception, match="continue_on_error is only allowed for read-only batches"):
        _call(mcp, [_mute_op(1, True)], continue_on_error=True)

    assert bridge.calls == []
    assert log.recent(10, include_payload=True) == []


def test_successful_write_batch_rolls_back_as_one_unit(batch_mcp) -> None:
    mcp, bridge, _log = batch_mcp
    result = _call(mcp, [_mute_op(1, True), _mute_op(2, True)])
    assert result["ok"] is True

    rollback = safety.rollback_last_change(bridge)

    assert rollback["ok"] is True
    assert rollback["rolled_back"] == "fl_batch"
    assert bridge.tracks[1]["mute"] is False
    assert bridge.tracks[2]["mute"] is False
    assert bridge.calls[-2:] == [
        (protocol.CMD_MIXER_SET_MUTE, {"track": 2, "state": False}),
        (protocol.CMD_MIXER_SET_MUTE, {"track": 1, "state": False}),
    ]


def test_persistent_write_batch_dry_run_returns_plan(batch_mcp) -> None:
    mcp, bridge, log = batch_mcp
    safety.set_dry_run(True)

    result = _call(mcp, [_mute_op(1, True)])

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["count"] == 1
    assert result["completed"] == 0
    assert result["results"][0]["planned"] == {
        "command": protocol.CMD_MIXER_SET_MUTE,
        "params": {"track": 1, "state": True},
    }
    assert bridge.calls == []
    assert bridge.tracks[1]["mute"] is False
    assert log.recent(10, include_payload=True) == []


def test_partial_write_failure_uses_group_rollback_path(isolated_safety_log) -> None:
    bridge = WriteBatchBridge()
    bridge.fail_set_track = 2
    prepared = batch_tools._prepare_batch([_mute_op(1, True), _mute_op(2, True)])

    with pytest.raises(safety.GroupWriteError) as exc_info:
        batch_tools._execute_persistent_write_batch(bridge, prepared)

    result = exc_info.value.result
    assert result["ok"] is False
    assert result["phase"] == "execute"
    assert result["failed_index"] == 1
    assert result["rollback_attempted"] is True
    assert result["partial_rollback"]["ok"] is True
    assert bridge.tracks[1]["mute"] is False
    assert bridge.tracks[2]["mute"] is False
    assert isolated_safety_log.recent(10, include_payload=True) == []


def test_failed_write_that_mutated_is_included_in_group_rollback(
    isolated_safety_log,
) -> None:
    bridge = WriteBatchBridge()
    bridge.mutate_then_fail_set_track = 2
    prepared = batch_tools._prepare_batch([_mute_op(1, True), _mute_op(2, True)])

    with pytest.raises(safety.GroupWriteError) as exc_info:
        batch_tools._execute_persistent_write_batch(bridge, prepared)

    result = exc_info.value.result
    assert result["ok"] is False
    assert result["phase"] == "execute"
    assert result["failed_index"] == 1
    assert result["rollback_attempted"] is True
    assert result["partial_rollback"]["ok"] is True
    assert [row["index"] for row in result["partial_rollback"]["results"]] == [1, 0]
    assert bridge.tracks[1]["mute"] is False
    assert bridge.tracks[2]["mute"] is False
    assert isolated_safety_log.recent(10, include_payload=True) == []
