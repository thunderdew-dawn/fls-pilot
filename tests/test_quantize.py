#!/usr/bin/env python3
"""Offline test: pyscript_gen.quantize_notes (snap math) + render_quantize_script.

python scripts/test_quantize.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.pyscript_gen import quantize_notes, render_quantize_script  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


def main() -> int:
    notes = [
        {"pitch": 60, "time_bars": 0.03, "length_bars": 0.20, "velocity": 0.8},
        {"pitch": 62, "time_bars": 0.26, "length_bars": 0.10, "velocity": 0.8},
    ]
    # snap starts to 1/16 (0.0625): 0.03 -> 0.0 ; 0.26 -> 0.25
    q = quantize_notes(notes, 0.0625)
    check(
        "start 0.03 snaps to 0.0 (1/16)",
        abs(q[0]["time_bars"] - 0.0) < 1e-9,
        str(q[0]["time_bars"]),
    )
    check(
        "start 0.26 snaps to 0.25 (1/16)",
        abs(q[1]["time_bars"] - 0.25) < 1e-9,
        str(q[1]["time_bars"]),
    )
    check("lengths untouched when snap_ends off", q[0]["length_bars"] == 0.20)
    check("pitch/velocity preserved", q[0]["pitch"] == 60 and q[0]["velocity"] == 0.8)

    # snap_ends to 1/4: length 0.20 -> 0.25 (rounds up, min one grid)
    q2 = quantize_notes(notes, 0.25, snap_ends=True)
    check(
        "snap_ends snaps length 0.20 -> 0.25",
        abs(q2[0]["length_bars"] - 0.25) < 1e-9,
        str(q2[0]["length_bars"]),
    )
    check("snap_ends never zero-length", all(n["length_bars"] >= 0.25 for n in q2))

    # grid 0 -> unchanged (but copied, not the same objects)
    q0 = quantize_notes(notes, 0)
    check("grid 0 leaves notes unchanged", q0[0]["time_bars"] == 0.03 and q0 is not notes)

    # render_quantize_script embeds the grid + uses addNote
    s = render_quantize_script(0.0625, True)
    check(
        "render embeds grid + snap_ends + addNote",
        "GRID_BARS = 0.0625" in s
        and "SNAP_ENDS = True" in s
        and "addNote" in s
        and "score.noteCount" in s,
    )

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
