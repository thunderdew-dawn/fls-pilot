#!/usr/bin/env python3
"""Offline test: analyze_bands on SYNTHETIC low/high sine WAVs (no FL).

python scripts/test_reference_match.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from fls_pilot.tools.audio import analyze_bands  # noqa: E402

SR = 22050
_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    _P += 1 if cond else 0
    _F += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


def sine(freq, secs=2.0):
    t = np.linspace(0, secs, int(SR * secs), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="flmcp_ref_"))
    low, high = d / "low.wav", d / "high.wav"
    sf.write(str(low), sine(80), SR)  # 80 Hz -> low band (<250)
    sf.write(str(high), sine(8000), SR)  # 8 kHz -> high band (>4000)

    rl, rh = analyze_bands(str(low)), analyze_bands(str(high))
    print("low.wav  bands:", rl["bands_pct"], " peak_db", rl["peak_db"])
    print("high.wav bands:", rh["bands_pct"], " peak_db", rh["peak_db"])

    check("80 Hz sine -> LOW band dominant", rl["bands_pct"]["low"] > 60, str(rl["bands_pct"]))
    check("8 kHz sine -> HIGH band dominant", rh["bands_pct"]["high"] > 60, str(rh["bands_pct"]))
    check("level reported (peak_db near 0)", rl["peak_db"] is not None and rl["peak_db"] > -10)

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
