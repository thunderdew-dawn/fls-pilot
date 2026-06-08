#!/usr/bin/env python3
"""Offline test: color.parse_color + channel/track target resolution (no FL).

python scripts/test_color.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot.tools.bulk import resolve_targets  # noqa: E402
from fls_pilot.tools.color import (  # noqa: E402
    COLOR_NAMES,
    _resolve_channels,
    parse_color,
)

_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


def main() -> int:
    # names (case-insensitive)
    check("'red' -> palette rgb", parse_color("red") == COLOR_NAMES["red"], str(parse_color("red")))
    check("'RED' case-insensitive", parse_color("RED") == COLOR_NAMES["red"])
    check("'grey' aliases 'gray'", parse_color("grey") == parse_color("gray"))
    check("'blue' known", parse_color("blue") == (33, 150, 243), str(parse_color("blue")))

    # hex forms
    check(
        "'#33A1FF' -> (51,161,255)",
        parse_color("#33A1FF") == (51, 161, 255),
        str(parse_color("#33A1FF")),
    )
    check("'33a1ff' (no #) same", parse_color("33a1ff") == (51, 161, 255))
    check("3-digit '#f0a' expands", parse_color("#f0a") == (255, 0, 170), str(parse_color("#f0a")))
    check("pure '#FF0000' -> red", parse_color("#FF0000") == (255, 0, 0))

    # rejects
    check("unknown name -> None", parse_color("chartreuseish") is None)
    check("bad hex len -> None", parse_color("#12") is None)
    check("too-long hex -> None", parse_color("#1234567") is None)
    check("non-hex chars -> None", parse_color("#gggggg") is None)
    check("None -> None", parse_color(None) is None)

    # palette integrity: every value a valid 0-255 triple
    ok = all(
        isinstance(v, tuple)
        and len(v) == 3
        and all(isinstance(c, int) and 0 <= c <= 255 for c in v)
        for v in COLOR_NAMES.values()
    )
    check("all palette values are 0-255 triples", ok)

    # track resolution (reused from bulk): family + Master excluded
    tracks = [
        {"index": 0, "name": "Master"},
        {"index": 1, "name": "Kick"},
        {"index": 2, "name": "Snare"},
        {"index": 3, "name": "Lead Vocal"},
        {"index": 4, "name": "Bass"},
    ]
    drums = resolve_targets(tracks, "drums", None)
    check("category 'drums' matches kick+snare", drums == {1, 2}, str(sorted(drums)))
    check("Master (0) never targeted", 0 not in resolve_targets(tracks, None, ["master", 0]))
    check("explicit name substring 'vocal'", resolve_targets(tracks, None, ["vocal"]) == {3})

    # channel resolution: indices + name substrings (channel 0 allowed)
    chans = [
        {"index": 0, "name": "Kick"},
        {"index": 1, "name": "Clap"},
        {"index": 2, "name": "Bass"},
    ]
    check("channels by index", _resolve_channels(chans, [0, 2]) == {0, 2})
    check("channels by name substring", _resolve_channels(chans, ["clap"]) == {1})
    check("channel 0 NOT excluded", 0 in _resolve_channels(chans, ["kick"]))

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
