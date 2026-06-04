#!/usr/bin/env python3
"""Offline unit tests for Phase 6 Scale & Mode Composition Pack.

Asserts that scale catalogue loading, note mapping logic, and compose tools
work correctly.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.music import scales  # noqa: E402
from fl_studio_mcp.tools import compose as comp_tools  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    status = "PASS" if cond else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")


def main() -> int:
    print("Testing parse_root_note...")
    check("Parse C5 -> 60", scales.parse_root_note("C5") == 60)
    check("Parse A#4 -> 58", scales.parse_root_note("A#4") == 58)
    check("Parse Bb3 -> 46", scales.parse_root_note("Bb3") == 46)
    check("Parse integer 72 -> 72", scales.parse_root_note(72) == 72)
    check("Parse string integer '72' -> 72", scales.parse_root_note("72") == 72)

    # Boundary / error checks
    try:
        scales.parse_root_note("xyz")
        check("Parse invalid string throws ValueError", False)
    except ValueError:
        check("Parse invalid string throws ValueError", True)

    try:
        scales.parse_root_note(-5)
        check("Parse out of range MIDI note throws ValueError", False)
    except ValueError:
        check("Parse out of range MIDI note throws ValueError", True)

    print("\nTesting midi_to_note_name...")
    check("MIDI 60 -> C5", scales.midi_to_note_name(60) == "C5")
    check("MIDI 58 -> A#4", scales.midi_to_note_name(58) == "A#4")
    check(
        "MIDI 46 -> A#3", scales.midi_to_note_name(46) == "A#3"
    )  # Bb3 is A#3 in standard sharps spelling

    print("\nTesting get_scale_notes...")
    # Western Major (intervals [0, 2, 4, 5, 7, 9, 11])
    res_major = scales.get_scale_notes("major", "C5")
    check("Major scale key resolved", res_major["key"] == "major")
    check("Major scale C5 notes count", len(res_major["notes_asc"]) == 7)
    check("Major scale C5 pitches", res_major["notes_asc"] == [60, 62, 64, 65, 67, 69, 71])
    check(
        "Major scale C5 note names",
        res_major["names_asc"] == ["C5", "D5", "E5", "F5", "G5", "A5", "B5"],
    )

    # Raga Mohanam (intervals [0, 2, 4, 7, 9])
    res_mohanam = scales.get_scale_notes("mohanam", "G4")
    check("Mohanam scale resolved", res_mohanam["key"] == "mohanam")
    check("Mohanam G4 pitches", res_mohanam["notes_asc"] == [55, 57, 59, 62, 64])  # G4 = 55
    check("Mohanam G4 note names", res_mohanam["names_asc"] == ["G4", "A4", "B4", "D5", "E5"])

    # Asymmetric scale Raga Abheri (asc: [0, 3, 5, 7, 10], desc: [0, 2, 3, 5, 7, 9, 10])
    res_abheri = scales.get_scale_notes("abheri", "C5")
    check("Abheri scale resolved", res_abheri["key"] == "abheri")
    check("Abheri C5 ascending count (pentatonic)", len(res_abheri["notes_asc"]) == 5)
    check("Abheri C5 descending count (heptatonic)", len(res_abheri["notes_desc"]) == 7)
    check(
        "Abheri C5 descending notes are reversed",
        res_abheri["notes_desc"] == [70, 69, 67, 65, 63, 62, 60],
    )

    print("\nTesting registered compose tools...")

    class MockMCP:
        def __init__(self):
            self.tools = {}

        def tool(self, annotations=None):
            def decorator(func):
                self.tools[func.__name__] = func
                return func

            return decorator

    mcp = MockMCP()
    comp_tools.register(mcp)
    fl_scale_list = mcp.tools["fl_scale_list"]
    fl_scale_get = mcp.tools["fl_scale_get"]

    # Test fl_scale_list
    list_res = fl_scale_list()
    check("fl_scale_list returned ok", list_res.get("ok") is True)
    check("families found in response", "families" in list_res)
    check("Western family present", "Western" in list_res["families"])
    check("Melakarta Raga family present", "Melakarta Raga" in list_res["families"])

    # Test fl_scale_get
    get_res = fl_scale_get("dorian", "D5")
    check("fl_scale_get returned ok", get_res.get("ok") is True)
    check(
        "Dorian D5 pitches correct", get_res.get("notes_asc") == [62, 64, 65, 67, 69, 71, 72]
    )  # D5=62

    # Test fl_scale_get error path
    get_err = fl_scale_get("nonexistent_scale", "C5")
    check("fl_scale_get invalid scale returns ok=False", get_err.get("ok") is False)
    check("fl_scale_get error message present", "error" in get_err)

    print(f"\nPhase 6 Offline test results: {_P} passed, {_F} failed.")
    return 1 if _F > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
