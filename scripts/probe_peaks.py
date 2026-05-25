#!/usr/bin/env python3
"""Level-awareness Slice 1: probe mixer.getTrackPeaks (READ ONLY).

Peaks are only meaningful while audio is PLAYING. Run this once with transport
STOPPED (expect near-zero), then START playback in FL and run it again -- it
samples ~2 s (20 reads) and reports min/max/avg + dB.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/probe_peaks.py [track]      # default 9 (Drums)

modes (FL): mixer.getTrackPeaks(index, mode) -> 0 = L, 1 = R, 2 = max(L,R).
Values are LINEAR (1.0 ~ 0 dBFS, can exceed 1.0).
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol                       # noqa: E402
from fl_studio_mcp.connection import get_bridge           # noqa: E402

TRACK = int(sys.argv[1]) if len(sys.argv) > 1 else 9
SILENCE = 1e-4


def to_db(v):
    if v is None or v <= 1e-6:
        return None                       # -inf / silence
    return 20.0 * math.log10(v)


def fmt_db(v):
    d = to_db(v)
    return "-inf (silence)" if d is None else "%.1f dB" % d


def main() -> int:
    b = get_bridge()
    b.open()
    if not b.is_alive():
        print("Bridge not alive -- FL open? controller (slice-peaks-v6) loaded? daemon up?")
        return 1

    playing = bool(b.call(protocol.CMD_GET_PLAY_STATE).get("playing"))
    print("transport: %s" % ("PLAYING" if playing else "STOPPED"))
    print("getTrackPeaks modes -> 0=L, 1=R, 2=max(LR); values LINEAR (1.0 ~ 0 dBFS)")

    pk = b.call(protocol.CMD_MIXER_GET_PEAKS, {"track": TRACK})
    print("\ninstant peaks track %d:  L=%s  R=%s  max=%s   (max -> %s)"
          % (TRACK, pk.get("peak_l"), pk.get("peak_r"), pk.get("peak_max"), fmt_db(pk.get("peak_max"))))

    n = 20
    print("\nsampling %d reads over ~2s (peak_max)..." % n)
    vals = []
    for _ in range(n):
        v = b.call(protocol.CMD_MIXER_GET_PEAKS, {"track": TRACK}).get("peak_max")
        if v is not None:
            vals.append(v)
        time.sleep(0.1)

    if not vals or max(vals) < SILENCE:
        print("  -> NO SIGNAL (near-zero). If you expected level: is playback running "
              "and is track %d actually passing audio?" % TRACK)
        print("  (this is the correct 'stopped/silence' result -- not a real level)")
        return 0

    mn, mx, av = min(vals), max(vals), sum(vals) / len(vals)
    print("  peak_max  linear:  min=%.5f  max=%.5f  avg=%.5f" % (mn, mx, av))
    print("  peak_max  dB:      min=%s  max=%s  avg=%s" % (fmt_db(mn), fmt_db(mx), fmt_db(av)))
    print("\n  derived 'current level': peaking to %s, sitting ~%s on average"
          % (fmt_db(mx), fmt_db(av)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
