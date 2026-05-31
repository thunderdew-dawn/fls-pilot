#!/usr/bin/env python3
"""CLI: transcribe a monophonic melody from an audio file (offline, no FL).

python scripts/extract_melody_file.py <path> [bpm] [fmin] [fmax] [min_conf] [engine]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import contextlib

from fl_studio_mcp.tools.audio import audio_extract_melody  # noqa: E402


def main() -> int:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        print("usage: extract_melody_file.py <path> [bpm] [fmin] [fmax] [min_conf] [engine]")
        return 2
    path = sys.argv[1]
    if not os.path.isfile(path):
        print("file not found:", path)
        return 1
    bpm = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] not in ("-", "auto") else None
    fmin = sys.argv[3] if len(sys.argv) > 3 else "C2"
    fmax = sys.argv[4] if len(sys.argv) > 4 else "C7"
    min_conf = float(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != "-" else None
    engine = sys.argv[6] if len(sys.argv) > 6 else None
    r = audio_extract_melody(
        path, bpm, fmin_note=fmin, fmax_note=fmax, min_conf=min_conf, engine=engine
    )
    print(
        "engine={}  bpm_used={}  note_count={}  kept={}  confidence={}  filters={}".format(
            r["engine"],
            r["bpm_used"],
            r["note_count"],
            r["kept_count"],
            r["confidence"],
            r.get("filters"),
        )
    )
    print("quality:", r["quality"])
    print("\ndetected notes (name @ start_sec, dur, voiced_prob, keep?):")
    for n in r["notes"]:
        print(
            "  %-4s @ %6.2fs  dur %5.2fs  prob %.2f  %s"
            % (
                n["name"],
                n["start_sec"],
                n["dur_sec"],
                n["voiced_prob"],
                "keep" if n["kept"] else "drop",
            )
        )
    print("\nbridge_notes (first 16):")
    print(json.dumps(r["bridge_notes"][:16], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
