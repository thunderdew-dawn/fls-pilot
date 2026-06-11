#!/usr/bin/env python3
"""Focused tests for verified grouped write safety."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import protocol, safety  # noqa: E402


class GroupBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.tracks = {
            1: {"index": 1, "mute": False, "solo": False, "name": "Insert 1"},
            2: {"index": 2, "mute": False, "solo": False, "name": "Insert 2"},
        }
        self.fail_set_track: int | None = None
        self.fail_restore_track: int | None = None
        self.readback_mute_overrides: dict[int, bool] = {}

    def call(self, command, params=None):
        params = params or {}
        self.calls.append((command, dict(params)))
        if command == protocol.CMD_MIXER_GET_TRACK:
            track = int(params["index"])
            result = dict(self.tracks[track])
            if track in self.readback_mute_overrides:
                result["mute"] = self.readback_mute_overrides[track]
            return result
        if command == protocol.CMD_MIXER_SET_MUTE:
            track = int(params["track"])
            if self.fail_set_track == track and params["state"] is True:
                raise RuntimeError(f"set failed for track {track}")
            if self.fail_restore_track == track and params["state"] is False:
                raise RuntimeError(f"restore failed for track {track}")
            self.tracks[track]["mute"] = bool(params["state"])
            return {"track": track, "mute": self.tracks[track]["mute"]}
        raise AssertionError(command)


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


def _mute_write(track: int, state: bool) -> dict:
    return {
        "snap_scope": f"mixer_track:{track}",
        "command": protocol.CMD_MIXER_SET_MUTE,
        "params": {"track": track, "state": state},
        "verify": ("mute", state),
        "restore": lambda before, track=track: {
            "command": protocol.CMD_MIXER_SET_MUTE,
            "params": {"track": track, "state": before["mute"]},
        },
    }


def test_safe_write_group_success_reads_back_each_write(isolated_safety_log) -> None:
    bridge = GroupBridge()

    result = safety.safe_write_group(
        bridge,
        tool="bulk_mute",
        scope="mixer:bulk",
        writes=[_mute_write(1, True), _mute_write(2, True)],
        rollback_unit="mute_pair",
    )

    assert result["ok"] is True
    assert result["before"] == [
        {"index": 1, "mute": False, "solo": False, "name": "Insert 1"},
        {"index": 2, "mute": False, "solo": False, "name": "Insert 2"},
    ]
    assert [after["mute"] for after in result["after"]] == [True, True]
    assert bridge.tracks[1]["mute"] is True
    assert bridge.tracks[2]["mute"] is True
    assert isolated_safety_log.recent(1)[0]["rollback_unit"] == "mute_pair"


def test_safe_write_success_reports_rollback_guidance(isolated_safety_log) -> None:
    bridge = GroupBridge()

    result = safety.safe_write(
        bridge,
        tool="single_mute",
        scope="mixer_track:1",
        command=protocol.CMD_MIXER_SET_MUTE,
        params={"track": 1, "state": True},
        verify=("mute", True),
        rollback_unit="single_mute_unit",
        build_restore=lambda before: {
            "command": protocol.CMD_MIXER_SET_MUTE,
            "params": {"track": 1, "state": before["mute"]},
        },
    )

    assert result["ok"] is True
    assert result["change_id"].startswith("chg_")
    assert result["before"]["mute"] is False
    assert result["after"]["mute"] is True
    assert result["rollback"]["change_id"] == result["change_id"]
    assert result["rollback"]["rollback_unit"] == "single_mute_unit"
    assert "fl_rollback_change" in result["undo"]
    assert result["change_id"] in result["undo"]


def test_safe_write_group_dry_run_validates_without_snapshotting(isolated_safety_log) -> None:
    bridge = GroupBridge()
    safety.set_dry_run(True)

    result = safety.safe_write_group(
        bridge,
        tool="bulk_mute",
        scope="mixer:bulk",
        writes=[_mute_write(1, True)],
        rollback_unit="dry_run_group",
    )

    assert result == {
        "ok": True,
        "dry_run": True,
        "planned": {
            "tool": "bulk_mute",
            "rollback_unit": "dry_run_group",
            "scope": "mixer:bulk",
            "writes": [
                {
                    "command": protocol.CMD_MIXER_SET_MUTE,
                    "params": {"track": 1, "state": True},
                }
            ],
        },
    }
    assert bridge.calls == []


def test_safe_write_group_validation_failure_does_not_mutate(isolated_safety_log) -> None:
    bridge = GroupBridge()

    with pytest.raises(safety.GroupWriteError) as exc_info:
        safety.safe_write_group(
            bridge,
            tool="bad_group",
            scope="mixer:bulk",
            writes=[
                {
                    "snap_scope": "mixer_track:1",
                    "command": protocol.CMD_MIXER_SET_MUTE,
                    "params": {"track": 1, "state": True},
                }
            ],
        )

    result = exc_info.value.result
    assert result["ok"] is False
    assert result["phase"] == "validation"
    assert result["mutation_started"] is False
    assert bridge.calls == []
    assert isolated_safety_log.recent(10, include_payload=True) == []


def test_safe_write_group_partial_failure_rolls_back_executed_writes(
    isolated_safety_log,
) -> None:
    bridge = GroupBridge()
    bridge.fail_set_track = 2

    with pytest.raises(safety.GroupWriteError) as exc_info:
        safety.safe_write_group(
            bridge,
            tool="bulk_mute",
            scope="mixer:bulk",
            writes=[_mute_write(1, True), _mute_write(2, True)],
        )

    result = exc_info.value.result
    assert result["ok"] is False
    assert result["phase"] == "execute"
    assert result["failed_index"] == 1
    assert result["mutation_started"] is True
    assert result["rollback_attempted"] is True
    assert result["partial_rollback"]["ok"] is True
    assert bridge.tracks[1]["mute"] is False
    assert bridge.tracks[2]["mute"] is False
    assert isolated_safety_log.recent(10, include_payload=True) == []
    assert (protocol.CMD_MIXER_SET_MUTE, {"track": 1, "state": False}) in bridge.calls


def test_safe_write_group_verify_mismatch_rolls_back_executed_write(
    isolated_safety_log,
    monkeypatch,
) -> None:
    monkeypatch.setattr(safety.time, "sleep", lambda _: None)
    bridge = GroupBridge()
    bridge.readback_mute_overrides[1] = False

    with pytest.raises(safety.GroupWriteError) as exc_info:
        safety.safe_write_group(
            bridge,
            tool="bulk_mute",
            scope="mixer:bulk",
            writes=[_mute_write(1, True)],
        )

    result = exc_info.value.result
    assert result["ok"] is False
    assert result["phase"] == "execute"
    assert result["failed_index"] == 0
    assert result["mutation_started"] is True
    assert result["partial_rollback"]["ok"] is True
    assert bridge.tracks[1]["mute"] is False
    assert isolated_safety_log.recent(10, include_payload=True) == []
    assert "did not match expected" in result["error"]


def test_safe_write_group_successful_group_rolls_back_as_one_unit(
    isolated_safety_log,
) -> None:
    bridge = GroupBridge()
    result = safety.safe_write_group(
        bridge,
        tool="bulk_mute",
        scope="mixer:bulk",
        writes=[_mute_write(1, True), _mute_write(2, True)],
        rollback_unit="mute_pair",
    )
    assert result["ok"] is True
    assert result["rollback"]["change_id"] == result["change_id"]
    assert result["rollback"]["rollback_unit"] == "mute_pair"
    assert "fl_rollback_last_change" in result["undo"]

    rollback = safety.rollback_last_change(bridge)

    assert rollback["ok"] is True
    assert rollback["rolled_back"] == "bulk_mute"
    assert bridge.tracks[1]["mute"] is False
    assert bridge.tracks[2]["mute"] is False
    assert bridge.calls[-2:] == [
        (protocol.CMD_MIXER_SET_MUTE, {"track": 2, "state": False}),
        (protocol.CMD_MIXER_SET_MUTE, {"track": 1, "state": False}),
    ]
