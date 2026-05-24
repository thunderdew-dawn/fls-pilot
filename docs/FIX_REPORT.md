# FL Studio MCP — Fix Report

- **Date:** 2026-05-23
- **Environment:** FL Studio Producer Edition v25.2.5 [build 5319], MIDI scripting v40, embedded Python 3.12, Windows, loopMIDI
- **Canonical project:** `C:\Users\<you>\flmcp\flstudio-mcp` (v0.2.0)
- **Deployed controller:** `C:\Users\<you>\Documents\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP\device_FLStudioMCP.py`

---

## 1. Objective

Two `flstudio-mcp` extractions existed on disk: a stale **v0.1** (`C:\Users\<you>\Code\flstudio-mcp\flstudio-mcp`, file-queue era) and a working **v0.2** elsewhere. The editable install / `test_bridge.py` resolution was ambiguous. Goal: collapse to **one clean v0.2 folder**, verify the bridge end-to-end, and remove the stale copy.

## 2. Final Status — COMPLETE (bridge fully working, 7/7)

| Check | Result |
|---|---|
| ping | OK |
| get_tempo | OK — `145.0 / 145000` |
| set_tempo to 150 | OK — `150.0` (exact) |
| restore to 145 | OK — `145.0` (exact) |
| play | OK |
| get_play_state | OK |
| stop | OK |

---

## 3. Root Causes (3 distinct issues)

The initial assumption was "the only problem is the stale folder," but three separate issues were found.

### (1) Stale folder / wrong editable install — the known one
The editable install and `test_bridge.py` resolution were ambiguous between the v0.1 and v0.2 trees. Fixed by a clean v0.2 extract and re-pointing the editable install.

### (2) FL MIDI routing — duplicate output on Port 42 (config bug)
Both `FLStudioMCP RX` and `FLStudioMCP TX` were enabled as **outputs** on Port 42. `device.midiOutSysex()` routes by matching Port number, so it became ambiguous and the heartbeat went to `RX` (which the server does not read) instead of `TX`. Symptom: `Heartbeat age: None`.

Fix (FL Options > MIDI Settings):
- Input: keep `FLStudioMCP RX` enabled, Controller type = FLStudioMCP, Port 42.
- Output: keep `FLStudioMCP TX` enabled, Port 42.
- Disable `FLStudioMCP RX` (output) and `FLStudioMCP TX` (input).

### (3) Controller script — two genuine code bugs (found by reading the code)

**3a. `OnSysEx` missing.** FL 25.2.5 delivers incoming SysEx to the `OnSysEx(event)` callback, but the script only implemented `OnMidiMsg`. So inbound commands were silently dropped (request timeout), while the outbound heartbeat (via `OnIdle`) still worked — which made the failure misleading.

**3b. `set_tempo` value mapping.**
- `midi.REC_Updated` does not exist on this build (`AttributeError`); the correct constant is `midi.REC_UpdateValue`.
- The `midi.REC_FromMIDI` flag made `processRECEvent` interpret the value as a normalized MIDI fraction (0–65536) instead of the raw native value. Passing `bpm * 1000` (e.g. 145000) collapsed the tempo to ~10 BPM.

---

## 4. Changes Made

### Code edits — `fl_controller/FLStudioMCP/device_FLStudioMCP.py`
Applied to the canonical repo **and** the deployed Hardware copy (kept in sync).

1. Refactored the SysEx-handling body into a `_handle_request_sysex(event, source)` helper. Added an **`OnSysEx`** callback; `OnMidiMsg` also delegates to the same helper so it works regardless of which callback the FL build uses.
2. `_h_set_tempo` flags changed:
   - `REC_Updated` -> `REC_UpdateValue`
   - removed `REC_FromMIDI` (use the raw native value, consistent with the `get_tempo` scale)

```diff
- flags = midi.REC_Updated | midi.REC_UpdateControl | midi.REC_FromMIDI
+ flags = midi.REC_UpdateValue | midi.REC_UpdateControl
```

### Filesystem
- Clean v0.2 extract -> `C:\Users\<you>\flmcp\flstudio-mcp`
- `pip install -e . --force-reinstall --no-deps` -> editable install now points at the clean folder (`__version__ == 0.2.0`, module path under that tree)
- Deleted stale `C:\Users\<you>\Code\flstudio-mcp\flstudio-mcp` and `C:\Users\<you>\Downloads\flstudio-mcp-v0.1.0.zip`

### FL MIDI settings (final state)
- Input `FLStudioMCP RX` — Port 42, Controller type FLStudioMCP — enabled
- Output `FLStudioMCP TX` — Port 42 — enabled
- `FLStudioMCP RX` output and `FLStudioMCP TX` input — disabled

---

## 5. Progress Timeline

| Step | Description | Status |
|---|---|---|
| 1 | Locate v0.2 zip (`Music\FL MCP\flstudio-mcp-v0.2.0.zip`) | Done |
| 2 | Clean extract -> `$HOME\flmcp\flstudio-mcp` (v0.2.0) | Done |
| 3 | Re-point editable install (`__version__ 0.2.0`, clean module path) | Done |
| 4 | Verify ports (`RX 9` / `TX 9` matched) | Done |
| 5 | Bridge test — first line `Port to FL:` (v0.2 confirmed), 3 bugs fixed -> 7/7 | Done |
| 6 | Tempo scale — `raw = bpm * 1000`, `_tempo_scale() = 1000` correct, no edit | Done |
| 7 | Stale cleanup — v0.1 folder + zip deleted (safety-verified) | Done |

---

## 6. Maintenance Notes

- After editing the repo controller (`fl_controller/...`), copy it to `Documents\...\Hardware\FLStudioMCP\` and use FL **Reload script** — the deployed copy is what FL runs.
- The two virtual MIDI ports must always share the **same Port number (42)**; the controller uses it to route `device.midiOutSysex` responses to the correct output.
- Stale-vs-clean check: v0.1 `test_bridge.py` prints `Bridge root:` / `Heartbeat age: None`; v0.2 prints `Port to FL:` / `Port from FL:`.

---

## 7. Outstanding / Optional

- Empty folder `C:\Users\<you>\Code\flstudio-mcp` remains and can be removed.
- The two controller fixes (`OnSysEx`, `set_tempo`) are genuine upstream bugs worth contributing back to `paper-kasu/flstudio-mcp`.
