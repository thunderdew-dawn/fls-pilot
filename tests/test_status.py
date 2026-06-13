from __future__ import annotations

import json
from pathlib import Path

from fls_pilot import dashboard, protocol


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []
        self.closed = False

    def wait_for_heartbeat(self, timeout: float = 1.0) -> bool:
        return True

    def heartbeat_age(self) -> float:
        return 0.842

    def is_alive(self) -> bool:
        return True

    def call(self, command: str, params: dict | None = None, *, timeout: float | None = None):
        self.calls.append((command, dict(params or {})))
        if command == protocol.CMD_GET_PROJECT_STATE:
            return {
                "fl_version": "25.2.5",
                "tempo_bpm": 145.0,
                "playing": True,
                "recording": False,
                "pattern_number": 2,
                "pattern_count": 3,
                "channel_count": 3,
                "mixer_track_count": 4,
            }
        if command == protocol.CMD_GET_PLAY_STATE:
            return {"playing": True, "recording": False}
        if command == protocol.CMD_GET_SONG_POS:
            return "65:02:11"
        if command == protocol.CMD_GET_TEMPO:
            return 145.0
        if command == protocol.CMD_CHANNEL_LIST:
            return {
                "total": 3,
                "start": params.get("start", 0) if params else 0,
                "next_start": None,
                "channels": [
                    {"i": 0, "name": "Kick", "mute": False, "solo": False},
                    {"i": 1, "name": "Kick", "mute": True, "solo": False},
                    {"i": 2, "name": "Bass", "mute": False, "solo": False},
                ],
            }
        if command == protocol.CMD_MIXER_LIST_TRACKS:
            return {
                "total": 4,
                "start": params.get("start", 0) if params else 0,
                "next_start": None,
                "tracks": [
                    {"i": 0, "name": "Master", "mute": False, "solo": False},
                    {"i": 1, "name": "Drums", "mute": False, "solo": True},
                ],
            }
        if command == protocol.CMD_PATTERN_LIST:
            return {
                "total": 3,
                "start": params.get("start", 0) if params else 0,
                "next_start": None,
                "patterns": [
                    {"i": 1, "name": "Pattern 1"},
                    {"i": 2, "name": "Hook"},
                ],
            }
        if command == protocol.CMD_PLAYLIST_LIST_TRACKS:
            return {
                "total": 2,
                "start": params.get("start", 0) if params else 0,
                "next_start": None,
                "tracks": [
                    {"i": 1, "name": "Arrangement", "mute": False, "solo": False},
                    {"i": 2, "name": "Reference", "mute": True, "solo": False},
                ],
            }
        raise AssertionError(f"unexpected command: {command}")

    def close(self) -> None:
        self.closed = True


def test_collect_dashboard_snapshot_is_read_only(monkeypatch) -> None:
    bridge = FakeBridge()
    monkeypatch.setattr(dashboard.connection, "get_bridge", lambda: bridge)

    snapshot = dashboard.collect_dashboard_snapshot()

    assert snapshot["mode"] == "read-only"
    assert snapshot["bridge"]["state"] == "live"
    assert snapshot["project"]["tempo_bpm"] == 145.0
    assert snapshot["project"]["playlist_track_count"] == 2
    assert bridge.closed is True
    assert {command for command, _ in bridge.calls} <= dashboard.READ_COMMANDS

    organization = snapshot["analysis"]["organization"]["signals"]
    duplicate_signal = next(
        item for item in organization if item["label"] == "Duplicate Channel Names"
    )
    assert duplicate_signal["value"] == 1


def test_export_dashboard_writes_static_app(tmp_path: Path) -> None:
    snapshot = dashboard.collect_dashboard_snapshot(offline=True)
    index_path = dashboard.export_dashboard(tmp_path / "site", snapshot)

    assert index_path.is_file()
    assert (index_path.parent / "styles.css").is_file()
    assert (index_path.parent / "app.js").is_file()
    assert (index_path.parent / "assets" / "fls-pilot-logo-wide.png").is_file()

    data_js = (index_path.parent / "dashboard-data.js").read_text(encoding="utf-8")
    payload = data_js.removeprefix("window.FLS_PILOT_DASHBOARD_DATA = ").rstrip(";\n")
    exported = json.loads(payload)
    assert exported["mode"] == "read-only"
    assert exported["bridge"]["state"] == "unavailable"
