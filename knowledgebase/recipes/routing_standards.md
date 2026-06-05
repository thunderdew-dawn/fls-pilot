# Mixing Intents & Routing Principles

- **Date:** 2026-05-25
- **Agent/Author:** System Migration
- **Topic:** Controller/Server Architecture & Mixing/Routing Tools
- **Affected File/API:** `tools/mixing.py`, `tools/routing.py`, FL controller scripts
- **Confidence Level:** `implementation_verified`
- **Source/Method:** `MIXING_ROUTING_REPORT.md`. FL Studio Producer Edition v25.2.5 [build 5319], Windows.

## Context
Defining the architecture principle for routing and orchestration, and summarizing mixing intent development (EQ, Reverb, Delay) based on empirical calibration.

## Observation & Result
### 1. Architecture principle (the big lesson)
- **Controller stays THIN; the server does the THINKING.**
- Heavy loops in the controller sandbox stall FL (e.g., timing out at 20s). The controller should only return cheap RAW data and do simple writes.
- All orchestration (empty/unused detection, grouping) lives on the server (plain Python). This also removes the need for FL controller reloads for logic changes.

### 2. Plugin Calibration
- Every plugin is calibrated individually (e.g. Fruity Parametric EQ 2: frequency is logarithmic, level is linear dB, width is linear %).
- Native FL plugins expose real param names + small counts (EQ2=36, Reeverb=15, Delay3=26). Name-based addressing is highly reliable for them.

### 3. Mixing Intents
- Applied as one `safe_write_group` unit so a single `fl_rollback_last_change` reverts the whole move.

### 4. Routing Read & Write
- Judgement for empty/unused tracks is purely server-side.
- The `route:src:dst` snapshot scope captures routing changes.
- Grouping (`fl_group_tracks`) uses exclusive bus grouping (sources to Master OFF, sources to Bus ON, Bus to Master ON). Applied as ONE `safe_write_group`.

## Tested Values
- `test_mixing_intents.py`, `test_reverb_delay_intents.py`, `test_routing_read.py`, `test_group_tracks.py`.

## Known Pitfalls / Open Questions
- SysEx payload is limited (~1.5 KB), necessitating pagination.
- Controller reload via "Update MIDI scripts" is flaky. A full FL restart is the reliable reload.
- The old heavy `_h_detect_cleanup` is dead code in the controller and must be removed to prevent stalls.

## Next Recommended Action
- Continue moving heavy logic from the controller to the server.
