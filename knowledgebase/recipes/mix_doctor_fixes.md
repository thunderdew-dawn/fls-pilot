# Controller Fixes and Tempo Scaling

- **Date:** 2026-05-23
- **Agent/Author:** System Migration
- **Topic:** SysEx and Tempo Bugs in Controller Script
- **Affected File/API:** `fl_controller/FLStudioMCP/device_FLStudioMCP.py`, `midi`
- **Confidence Level:** `implementation_verified`
- **Source/Method:** `FIX_REPORT.md` post-mortem tracking bugs in SysEx routing and tempo mapping. FL Studio v25.2.5 [build 5319], Windows.

## Context
Diagnosing bridge failures where the server's heartbeat timed out or `set_tempo` resulted in severely collapsed BPM values.

## Observation & Result
### 1. FL MIDI routing — duplicate output on Port 42
- Both `FLStudioMCP RX` and `FLStudioMCP TX` were enabled as outputs on Port 42. `device.midiOutSysex()` routes by matching Port number, creating ambiguity. Heartbeats went to `RX` (which the server does not read) instead of `TX`.
- **Fix:** Disable `FLStudioMCP RX` (output) and `FLStudioMCP TX` (input). Keep RX input and TX output.

### 2. SysEx Callback (`OnSysEx` missing)
- FL 25.2.5 delivers incoming SysEx to the `OnSysEx(event)` callback, but the old script only implemented `OnMidiMsg`. Inbound commands were silently dropped.
- **Fix:** Refactored SysEx handling into a `_handle_request_sysex(event, source)` helper and added `OnSysEx`.

### 3. `set_tempo` value mapping
- `midi.REC_Updated` does not exist on this build (`AttributeError`). The correct constant is `midi.REC_UpdateValue`.
- The `midi.REC_FromMIDI` flag made `processRECEvent` interpret the value as a normalized MIDI fraction (0–65536) instead of raw native value. Passing `bpm * 1000` collapsed tempo to ~10 BPM.
- **Fix:** Use `midi.REC_UpdateValue | midi.REC_UpdateControl` without `REC_FromMIDI`.

## Tested Values
- Bridge tested end-to-end (ping, get_tempo, set_tempo, play, get_play_state, stop).

## Known Pitfalls / Open Questions
- Stale editable installs can cause the server to point to old codebase versions.
- The two virtual MIDI ports must always share the same Port number (e.g., 42).
- After editing the repo controller, it must be copied to `Documents\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP\` and FL must be reloaded.

## Next Recommended Action
- Ensure virtual MIDI ports are strictly separated (one exclusively for input, one exclusively for output).
