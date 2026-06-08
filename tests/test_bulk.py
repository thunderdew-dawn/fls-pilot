#!/usr/bin/env python3
"""Offline test: bulk.resolve_targets (category + explicit selection), no FL.

python scripts/test_bulk.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot.tools.bulk import resolve_targets  # noqa: E402

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


TRACKS = [
    {"index": 0, "name": "Master"},
    {"index": 1, "name": "Kick"},
    {"index": 2, "name": "Snare"},
    {"index": 3, "name": "Lead Vox"},
    {"index": 5, "name": "Bass"},
    {"index": 6, "name": "Future Trumpet"},
]


def main() -> int:
    check(
        "category 'drums' -> Kick + Snare",
        resolve_targets(TRACKS, category="drums") == {1, 2},
        str(resolve_targets(TRACKS, category="drums")),
    )
    check("category 'bass' -> Bass", resolve_targets(TRACKS, category="bass") == {5})
    check("category 'vocals' -> Lead Vox", resolve_targets(TRACKS, category="vocals") == {3})
    check("explicit name 'vox' -> Lead Vox", resolve_targets(TRACKS, names=["vox"]) == {3})
    check("explicit index [6] -> {6}", resolve_targets(TRACKS, names=[6]) == {6})
    check(
        "unknown category 'trumpet' -> literal name match (6)",
        resolve_targets(TRACKS, category="trumpet") == {6},
    )
    check(
        "Master (index 0) is never selected",
        0 not in resolve_targets(TRACKS, category="master")
        and 0 not in resolve_targets(TRACKS, names=["master", 0]),
    )
    check(
        "category + names union", resolve_targets(TRACKS, category="drums", names=[5]) == {1, 2, 5}
    )
    check("no criteria -> empty set", resolve_targets(TRACKS) == set())

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
