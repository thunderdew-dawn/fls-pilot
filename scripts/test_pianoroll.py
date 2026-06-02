#!/usr/bin/env python3
"""Offline unit tests for Phase 4 Piano Roll Pack.

Asserts that chord generation, note name parsing, script rendering,
and rollback undo payloads work correctly.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.pyscript_gen import (  # noqa: E402
    render_apply_script,
    render_quantize_script,
    render_transpose_script,
    write_marker_add_script,
    write_marker_clear_script,
)
from fl_studio_mcp.tools import pianoroll as pr_tools  # noqa: E402

_P = _F = 0


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []
        self.last_notes = None
        self.last_mode = None
        self.last_quantize = None
        self.last_snap = None
        self.last_transpose = None
        self.last_duplicate = None
        self.last_velocity_ramp = None
        self.last_marker_add = None
        self.last_marker_clear = None
        self.last_channel = None
        self.last_pattern = None

    def call(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        return {"ok": True, "command": command, "params": params}

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
        self.last_duplicate = duplicate_bars
        self.last_velocity_ramp = velocity_ramp
        self.last_marker_add = marker_add
        self.last_marker_clear = marker_clear
        self.last_channel = channel
        self.last_pattern = pattern
        return {"ok": True, "count": len(notes), "triggered": trigger}


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    status = "PASS" if cond else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")


def main() -> int:
    # 1. Test Note Name Parser
    print("Testing Note Name Parser...")

    # C5 is 60 (FL Studio standard middle C)
    check("C5 parses to 60", pr_tools.parse_root_note("C5") == 60)
    check("c5 parses to 60 (case-insensitive)", pr_tools.parse_root_note("c5") == 60)
    check("C4 parses to 48", pr_tools.parse_root_note("C4") == 48)
    check("A#4 parses to 58", pr_tools.parse_root_note("A#4") == 58)
    check("Bb4 parses to 58 (flat mapping)", pr_tools.parse_root_note("Bb4") == 58)
    check("B4 parses to 59", pr_tools.parse_root_note("B4") == 59)
    check("C0 parses to 0", pr_tools.parse_root_note("C0") == 0)
    check("G10 parses to 127", pr_tools.parse_root_note("G10") == 127)

    # Integers
    check("Integer 60 remains 60", pr_tools.parse_root_note(60) == 60)
    check("String '60' remains 60", pr_tools.parse_root_note("60") == 60)

    # Error cases
    try:
        pr_tools.parse_root_note("C-1")
        check("C-1 throws ValueError (negative MIDI)", False)
    except ValueError:
        check("C-1 throws ValueError (negative MIDI)", True)

    try:
        pr_tools.parse_root_note("G#10")
        check("G#10 throws ValueError (>127)", False)
    except ValueError:
        check("G#10 throws ValueError (>127)", True)

    try:
        pr_tools.parse_root_note("XYZ")
        check("XYZ throws ValueError (invalid name)", False)
    except ValueError:
        check("XYZ throws ValueError (invalid name)", True)

    # 2. Test Pyscript Generation Rendering
    print("\nTesting Pyscript Generation Rendering...")

    notes = [{"pitch": 60, "time_bars": 0.0, "length_bars": 1.0, "velocity": 0.8}]
    apply_src = render_apply_script(notes, mode="replace")
    check("render_apply_script generates valid headers", '# Script.Name = "MCP Apply"' in apply_src)
    check("render_apply_script bakes in MODE", "MODE = 'replace'" in apply_src)
    check("render_apply_script bakes in NOTES", "[(60, 0.0, 1.0, 0.8)]" in apply_src)

    quant_src = render_quantize_script(0.0625, snap_ends=True)
    check("render_quantize_script bakes in GRID_BARS", "GRID_BARS = 0.0625" in quant_src)
    check("render_quantize_script bakes in SNAP_ENDS", "SNAP_ENDS = True" in quant_src)

    trans_src = render_transpose_script(4)
    check("render_transpose_script bakes in SEMITONES", "SEMITONES = 4" in trans_src)
    marker_path = write_marker_add_script(2.0, "Verse", mode=0)
    check(
        "write_marker_add_script writes MCP_Apply.pyscript",
        marker_path.endswith("MCP_Apply.pyscript"),
    )
    marker_clear_path = write_marker_clear_script()
    check(
        "write_marker_clear_script writes MCP_Apply.pyscript",
        marker_clear_path.endswith("MCP_Apply.pyscript"),
    )

    # 3. Test Core Rollback / safe_piano_roll_write
    print("\nTesting Core Rollback & Undo generation...")

    class MockMCP:
        def __init__(self):
            self.tools = {}

        def tool(self, annotations=None):
            def decorator(func):
                self.tools[func.__name__] = func
                return func

            return decorator

    mcp = MockMCP()
    pr_tools.register(mcp)
    fl_piano_write_notes = mcp.tools["fl_piano_write_notes"]
    fl_piano_write_chord = mcp.tools["fl_piano_write_chord"]
    fl_piano_clear = mcp.tools["fl_piano_clear"]
    fl_piano_transpose = mcp.tools["fl_piano_transpose"]
    fl_piano_duplicate = mcp.tools["fl_piano_duplicate"]
    fl_piano_velocity_ramp = mcp.tools["fl_piano_velocity_ramp"]
    fl_piano_add_marker = mcp.tools["fl_piano_add_marker"]
    fl_piano_clear_markers = mcp.tools["fl_piano_clear_markers"]
    fl_piano_get_notes = mcp.tools["fl_piano_get_notes"]

    bridge = FakeBridge()
    from fl_studio_mcp import connection

    orig_get_bridge = connection.get_bridge
    connection.get_bridge = lambda: bridge
    pr_tools.get_bridge = lambda: bridge

    try:
        # Simulate writing a chord (C minor seventh)
        # min7 intervals are [0, 3, 7, 10] -> root 60 -> notes 60, 63, 67, 70
        res = fl_piano_write_chord("min7", "C5", time_bars=0.0, length_bars=1.0)
        check("fl_piano_write_chord returned ok", res.get("ok") is True)

        # Verify Cmd+Opt+Y trigger was logged in change log
        check(
            "CMD_ENSURE_PIANO_ROLL was called before writing",
            bridge.calls[0] == (protocol.CMD_ENSURE_PIANO_ROLL, {}),
        )
        check("apply_notes received 4 notes for min7", len(bridge.last_notes) == 4)
        check("notes list pitch match", [n["pitch"] for n in bridge.last_notes] == [60, 63, 67, 70])

        targeted_note = pr_tools.PianoRollNote(pitch=62, time_bars=0.0, length_bars=0.25)
        res_target = fl_piano_write_notes([targeted_note], mode="append", channel=3, pattern=2)
        check("fl_piano_write_notes target returned ok", res_target.get("ok") is True)
        check(
            "CMD_ENSURE_PIANO_ROLL received channel/pattern",
            bridge.calls[-1] == (protocol.CMD_ENSURE_PIANO_ROLL, {"channel": 3, "pattern": 2}),
        )
        check("apply_notes received target channel", bridge.last_channel == 3)
        check("apply_notes received target pattern", bridge.last_pattern == 2)

        # Test Rollback of note-write
        # Note write uses FL Studio's undo stack via general_undo (undoUp)
        rb_res = safety.rollback_last_change(bridge)
        check("Rollback of note-write returned ok", rb_res.get("ok") is True)
        check(
            "Rollback invoked CMD_GENERAL_UNDO",
            bridge.calls[-1] == (protocol.CMD_GENERAL_UNDO, {}),
        )

        # Test fl_piano_clear
        res_clear = fl_piano_clear()
        check("fl_piano_clear returned ok", res_clear.get("ok") is True)
        check("apply_notes received empty notes for clear", len(bridge.last_notes) == 0)

        # Test fl_piano_transpose
        res_trans = fl_piano_transpose(semitones=-2)
        check("fl_piano_transpose returned ok", res_trans.get("ok") is True)
        check("apply_notes received transpose factor", bridge.last_transpose == -2)

        res_dup = fl_piano_duplicate(offset_bars=1.0)
        check("fl_piano_duplicate returned ok", res_dup.get("ok") is True)
        check("apply_notes received duplicate offset", bridge.last_duplicate == 1.0)

        res_ramp = fl_piano_velocity_ramp(start=0.3, end=0.9)
        check("fl_piano_velocity_ramp returned ok", res_ramp.get("ok") is True)
        check("apply_notes received velocity_ramp tuple", bridge.last_velocity_ramp == (0.3, 0.9))

        res_marker = fl_piano_add_marker(time_bars=2.0, name="Verse")
        check("fl_piano_add_marker returned ok", res_marker.get("ok") is True)
        check(
            "apply_notes received marker_add payload",
            bridge.last_marker_add.get("name") == "Verse",
        )

        res_clear_markers = fl_piano_clear_markers()
        check("fl_piano_clear_markers returned ok", res_clear_markers.get("ok") is True)
        check("apply_notes marker_clear flag set", bridge.last_marker_clear is True)

        # Test fl_piano_get_notes API limit reporting
        res_get = fl_piano_get_notes()
        check("fl_piano_get_notes returned ok=False", res_get.get("ok") is False)
        check("fl_piano_get_notes error is api-limited", "api-limited" in res_get.get("error"))

    finally:
        connection.get_bridge = orig_get_bridge

    print(f"\nPhase 4 Offline test results: {_P} passed, {_F} failed.")
    return 1 if _F > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
