#!/usr/bin/env python3
"""Stage 2 melody-transcription test on a SYNTHETIC monophonic melody.

Generates a clean C-major scale (one sine note at a time -- monophonic) and
checks pyin recovers the pitches. Shows detected notes; does NOT write to FL.

    python scripts/test_melody_extract.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from fls_pilot.tools.audio import audio_extract_melody  # noqa: E402

SR = 22050
SCALE = [60, 62, 64, 65, 67, 69, 71, 72]  # C major scale C4..C5
SCALE_PC = sorted({p % 12 for p in SCALE})  # {0,2,4,5,7,9,11}
_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


def melody_wav(secs_per_note=0.5):
    parts = []
    for midi in SCALE:
        f = 440.0 * 2 ** ((midi - 69) / 12.0)
        t = np.linspace(0, secs_per_note, int(SR * secs_per_note), endpoint=False)
        env = np.hanning(len(t)).astype(np.float32)
        parts.append((0.5 * np.sin(2 * np.pi * f * t)).astype(np.float32) * env)
    return np.concatenate(parts)


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="flmcp_mel_"))
    wav = d / "cmaj_melody.wav"
    sf.write(str(wav), melody_wav(), SR)  # ~4 s, 8 notes, 120 BPM feel

    print("extracting melody (pyin -- slow)...\n")
    r = audio_extract_melody(str(wav), bpm=120.0, engine="pyin")  # pin pyin: light + deterministic
    print(
        "bpm_used={} note_count={} confidence={}".format(
            r["bpm_used"], r["note_count"], r["confidence"]
        )
    )
    print("\ndetected notes (name @ start_sec, dur, prob):")
    for n in r["notes"]:
        print(
            "  %-4s @ %.2fs  dur %.2fs  prob %.2f"
            % (n["name"], n["start_sec"], n["dur_sec"], n["voiced_prob"])
        )
    print("\nbridge_notes (first 8):", r["bridge_notes"][:8])

    detected_pc = sorted({n["midi"] % 12 for n in r["notes"]})
    covered = [pc for pc in SCALE_PC if pc in detected_pc]
    print(
        "\nscale pitch-classes %s ; detected %s ; covered %d/7"
        % (SCALE_PC, detected_pc, len(covered))
    )

    check(
        "found a sensible note count (5-14 for 8 notes)",
        5 <= r["note_count"] <= 14,
        "got %d" % r["note_count"],
    )
    check("recovers >=6/7 C-major pitch classes", len(covered) >= 6, f"covered={covered}")
    check(
        "no out-of-scale pitch classes",
        all(pc in SCALE_PC for pc in detected_pc),
        f"detected={detected_pc}",
    )

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
