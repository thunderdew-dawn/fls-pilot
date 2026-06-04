#!/usr/bin/env python3
"""LIVE: Hard-standardize a copied FL project into a deterministic fixture.

Goal
----
- Make the project clean + clearly structured (names/colors/markers).
- Provide a stable baseline for live MCP capability tests.

Safety
------
All mutations are rollbackable through the MCP safety layer:
- Bulk property edits use safety.safe_write_group (one rollback unit per domain).
- Marker writes are undo-backed and grouped.

This script does NOT delete anything and does NOT edit playlist clips.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("FLSTUDIO_MCP_TRANSPORT", "tcp")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.connection import fetch_all_pages, get_bridge  # noqa: E402


@dataclass(frozen=True)
class RGB:
    r: int
    g: int
    b: int


_MIXER_RESERVED: dict[int, tuple[str, RGB]] = {
    49: ("FX - REVERB", RGB(0, 150, 136)),
    50: ("BUS - EQ2 (PEQ2)", RGB(96, 125, 139)),
}

_PLAYLIST_TEMPLATE: list[tuple[str, RGB]] = [
    ("FIX - DRUMS - KICK", RGB(229, 57, 53)),
    ("FIX - DRUMS - BASS", RGB(251, 140, 0)),
    ("FIX - DRUMS - HATS", RGB(253, 216, 53)),
    ("FIX - DRUMS - PERC", RGB(255, 179, 0)),
    ("FIX - SYN - LEAD", RGB(156, 39, 176)),
    ("FIX - SYN - FX", RGB(0, 188, 212)),
    ("FIX - SYN - PAD", RGB(33, 150, 243)),
    ("FIX - ATMOS", RGB(57, 73, 171)),
    ("FIX - RISERS", RGB(216, 27, 96)),
    ("FIX - VOX", RGB(236, 64, 122)),
    ("FIX - REFERENCE", RGB(158, 158, 158)),
    ("FIX - PRINT / BOUNCE", RGB(121, 85, 72)),
]

_MARKERS: list[tuple[int, str]] = [
    (1, "FIXTURE START"),
    (9, "SECTION B"),
    (17, "SECTION C"),
]


def _w_mixer_set_name(track: int, name: str) -> dict:
    return {
        "snap_scope": f"mixer_track:{track}",
        "command": protocol.CMD_MIXER_SET_NAME,
        "params": {"track": track, "name": name},
        "restore": (
            lambda before, track=track: {
                "command": protocol.CMD_MIXER_SET_NAME,
                "params": {"track": track, "name": before.get("name", "")},
            }
        ),
    }


def _w_mixer_set_color(track: int, rgb: RGB) -> dict:
    return {
        "snap_scope": f"mixer_track:{track}",
        "command": protocol.CMD_MIXER_SET_COLOR,
        "params": {"track": track, "r": rgb.r, "g": rgb.g, "b": rgb.b},
        "restore": (
            lambda before, track=track: {
                "command": protocol.CMD_MIXER_SET_COLOR,
                "params": {
                    "track": track,
                    "color": int((before.get("color") or {}).get("int", 0)),
                },
            }
        ),
    }


def _w_playlist_set_name(index: int, name: str) -> dict:
    return {
        "snap_scope": f"playlist_track:{index}",
        "command": protocol.CMD_PLAYLIST_SET_NAME,
        "params": {"index": index, "name": name},
        "restore": (
            lambda before, index=index: {
                "command": protocol.CMD_PLAYLIST_SET_NAME,
                "params": {"index": index, "name": before.get("name", "")},
            }
        ),
    }


def _w_playlist_set_color(index: int, rgb: RGB) -> dict:
    return {
        "snap_scope": f"playlist_track:{index}",
        "command": protocol.CMD_PLAYLIST_SET_COLOR,
        "params": {"index": index, "r": rgb.r, "g": rgb.g, "b": rgb.b},
        "restore": (
            lambda before, index=index: {
                "command": protocol.CMD_PLAYLIST_SET_COLOR,
                "params": {
                    "index": index,
                    "color": int((before.get("color") or {}).get("int", 0)),
                },
            }
        ),
    }


def _w_add_marker(bar: int, name: str) -> dict:
    return {
        "snap_scope": "project_state",
        "command": protocol.CMD_ARRANGE_ADD_MARKER,
        "params": {"bar": int(bar), "name": str(name)},
        "restore": (lambda _before: {"command": protocol.CMD_GENERAL_UNDO, "params": {}}),
    }


def main() -> int:
    bridge = get_bridge()
    pong = bridge.call(protocol.CMD_PING, {})
    print(f"FL: {pong.get('fl_version')} | build={pong.get('build')}")

    safety.set_dry_run(False)

    # ---- mixer reserved tracks --------------------------------------------
    mixer_tracks = fetch_all_pages(bridge, protocol.CMD_MIXER_LIST_TRACKS, "tracks").get(
        "tracks", []
    )
    max_track = max([int(t.get("i", 0)) for t in mixer_tracks] + [0])
    missing = [t for t in _MIXER_RESERVED if t > max_track]
    if missing:
        print(f"[FAIL] Reserved mixer tracks do not exist on this project: {missing}")
        return 2

    mixer_writes: list[dict] = []
    for track, (name, rgb) in _MIXER_RESERVED.items():
        mixer_writes.append(_w_mixer_set_name(track, name))
        mixer_writes.append(_w_mixer_set_color(track, rgb))

    res = safety.safe_write_group(
        bridge, tool="fixture_mixer", scope="fixture:mixer", writes=mixer_writes
    )
    if not res.get("ok"):
        print(f"[FAIL] mixer fixture write failed: {res}")
        return 1
    print(f"[OK] mixer standardized (change_id={res.get('change_id')})")

    # ---- playlist tracks ---------------------------------------------------
    # IMPORTANT: We cannot inspect playlist clip/automation occupancy on this
    # MCP surface (FL API limitation + no controller handler). To avoid
    # overwriting real content, only standardize a dedicated FIXTURE range at
    # the end of the playlist.
    playlist_start = int(os.environ.get("FL_FIXTURE_PLAYLIST_START", "481"))

    tracks = fetch_all_pages(bridge, protocol.CMD_PLAYLIST_LIST_TRACKS, "tracks")
    playlist_rows = tracks.get("tracks", [])
    total_playlist = int(tracks.get("total", len(playlist_rows)))
    if total_playlist <= 0:
        print("[FAIL] playlist track list is empty")
        return 2

    playlist_writes: list[dict] = []
    if playlist_start < 1 or playlist_start > total_playlist:
        print(
            f"[FAIL] FL_FIXTURE_PLAYLIST_START={playlist_start} is out of range "
            f"(1..{total_playlist})."
        )
        return 2
    for offset, (name, rgb) in enumerate(_PLAYLIST_TEMPLATE):
        idx = playlist_start + offset
        if idx > total_playlist:
            break
        playlist_writes.append(_w_playlist_set_name(idx, name))
        playlist_writes.append(_w_playlist_set_color(idx, rgb))

    res = safety.safe_write_group(
        bridge, tool="fixture_playlist", scope="fixture:playlist", writes=playlist_writes
    )
    if not res.get("ok"):
        print(f"[FAIL] playlist fixture write failed: {res}")
        return 1
    print(f"[OK] playlist standardized (change_id={res.get('change_id')})")

    # ---- markers -----------------------------------------------------------
    marker_writes = [_w_add_marker(bar, name) for bar, name in _MARKERS]
    res = safety.safe_write_group(
        bridge, tool="fixture_markers", scope="fixture:markers", writes=marker_writes
    )
    if not res.get("ok"):
        print(f"[FAIL] marker fixture write failed: {res}")
        return 1
    print(f"[OK] markers added (change_id={res.get('change_id')})")

    print("\nNext:")
    print("  - Run: python3 scripts/run_live_capability_sweep.py")
    print("  - If anything looks wrong: fl_rollback_last_change (repeat as needed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
