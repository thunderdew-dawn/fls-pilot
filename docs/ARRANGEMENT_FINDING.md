# flstudio-mcp — Arrangement findings + Slice 1 (multi-pattern mechanic)

**Version:** 0.3.0 · **Env:** FL Studio Producer Edition v25.2.5 [build 5319], Windows · **Date:** 2026-05-25

## 1. API boundary (probe via dir() on the live modules)

`scripts/probe_arrangement.py` (the `api_probe` controller command):

- **playlist (42 fns):** track mute/solo/name/color/select + **live-performance
  mode** (`triggerLiveClip`, `getLiveBlockStatus`, …) + view/selection. **There
  is NO `addClip`/`placeClip`/`addPattern`/timeline-authoring function.**
  → **Cannot place pattern clips on the playlist programmatically.** (make-or-break = NO)
- **arrangement (12 fns):** `addAutoTimeMarker`, `getMarkerName`, `jumpToMarker`,
  `currentTime`, `selectionSet/Start/End/Clear/IsActive`. **Named markers YES.**
  No `removeMarker` (undo to remove). No arrangement-switching fn.
- **patterns (27 fns):** `jumpToPattern` (creates), `setPatternName`,
  `getPatternName`, `clonePattern`, `findFirstNextEmptyPat`, `getPatternLength`,
  `isPatternDefault`. **Create / name / clone / fill YES.**
- ppq = 96, ppb = 384 (4/4).

### Verdict — what "arrangement" realistically IS in FL via the API
**(b) prep + name + fill section PATTERNS, and MARK the song structure with
named markers; the USER drags the patterns onto the playlist.** Not full
auto-layout (clip placement is impossible).

## 2. Slice 1 — multi-pattern mechanic (PROVEN)

Primitives (`tools/arrange.py` + controller):
- `arrange_new_pattern(name)` — `findFirstNextEmptyPat`/count+1, `jumpToPattern`
  (this SELECTS it), `setPatternName`. Returns the index.
- `arrange_clone_pattern(src, new_name)` — `clonePattern` + rename (copies notes).
- `arrange_add_marker(bar, name)` — `addAutoTimeMarker((bar-1)*ppb, name)`.
- Note fill reuses the Phase-2 piano-roll bridge (`fl_write_piano_roll_notes`).

**Make-or-break confirmed:** the note bridge writes into the **currently
SELECTED pattern** (and the focused channel). So the flow `arrange_new_pattern`
(selects) -> `apply_notes` lands each section's notes in its own pattern.
Verified live: INTRO got C-E-G, VERSE got A-C-E (different per pattern), VERSE2
cloned VERSE, markers placed at bars 1 & 5.

Chord progressions need no new capability — just a longer note list
(chords x bars via `time_bars`/`length_bars`) in one `apply_notes` call.

## 3. Gotchas / TODO
- **Note-bridge setup** (per FL session): the Piano roll must be OPEN and
  `MCP_Apply` run ONCE from its Scripting menu so `Ctrl+Alt+Y` targets it.
  If not set up, fills silently no-op.
- **`triggered:True` is NOT confirmation** the script ran — the bridge can only
  confirm it sent the hotkey + focused FL. Hardening TODO.
- **Channel targeting:** the bridge writes to the FOCUSED channel. Multi-
  instrument sections need explicit channel selection (Slice 2).
- `arrange_new_pattern` re-runs create duplicate-named patterns (no reuse of a
  named-but-empty pattern). Fine for now; refine later.
