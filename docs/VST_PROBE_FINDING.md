# flstudio-mcp — 3rd-party VST probe finding

**Version:** 0.3.0 · **Env:** FL Studio Producer Edition v25.2.5 [build 5319], Windows · **Date:** 2026-05-25

**Question (make-or-break, like the native param-name question was for Phase 1B):**
does FL's VST wrapper expose **real param names** and **readable value-strings**
for a 3rd-party plugin on this machine? If yes, the calibrate→intent pattern
works for VSTs exactly like native plugins.

## Verdict: YES ✅ (best case)

Probed **FabFilter Pro-C 3** (`scripts/probe_vst.py`, auto-detected at
**track 8, slot 4**):

- **`getParamName` → REAL names** — `Threshold, Ratio, Knee, Range, Attack,
  Release, Lookahead, Hold, Mix, Output Level, Style, Auto Gain, …`.
  **100/100 named, zero "Param N".**
- **`getParamValueString` → READABLE UNITS** — `-16.00 dB`, `3.50:1`,
  `0.725 ms`, `100.0 ms`, `+7.35 dB`, `100.0%`. **100/100 non-empty.**
- So sweep+readback **calibration is feasible for this VST**, same method as the
  native Fruity plugins.

## Details
- `getParamCount` = **4240** (the FL VST-wrapper signature), **but the real
  params sit at LOW indices** — 100 non-empty found scanning 0–1024 (the comp
  core is all at idx 0–99). Scanned via the existing paginated `plugin_get_params`
  (skips empty names, 150/page) — no controller stall.
- **Pro-C 3 ratio is a clean `X:1`** (e.g. `3.50:1`) — **no bidirectional trap**
  (unlike Fruity Limiter, whose ratio flips to `1:X` expansion below norm 0.5).

## Addressing recommendation
- **Core comp params are name-addressable** (`Threshold/Ratio/Attack/Release/
  Knee/Range/Mix/Output Level` — short, unique names).
- For the full set, **cache indices + re-validate `getParamName(index)` on
  connect** — the controller truncates names to 30 chars (long sidechain-EQ
  names can collide), and a VST update could shift indices.

## Next
Calibrate the Pro-C 3 COMP params (Slice 2), then build VST compression intents
on top — reusing the proven calibrate→table-interp→intent pattern.
