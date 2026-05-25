#!/usr/bin/env python3
"""Stage 1 audio-analysis test on SYNTHETIC files (known BPM + known key).

Generates two WAVs (no FL, no ffmpeg needed for WAV):
  - a 100 BPM click track  -> verify detected tempo ~= 100 (allow half/double)
  - a C-major scale of tones -> verify estimated key tonic is C (or A, relative)

    python scripts/test_audio_analysis.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np                                   # noqa: E402
import soundfile as sf                               # noqa: E402

from fl_studio_mcp.tools.audio import audio_analyze  # noqa: E402

SR = 22050
_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    if cond:
        _P += 1
    else:
        _F += 1
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", label, ("  -- " + detail) if detail else ""))


def click_track(bpm, secs=8.0):
    n = int(SR * secs)
    y = np.zeros(n, dtype=np.float32)
    period = int(SR * 60.0 / bpm)
    blen = 220                                        # ~10 ms broadband burst = strong onset
    for i in range(0, n, period):
        m = min(blen, n - i)
        y[i:i + m] += (np.random.rand(m).astype(np.float32) * 2 - 1) * np.hanning(m).astype(np.float32)
    return y


def cmajor_scale(secs_per_note=0.5):
    freqs = [261.63, 293.66, 329.63, 349.23, 392.0, 440.0, 493.88, 523.25]  # C4..C5
    parts = []
    for f in freqs * 2:                               # two octaves of the scale, ~8 s
        t = np.linspace(0, secs_per_note, int(SR * secs_per_note), endpoint=False)
        env = np.hanning(len(t)).astype(np.float32)   # avoid clicks at note edges
        parts.append((0.5 * np.sin(2 * np.pi * f * t)).astype(np.float32) * env)
    return np.concatenate(parts)


def near(v, target, tol):
    return v is not None and abs(v - target) <= tol


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="flmcp_audio_"))
    click = d / "click_100bpm.wav"
    tone = d / "cmajor_scale.wav"
    sf.write(str(click), click_track(100.0), SR)
    sf.write(str(tone), cmajor_scale(), SR)

    print("[1] tempo on 100 BPM click track")
    a = audio_analyze(str(click))
    print("   ", {k: a[k] for k in ("tempo_bpm", "beats", "onsets", "duration_sec")})
    bpm = a["tempo_bpm"]
    check("tempo ~= 100 (or half/double 50/200)",
          near(bpm, 100, 4) or near(bpm, 50, 3) or near(bpm, 200, 6), "got %s" % bpm)

    print("\n[2] key on C-major scale")
    a2 = audio_analyze(str(tone))
    print("   key:", a2["key"], a2["key"])  # show
    print("   ", a2["key"])
    tonic, mode, conf = a2["key"]["tonic"], a2["key"]["mode"], a2["key"]["confidence"]
    check("tonic is C (or A, relative minor)", tonic in ("C", "A"), "got %s %s (conf %s)" % (tonic, mode, conf))
    check("key labelled estimated", a2["key"].get("estimated") is True)

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
