# Arrangement API Bounds

- **Date:** 2026-05-25
- **Agent/Author:** System Migration
- **Topic:** Arrangement and Playlist Clip Capabilities
- **Affected File/API:** `playlist`, `arrangement`, `patterns` modules
- **Confidence Level:** `implementation_verified`
- **Source/Method:** API probe via `dir()` and `scripts/probe_arrangement.py`. FL Studio Producer Edition v25.2.5 [build 5319], Windows.

## Context
Determining how "arrangement" can realistically be programmed via the FL Studio API.

## Observation & Result
### 1. API Boundary
- **Playlist:** `track mute/solo/name/color/select` + live-performance mode. **There is NO `addClip`/`placeClip`/`addPattern` or timeline-authoring function.** Cannot place pattern clips on the playlist programmatically.
- **Arrangement:** `addAutoTimeMarker`, `getMarkerName`, `jumpToMarker`, `currentTime`, `selectionSet/Start/End/Clear/IsActive`. Named markers are supported. No `removeMarker` (undo to remove).
- **Patterns:** `jumpToPattern` (creates), `setPatternName`, `getPatternName`, `clonePattern`, `findFirstNextEmptyPat`, `getPatternLength`, `isPatternDefault`. Create / name / clone / fill are supported.
- **Verdict:** True automated playlist layout (clip placement) is impossible. Arrangement is limited to prepping, naming, and filling section PATTERNS, and marking the song structure with named markers. The USER must manually drag patterns onto the playlist.

### 2. Multi-Pattern Mechanic (Proven)
- `arrange_new_pattern(name)`: finds empty pattern, jumps (selects it), renames.
- `arrange_clone_pattern(src, new_name)`: clones and renames.
- `arrange_add_marker(bar, name)`: adds marker at `(bar-1)*ppb`.
- Note fill reuses the Piano Roll bridge (`fl_write_piano_roll_notes`).
- **Make-or-break confirmed:** the note bridge writes into the CURRENTLY SELECTED pattern and focused channel. The flow `arrange_new_pattern` (which selects) -> `apply_notes` lands notes in the right pattern.

## Tested Values
- Marker placement, pattern creation and note application into separate generated patterns (INTRO, VERSE, VERSE2).

## Known Pitfalls / Open Questions
- **Note-bridge setup:** The Piano roll must be OPEN and `MCP_Apply` run ONCE from its Scripting menu per session so `Ctrl+Alt+Y` targets it. If not set up, fills silently no-op.
- **Channel targeting:** The bridge writes to the FOCUSED channel. Multi-instrument sections need explicit channel selection.

## Next Recommended Action
- Implement chord progressions using the proven multi-pattern mechanic. Enhance channel targeting for multi-instrument sections.
