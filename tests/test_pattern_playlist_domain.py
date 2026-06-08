#!/usr/bin/env python3
"""Focused tests for consolidated pattern and playlist domain tools (Slice 08)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import protocol, safety  # noqa: E402
from fls_pilot.tools import pattern as pattern_domain_tools  # noqa: E402
from fls_pilot.tools import playlist as playlist_domain_tools  # noqa: E402


class FakeBridge:
    def __init__(self) -> None:
        self.patterns: dict[int, dict] = {
            1: {
                "index": 1,
                "name": "Pattern 1",
                "color": {"int": 0x112233},
                "length": 16.0,
            },
            2: {
                "index": 2,
                "name": "Verse",
                "color": {"int": 0x445566},
                "length": 8.0,
            },
        }
        self.selected_pattern = 1
        self.playlist_tracks: dict[int, dict] = {
            1: {
                "index": 1,
                "name": "Track 1",
                "color": {"int": 0xABCDEF},
                "mute": False,
                "solo": False,
                "selected": False,
            },
            2: {
                "index": 2,
                "name": "Drums",
                "color": {"int": 0x010203},
                "mute": False,
                "solo": False,
                "selected": False,
            },
        }
        self.calls: list[tuple[str, dict]] = []

    def call(self, command: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        self.calls.append((command, params))

        if command == protocol.CMD_PATTERN_LIST:
            patterns = list(self.patterns.values())
            return {"total": len(patterns), "patterns": patterns, "next_start": None}

        if command == protocol.CMD_PATTERN_GET:
            return dict(self.patterns[params["index"]])

        if command == protocol.CMD_PATTERN_GET_LENGTH:
            pattern = self.patterns[params["index"]]
            return {"index": params["index"], "length": pattern["length"]}

        if command == protocol.CMD_PATTERN_SELECTED:
            return {"selected": self.selected_pattern}

        if command == protocol.CMD_PATTERN_FIND_EMPTY:
            return {"index": 3, "pattern_count": len(self.patterns)}

        if command == protocol.CMD_PATTERN_SELECT:
            self.selected_pattern = params["index"]
            return {"selected": self.selected_pattern}

        if command == protocol.CMD_PATTERN_RENAME:
            pattern = self.patterns[params["index"]]
            pattern["name"] = params["name"]
            return dict(pattern)

        if command == protocol.CMD_PATTERN_SET_COLOR:
            pattern = self.patterns[params["index"]]
            color_int = params.get("color")
            if color_int is None:
                color_int = (params["r"] << 16) | (params["g"] << 8) | params["b"]
            pattern["color"] = {"int": color_int}
            return dict(pattern)

        if command == protocol.CMD_PATTERN_SET_LENGTH:
            pattern = self.patterns[params["index"]]
            pattern["length"] = float(params["beats"])
            return {"index": params["index"], "length": pattern["length"]}

        if command == protocol.CMD_PLAYLIST_LIST_TRACKS:
            tracks = list(self.playlist_tracks.values())
            return {"total": len(tracks), "tracks": tracks, "next_start": None}

        if command == protocol.CMD_PLAYLIST_GET_TRACK:
            return dict(self.playlist_tracks[params["index"]])

        if command == protocol.CMD_PLAYLIST_SET_MUTE:
            track = self.playlist_tracks[params["index"]]
            track["mute"] = params["state"]
            return {"index": params["index"], "mute": track["mute"]}

        if command == protocol.CMD_PLAYLIST_SET_SOLO:
            track = self.playlist_tracks[params["index"]]
            track["solo"] = params["state"]
            return {"index": params["index"], "solo": track["solo"]}

        if command == protocol.CMD_PLAYLIST_SET_NAME:
            track = self.playlist_tracks[params["index"]]
            track["name"] = params["name"]
            return dict(track)

        if command == protocol.CMD_PLAYLIST_SET_COLOR:
            track = self.playlist_tracks[params["index"]]
            color_int = params.get("color")
            if color_int is None:
                color_int = (params["r"] << 16) | (params["g"] << 8) | params["b"]
            track["color"] = {"int": color_int}
            return dict(track)

        if command == protocol.CMD_PLAYLIST_SELECT_TRACK:
            track = self.playlist_tracks[params["index"]]
            track["selected"] = params["state"]
            return {"index": params["index"], "selected": track["selected"]}

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
def domain_mcp(monkeypatch, tmp_path):
    bridge = FakeBridge()
    monkeypatch.setattr(pattern_domain_tools, "get_bridge", lambda: bridge)
    monkeypatch.setattr(playlist_domain_tools, "get_bridge", lambda: bridge)
    safety._log = safety.ChangeLog(tmp_path / "changes.jsonl")
    mcp = FastMCP(name="pattern-playlist-test")
    pattern_domain_tools.register(mcp)
    playlist_domain_tools.register(mcp)
    return mcp, bridge


def _call_pattern(mcp: FastMCP, action: str, params: dict | None = None):
    args = {"action": action}
    if params is not None:
        args["params"] = params
    return _unwrap(asyncio.run(mcp.call_tool("fl_pattern", args)))


def _call_playlist(mcp: FastMCP, action: str, params: dict | None = None):
    args = {"action": action}
    if params is not None:
        args["params"] = params
    return _unwrap(asyncio.run(mcp.call_tool("fl_playlist", args)))


def test_pattern_domain_read_list_and_get(domain_mcp) -> None:
    mcp, bridge = domain_mcp

    listed = _call_pattern(mcp, "list")
    detail = _call_pattern(mcp, "get", {"index": 2})

    assert listed["total"] == 2
    assert detail["name"] == "Verse"
    commands = [cmd for cmd, _ in bridge.calls]
    assert protocol.CMD_PATTERN_LIST in commands
    assert protocol.CMD_PATTERN_GET in commands


def test_pattern_domain_write_rename(domain_mcp) -> None:
    mcp, bridge = domain_mcp

    result = _call_pattern(mcp, "rename", {"index": 2, "name": "Chorus"})

    assert result["ok"] is True
    assert result["before"]["name"] == "Verse"
    assert result["after"]["name"] == "Chorus"
    assert bridge.patterns[2]["name"] == "Chorus"


def test_pattern_domain_write_select(domain_mcp) -> None:
    mcp, bridge = domain_mcp

    result = _call_pattern(mcp, "select", {"index": 2})

    assert result["ok"] is True
    assert result["before"] == {"selected": 1}
    assert result["after"] == {"selected": 2}
    assert bridge.selected_pattern == 2


def test_playlist_domain_track_read_list_and_get(domain_mcp) -> None:
    mcp, bridge = domain_mcp

    listed = _call_playlist(mcp, "list")
    detail = _call_playlist(mcp, "get", {"index": 2})

    assert listed["total"] == 2
    assert detail["name"] == "Drums"
    commands = [cmd for cmd, _ in bridge.calls]
    assert protocol.CMD_PLAYLIST_LIST_TRACKS in commands
    assert protocol.CMD_PLAYLIST_GET_TRACK in commands


def test_playlist_domain_track_write_mute(domain_mcp) -> None:
    mcp, bridge = domain_mcp

    result = _call_playlist(mcp, "set_mute", {"index": 2, "state": True})

    assert result["ok"] is True
    assert result["before"]["mute"] is False
    assert result["after"]["mute"] is True
    assert bridge.playlist_tracks[2]["mute"] is True


def test_playlist_domain_track_write_name(domain_mcp) -> None:
    mcp, bridge = domain_mcp

    result = _call_playlist(mcp, "set_name", {"index": 2, "name": "Drum Bus"})

    assert result["ok"] is True
    assert result["before"]["name"] == "Drums"
    assert result["after"]["name"] == "Drum Bus"
    assert bridge.playlist_tracks[2]["name"] == "Drum Bus"


def test_pattern_and_playlist_domains_reject_invalid_actions(domain_mcp) -> None:
    mcp, _bridge = domain_mcp

    with pytest.raises(Exception, match="unknown operation: pattern.delete"):
        _call_pattern(mcp, "delete", {"index": 1})

    with pytest.raises(Exception, match="unknown operation: playlist.clip_delete"):
        _call_playlist(mcp, "clip_delete", {"index": 1})


def test_pattern_and_playlist_domains_reject_invalid_parameters(domain_mcp) -> None:
    mcp, _bridge = domain_mcp

    with pytest.raises(Exception, match="beats must be > 0"):
        _call_pattern(mcp, "set_length", {"index": 1, "beats": 0})

    with pytest.raises(Exception, match="state must be a boolean"):
        _call_playlist(mcp, "set_mute", {"index": 1, "state": 1})
