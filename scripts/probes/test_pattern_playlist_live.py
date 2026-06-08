#!/usr/bin/env python3
"""LIVE integration test for Phase 3 Patterns & Playlist.

Talks to FL Studio through the running daemon (TCP) to verify that all
pattern and playlist mutations and their corresponding rollbacks work.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Force TCP transport
os.environ.setdefault("FLS_PILOT_TRANSPORT", "tcp")

# Add src/ to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import (
    protocol,  # noqa: E402
    safety,  # noqa: E402
)
from fls_pilot.connection import fetch_all_pages, get_bridge  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    status = "PASS" if cond else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")


def main() -> int:
    b = get_bridge()

    try:
        pong = b.call("ping", {})
    except Exception as e:
        print(f"Error connecting to bridge/daemon: {e}")
        print("Please ensure the FL Studio Pilot daemon is running and FL Studio is open.")
        return 1

    build_marker = pong.get("build")
    print(f"Connected to FL Studio: {pong.get('fl_version')} | Controller Build: {build_marker}")

    # Safety check: Clean the change log first to avoid LIFO confusion
    changelog = safety.get_changelog()
    while changelog.pop_last() is not None:
        pass

    try:
        print("\n--- 1. Testing Reads (Pattern & Playlist) ---")

        # Pattern list
        pats = fetch_all_pages(b, protocol.CMD_PATTERN_LIST, "patterns")
        check("List patterns succeeded", "patterns" in pats)
        print(f"  Found {len(pats.get('patterns', []))} patterns.")

        # Pattern length
        if pats.get("patterns"):
            first_pat = pats["patterns"][0]["pattern"]
            len_res = b.call(protocol.CMD_PATTERN_GET_LENGTH, {"index": first_pat})
            check("Get pattern length succeeded", "beats" in len_res and "steps" in len_res)
            print(
                f"  Pattern {first_pat} length: {len_res['beats']} beats ({len_res['steps']} steps)."
            )

        # Playlist track list
        tracks_res = fetch_all_pages(b, protocol.CMD_PLAYLIST_LIST_TRACKS, "tracks")
        check("List playlist tracks succeeded", "tracks" in tracks_res)
        print(f"  Found {len(tracks_res.get('tracks', []))} playlist tracks.")

        # Playlist track get
        track_detail = b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": 1})
        check("Get playlist track 1 details succeeded", track_detail.get("index") == 1)
        print(
            f"  Track 1 current name: {track_detail.get('name')!r}, mute: {track_detail.get('mute')}, color: {track_detail.get('color', {}).get('hex')}"
        )

        print("\n--- 2. Testing Pattern Mutations & Rollback ---")

        pat_count = len(pats.get("patterns", []))
        if pat_count >= 2:
            # Get initial selected pattern
            init_pat_sel = b.call(protocol.CMD_PATTERN_SELECTED, {})
            init_pat = init_pat_sel.get("selected", 1)
            target_pat = 2 if init_pat == 1 else 1

            print(f"Current active pattern: {init_pat}. Selecting pattern: {target_pat}...")
            sel_res = safety.safe_write(
                b,
                tool="pattern_select",
                scope="patterns_selected",
                command=protocol.CMD_PATTERN_SELECT,
                params={"index": target_pat},
                build_restore=lambda b_snap: {
                    "command": protocol.CMD_PATTERN_SELECT,
                    "params": {"index": b_snap["selected"]},
                },
            )
            check("Select pattern returned ok", sel_res.get("ok") is True)

            current_pat = b.call(protocol.CMD_PATTERN_SELECTED, {}).get("selected")
            check("Pattern selection verified in FL", current_pat == target_pat)

            # Rollback selection
            print("Rolling back pattern selection...")
            rb_sel = safety.rollback_last_change(b)
            check("Rollback pattern selection returned ok", rb_sel.get("ok") is True)

            restored_pat = b.call(protocol.CMD_PATTERN_SELECTED, {}).get("selected")
            check("Pattern selection successfully restored", restored_pat == init_pat)
        else:
            print("  Skipping pattern selection test (only 1 pattern exists in FL project).")

        # Pattern Rename
        pat_to_rename = 1
        pat_orig_detail = b.call(protocol.CMD_PATTERN_GET, {"index": pat_to_rename})
        orig_pat_name = pat_orig_detail.get("name", f"Pattern {pat_to_rename}")
        temp_pat_name = "MCP TEMP PAT"

        print(f"Renaming pattern {pat_to_rename} to {temp_pat_name!r}...")
        ren_res = safety.safe_write(
            b,
            tool="pattern_rename",
            scope=f"pattern:{pat_to_rename}",
            command=protocol.CMD_PATTERN_RENAME,
            params={"index": pat_to_rename, "name": temp_pat_name},
            build_restore=lambda b_snap: {
                "command": protocol.CMD_PATTERN_RENAME,
                "params": {"index": pat_to_rename, "name": b_snap["name"]},
            },
        )
        check("Rename pattern returned ok", ren_res.get("ok") is True)

        current_pat_name = b.call(protocol.CMD_PATTERN_GET, {"index": pat_to_rename}).get("name")
        check("Rename verified in FL", current_pat_name == temp_pat_name)

        # Rollback rename
        print("Rolling back pattern rename...")
        rb_ren = safety.rollback_last_change(b)
        check("Rollback pattern rename returned ok", rb_ren.get("ok") is True)

        restored_pat_name = b.call(protocol.CMD_PATTERN_GET, {"index": pat_to_rename}).get("name")
        check("Pattern name successfully restored", restored_pat_name == orig_pat_name)

        print("\n--- 3. Testing Playlist Track Mutations & Rollback ---")

        # Playlist track mute
        track_to_mute = 1
        orig_mute = bool(
            b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_mute}).get("mute")
        )
        temp_mute = not orig_mute

        print(f"Playlist track {track_to_mute} mute state: {orig_mute}. Setting to: {temp_mute}...")
        mute_res = safety.safe_write(
            b,
            tool="playlist_set_mute",
            scope=f"playlist_track:{track_to_mute}",
            command=protocol.CMD_PLAYLIST_SET_MUTE,
            params={"index": track_to_mute, "state": temp_mute},
            verify=("mute", temp_mute),
            build_restore=lambda b_snap: {
                "command": protocol.CMD_PLAYLIST_SET_MUTE,
                "params": {"index": track_to_mute, "state": b_snap["mute"]},
            },
        )
        check("Set playlist mute returned ok", mute_res.get("ok") is True)

        time.sleep(0.1)
        current_mute = bool(
            b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_mute}).get("mute")
        )
        check("Mute state verified in FL", current_mute == temp_mute)

        # Rollback mute
        print("Rolling back playlist track mute...")
        rb_mute = safety.rollback_last_change(b)
        check("Rollback mute returned ok", rb_mute.get("ok") is True)

        time.sleep(0.1)
        restored_mute = bool(
            b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_mute}).get("mute")
        )
        check("Playlist track mute successfully restored", restored_mute == orig_mute)

        # Playlist track name
        track_to_name = 1
        orig_track_name = b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_name}).get(
            "name", ""
        )
        temp_track_name = "MCP TEMP TRACK"

        print(f"Renaming playlist track {track_to_name} to {temp_track_name!r}...")
        name_res = safety.safe_write(
            b,
            tool="playlist_set_name",
            scope=f"playlist_track:{track_to_name}",
            command=protocol.CMD_PLAYLIST_SET_NAME,
            params={"index": track_to_name, "name": temp_track_name},
            build_restore=lambda b_snap: {
                "command": protocol.CMD_PLAYLIST_SET_NAME,
                "params": {"index": track_to_name, "name": b_snap["name"]},
            },
        )
        check("Set playlist track name returned ok", name_res.get("ok") is True)

        current_track_name = b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_name}).get(
            "name"
        )
        check("Rename verified in FL", current_track_name == temp_track_name)

        # Rollback name
        print("Rolling back playlist track rename...")
        rb_name = safety.rollback_last_change(b)
        check("Rollback rename returned ok", rb_name.get("ok") is True)

        restored_track_name = b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_name}).get(
            "name"
        )
        check("Playlist track name successfully restored", restored_track_name == orig_track_name)

        # Playlist track color
        track_to_color = 1
        orig_color_int = (
            b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_color})
            .get("color", {})
            .get("int", 0)
        )

        print(f"Changing playlist track {track_to_color} color...")
        color_res = safety.safe_write(
            b,
            tool="playlist_set_color",
            scope=f"playlist_track:{track_to_color}",
            command=protocol.CMD_PLAYLIST_SET_COLOR,
            params={"index": track_to_color, "r": 255, "g": 0, "b": 0},
            build_restore=lambda b_snap: {
                "command": protocol.CMD_PLAYLIST_SET_COLOR,
                "params": {"index": track_to_color, "color": b_snap["color"]["int"]},
            },
        )
        check("Set playlist track color returned ok", color_res.get("ok") is True)

        current_color_hex = (
            b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_color})
            .get("color", {})
            .get("hex")
        )
        check("Color verified in FL (should be #FF0000)", current_color_hex == "#FF0000")

        # Rollback color
        print("Rolling back playlist track color...")
        rb_color = safety.rollback_last_change(b)
        check("Rollback color returned ok", rb_color.get("ok") is True)

        restored_color_int = (
            b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_color})
            .get("color", {})
            .get("int")
        )
        check("Playlist track color successfully restored", restored_color_int == orig_color_int)

        # Playlist track selection
        track_to_select = 1
        orig_selected = bool(
            b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_select}).get("selected")
        )
        temp_selected = not orig_selected

        print(
            f"Playlist track {track_to_select} selection: {orig_selected}. Setting to: {temp_selected}..."
        )
        sel_res = safety.safe_write(
            b,
            tool="playlist_select_track",
            scope=f"playlist_track:{track_to_select}",
            command=protocol.CMD_PLAYLIST_SELECT_TRACK,
            params={"index": track_to_select, "state": temp_selected},
            verify=("selected", temp_selected),
            build_restore=lambda b_snap: {
                "command": protocol.CMD_PLAYLIST_SELECT_TRACK,
                "params": {"index": track_to_select, "state": b_snap["selected"]},
            },
        )
        check("Select playlist track returned ok", sel_res.get("ok") is True)

        current_selected = bool(
            b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_select}).get("selected")
        )
        check("Selection verified in FL", current_selected == temp_selected)

        # Rollback selection
        print("Rolling back playlist track selection...")
        rb_sel = safety.rollback_last_change(b)
        check("Rollback selection returned ok", rb_sel.get("ok") is True)

        restored_selected = bool(
            b.call(protocol.CMD_PLAYLIST_GET_TRACK, {"index": track_to_select}).get("selected")
        )
        check("Playlist track selection successfully restored", restored_selected == orig_selected)

    except Exception as e:
        print(f"Live test encountered an exception: {e}")
        return 1

    print(f"\nPhase 3 Live test results: {_P} passed, {_F} failed.")
    return 1 if _F > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
