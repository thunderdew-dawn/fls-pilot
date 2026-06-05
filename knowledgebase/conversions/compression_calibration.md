# Fruity Limiter Compression Calibration

- **Date:** 2026-05-25
- **Agent/Author:** System Migration
- **Topic:** Compression Calibration Curves (Fruity Limiter, COMP section)
- **Affected File/API:** Fruity Limiter plugin parameters
- **Confidence Level:** `measured_repeated`
- **Source/Method:** `scripts/calibrate_limiter.py` (sweeps COMP params 0->1, snapshots + restores). FL Studio Producer Edition v25.2.5 [build 5319], Windows.

## Context
Calibrating Fruity Limiter's COMP section to enable compression intents. Finding the mapping between normalized values [0, 1] and the actual dB/ratio values.

## Observation & Result
### 1. Detection
- `Fruity Limiter` exposes 18 params in one flat list. It runs gate -> compressor -> limiter as one chain.
- Key COMP Indices: Threshold (8), Ratio (9), Knee (10), Attack (11), Release (12), RMS window (14).
- There is NO COMP-specific makeup gain — the global `Gain (idx 0)` is the makeup control.

### 2. 🚩 The COMP-enable / silent-fail finding (the #1 risk)
- **No enable toggle exists.** The compressor is INERT at default (`Comp ratio = 1:1.0` and `Comp threshold = 0.0 dB`).
- **`Comp ratio` is BIDIRECTIONAL around norm 0.5**:
  - norm < 0.5 → `1:X` (upward expansion)
  - norm = 0.5 → `1:1.0` (no effect)
  - norm > 0.5 → `X:1` (downward compression) ✅
- Any "compress" intent MUST set ratio norm > 0.5 AND lower the threshold (norm < 1.0). Lowering threshold alone = silent no-op.

### 3. Calibration Curves (norm 0→1)
- **Threshold (8):** non-linear (steep low, gentle high). norm 1.0 = 0 dB, 0.5 = -11.2 dB, 0.85 = -3 dB. → **Table interp**.
- **Ratio (9):** bidirectional, non-linear >0.5. 0.50 = 1:1, 0.65 = 1.9:1, 0.80 = 4.6:1, 1.00 = 20:1. → **Table interp (upper half)**.
- **Knee (10):** linear. `% = 200·norm - 100` (-100% to +100%).
- **Attack (11):** exponential. 0 → 1000 ms.
- **Release (12):** exponential. 0 → 2000 ms.
- **Gain / makeup (0):** ~linear upper half. 0.5 = 0 dB, 1.0 = +18.1 dB.

## Tested Values
- 8 swept params (`Comp threshold/ratio/knee/attack/release/RMS window/curve` + global `Gain`) snapped and restored successfully.

## Known Pitfalls / Open Questions
- Do not edit LIMIT or GATE tab params when targeting COMP intents.
- Comp curve (13) is opaque (value string always `""`). Leave at default.

## Next Recommended Action
- Implement "compress / punch / glue" intents using `safe_write_group` setting ratio + threshold + attack/release + optional makeup together.
- Use table interpolation for threshold / ratio / attack / release.
