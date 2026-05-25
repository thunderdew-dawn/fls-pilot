#!/usr/bin/env python3
"""PROBE: torchcrepe pitch detection vs pyin, on one file.

ISOLATED -- does NOT import or modify the librosa/pyin melody code in
tools/audio.py. Shows notes only; NEVER writes to FL. Segmentation mirrors
audio_extract_melody so the comparison is apples-to-apples.

    python scripts/probe_crepe.py "<path>" [bpm] [fmin_note] [fmax_note] [min_conf]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np          # noqa: E402
import librosa              # noqa: E402
import torch                # noqa: E402
import torchcrepe           # noqa: E402

SR = 16000                  # CREPE is trained at 16 kHz
HOP = 160                   # 10 ms hop at 16 kHz -> 100 frames/sec

# Bb natural minor pitch classes: Bb C Db Eb F Gb Ab
BBMIN_PC = {10, 0, 1, 3, 5, 6, 8}
PC_NAME = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def segment(f0, conf, times, min_conf, min_note_sec=0.06):
    """Group consecutive same-rounded-pitch voiced frames into notes
    (same approach as audio_extract_melody, but conf-gated)."""
    midi = librosa.hz_to_midi(f0)
    raw, cur, start, probs = [], None, None, []

    def flush(end_t):
        if cur is not None and start is not None and (end_t - start) >= min_note_sec:
            raw.append((int(round(cur)), float(start), float(end_t - start),
                        float(np.mean(probs)) if probs else 0.0))

    for i in range(len(f0)):
        ok = bool(conf[i] >= min_conf) and np.isfinite(midi[i])
        if ok:
            if cur is None or int(round(midi[i])) != int(round(cur)):
                flush(times[i])
                cur, start, probs = midi[i], times[i], [conf[i]]
            else:
                probs.append(conf[i])
        else:
            flush(times[i])
            cur = start = None
            probs = []
    if len(times):
        flush(times[-1])
    return raw


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path or not Path(path).is_file():
        print("usage: probe_crepe.py <path> [bpm] [fmin_note] [fmax_note] [min_conf]")
        return 2
    bpm = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
    fmin_note = sys.argv[3] if len(sys.argv) > 3 else "C3"
    fmax_note = sys.argv[4] if len(sys.argv) > 4 else "C6"
    min_conf = float(sys.argv[5]) if len(sys.argv) > 5 else 0.3

    y, _ = librosa.load(path, sr=SR, mono=True)
    audio = torch.tensor(y, dtype=torch.float32).unsqueeze(0)
    fmin = float(librosa.note_to_hz(fmin_note))
    fmax = float(librosa.note_to_hz(fmax_note))

    print("running torchcrepe (model=full, CPU -- may take ~10-60s)...")
    t0 = time.time()
    pitch, period = torchcrepe.predict(
        audio, SR, hop_length=HOP, fmin=fmin, fmax=fmax,
        model="full", return_periodicity=True, batch_size=512, device="cpu")
    elapsed = time.time() - t0
    f0 = pitch.squeeze(0).cpu().numpy()
    conf = period.squeeze(0).cpu().numpy()
    times = np.arange(len(f0)) * HOP / SR

    raw = segment(f0, conf, times, min_conf)

    barlen = 4.0 * 60.0 / bpm

    def q(x):
        return round(round(x / (1 / 16.0)) * (1 / 16.0), 4)

    notes = []
    for pitch_midi, st, dur, pr in raw:
        notes.append({
            "midi": pitch_midi,
            "name": str(librosa.midi_to_note(pitch_midi, unicode=False)),
            "pc": pitch_midi % 12,
            "start_sec": round(st, 3), "dur_sec": round(dur, 3),
            "conf": round(pr, 3),
            "time_bars": q(st / barlen),
        })

    mean_conf = round(float(np.mean([n["conf"] for n in notes])), 3) if notes else 0.0
    det_pc = sorted({n["pc"] for n in notes})
    in_key = [n for n in notes if n["pc"] in BBMIN_PC]
    out_key = [n for n in notes if n["pc"] not in BBMIN_PC]

    print("\n=== torchcrepe result ===")
    print("file:", path, " (%.1fs compute)" % elapsed)
    print("bpm:", bpm, " range:", fmin_note, "-", fmax_note, " min_conf:", min_conf)
    print("frames:", len(f0), " mean periodicity(all):", round(float(conf.mean()), 3))
    print("note_count:", len(notes), " mean_conf:", mean_conf)
    print("\ndetected notes (name @ start, dur, conf):")
    for n in notes:
        flag = "" if n["pc"] in BBMIN_PC else "  <-- OUT of Bb minor"
        print("  %-4s @ %6.2fs  dur %5.2fs  conf %.2f%s" % (
            n["name"], n["start_sec"], n["dur_sec"], n["conf"], flag))

    print("\ndetected pitch-classes:", [PC_NAME[pc] for pc in det_pc])
    print("Bb-minor scale PCs     :", [PC_NAME[pc] for pc in sorted(BBMIN_PC)])
    print("in-key : %d/%d notes" % (len(in_key), len(notes)))
    print("out-of-key: %d  ->" % len(out_key), [n["name"] for n in out_key])

    # octave-spread = how many distinct octaves the notes span (lower = less jumping)
    octs = sorted({n["midi"] // 12 for n in notes})
    print("octave span:", octs, "(%d distinct octaves)" % len(octs))

    print("\n--- vs pyin (cleaned) ---")
    print("pyin: 8 notes, conf 0.491, C3 C#3 E3 G3 G3 C4 E3 C4 (E,G natural = out-of-key)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
