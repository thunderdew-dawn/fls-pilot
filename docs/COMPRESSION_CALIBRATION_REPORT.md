# flstudio-mcp — Compression Calibration Report (Fruity Limiter, COMP section)

**Version:** 0.3.0 · **Env:** FL Studio Producer Edition v25.2.5 [build 5319], MIDI scripting v40, Windows, Python 3.12 · **Date:** 2026-05-25

Compression intents **Slice 1 — detect + calibrate only.** Target: **Fruity
Limiter on mixer track 9 (Drums)**. No intent logic, no conversion functions
yet (Slice 2). Source: `scripts/calibrate_limiter.py` (snapshots + restores all
swept params).

---

## 1. Detection (confirmed, not hardcoded)

`plugin_list(9)` → **`Fruity Limiter` at slot 4** (0-based). The GUI's "Slot 5"
is the 1-based label; the API index is **4**.

`plugin_get_params(9, 4)` → **18 params** in one flat list. Fruity Limiter runs
**gate → compressor → limiter** as one chain; the GUI LIMIT / COMP / GATE tabs
only switch which knobs are visible (they are NOT a mode that disables stages).

### Full param dump, grouped
| # | Param | Default value | Section |
|---|---|---|---|
| 0 | Gain | 0.0 dB | GLOBAL (makeup) |
| 1 | Soft saturation threshold | 0.0 dB | GLOBAL |
| 2 | Limiter ceiling | 0.0 dB | LIMIT |
| 3 | Limiter attack time | 2.00 ms | LIMIT |
| 4 | Limiter attack curve | 3 | LIMIT |
| 5 | Limiter release time | 85.53 ms | LIMIT |
| 6 | Limiter release curve | 3 | LIMIT |
| 7 | Limiter peak window | 10.00 ms | LIMIT |
| 8 | **Comp threshold** | 0.0 dB | **COMP** |
| 9 | **Comp ratio** | 1:1.0 | **COMP** |
| 10 | **Comp knee** | 0 % | **COMP** |
| 11 | **Comp attack time** | 0.00 ms | **COMP** |
| 12 | **Comp release time** | 248.22 ms | **COMP** |
| 13 | **Comp curve** | "" (opaque) | **COMP** |
| 14 | **Comp RMS window** | 1.00 ms | **COMP** |
| 15 | Noise gain | 0.0 dB | GATE |
| 16 | Noise threshold | −INF dB | GATE |
| 17 | Noise release time | 50.01 ms | GATE |

> There is **no COMP-specific makeup gain** — the global **Gain (idx 0)** is the
> makeup control.

---

## 2. 🚩 The COMP-enable / silent-fail finding (the #1 risk)

- **No enable toggle and no mode switch exist.** You cannot "turn COMP on".
- **The compressor is INERT at default:** `Comp ratio = 1:1.0` and
  `Comp threshold = 0.0 dB`. At ratio 1:1 it does nothing regardless of threshold.
- **`Comp ratio` is BIDIRECTIONAL around norm 0.5** — the real trap:
  - norm **< 0.5** → displayed `1:X` = **upward / expansion** (not what we want)
  - norm **= 0.5** → `1:1.0` = no effect
  - norm **> 0.5** → displayed `X:1` = **downward compression** ✅
- **Therefore any "compress" intent MUST set ratio norm > 0.5 AND lower the
  threshold (norm < 1.0).** Lowering threshold alone (ratio 1:1) = silent no-op;
  raising ratio alone (threshold at 0 dB, nothing exceeds it) = barely anything.

---

## 3. Calibration — curve shapes (norm 0→1, 0.05 steps)

| Param (idx) | Shape | Mapping / notes |
|---|---|---|
| **Comp threshold** (8) | **non-linear** (steep low, gentle high) | norm 0→−60 dB, 0.5→−11.2, 0.85→−3, 1.0→**0 dB**. Lower norm ⇒ lower threshold ⇒ more gain reduction. → **table interp** |
| **Comp ratio** (9) | **bidirectional, non-linear >0.5** | compression half only (see table below). → **table interp (upper half)** |
| **Comp knee** (10) | **linear** | `% = 200·norm − 100` (−100 % … +100 %, 0 % @ 0.5) |
| **Comp attack** (11) | **exponential** | 0 → 1000 ms (0 ms @0, 42.8 ms @0.5) |
| **Comp release** (12) | **exponential** | 0 → 2000 ms (85.5 ms @0.5, 248 ms @0.667) |
| **Comp RMS window** (14) | **exponential** | 0 → 1000 ms (same family as attack) |
| **Comp curve** (13) | **opaque** | value-string always `""`; can set norm but can't read it — leave at default |
| **Gain / makeup** (0) | ~linear (upper half) | 0 dB @0.5 → +18.1 dB @1.0 (−INF @0) |

### Comp ratio → norm (compression half, the key Slice-2 table)
| norm | ratio | norm | ratio |
|---|---|---|---|
| 0.50 | 1:1 | 0.80 | 4.6:1 |
| 0.55 | 1.2:1 | 0.85 | 6.6:1 |
| 0.60 | 1.5:1 | 0.90 | 9.4:1 |
| 0.65 | 1.9:1 | 0.95 | 13.7:1 |
| 0.70 | 2.5:1 | 1.00 | 20:1 |
| 0.75 | 3.3:1 | (≈0.785) | (≈4:1) |

### Comp threshold → norm (key points)
| norm | dB | norm | dB |
|---|---|---|---|
| 1.00 | 0.0 | 0.50 | −11.2 |
| 0.85 | −3.0 | 0.25 | −19.6 |
| 0.70 | −6.3 | 0.05 | −35.4 |
| 0.60 | −8.7 | 0.00 | −60.0 |

---

## 4. Implications for Slice 2 (compression intents)

- A "compress / punch / glue" intent = one `safe_write_group` that sets, together:
  **ratio** (norm > 0.5 via the ratio table) **+ threshold** (lowered via the
  threshold table) **+ attack/release** (exp curves) **+ optional makeup** (global
  Gain) — so a single `fl_rollback_last_change` reverts the whole move.
- **threshold / ratio / attack / release** need **table-interpolation** (no clean
  closed form). **knee** is linear. **makeup** rides the global Gain.
- Leave **Comp curve** (opaque) and the **LIMIT** / **GATE** sections untouched
  unless an intent explicitly targets them.
- Guard the intent to the right plugin (name contains "limiter"), and never edit
  a LIMIT/GATE param when meaning a COMP one (wrong-tab = wrong knob).

---

## 5. Restore verification

All 8 swept params (`Comp threshold/ratio/knee/attack/release/RMS window/curve`
+ global `Gain`) were snapshotted before the sweep and restored after — readback
confirmed each back to its original (ratio `1:1.0`, threshold `0.0 dB`, etc.).
The Limiter was left exactly as found.

## 6. Files
- `scripts/calibrate_limiter.py` — auto-detects the Limiter slot, sweeps the COMP
  params + makeup Gain, snapshots + restores. READ/calibration only.
