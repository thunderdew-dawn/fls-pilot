# API Capability and Safety Audit

This document is the gate for the API-backed production-suite branch. It keeps
feature selection grounded in the FL Studio scripting APIs and in the project's
contribution rule: project-modifying tools must be reversible.

## Safety Contract

No tool may mutate FL Studio project state unless it can be rolled back through
the MCP safety layer. Read-only actions are the only exception.

Every persistent write must provide:

1. A scoped snapshot before the write.
2. The smallest practical FL command or generated script operation.
3. Readback of the affected state.
4. A persisted changelog entry with restore data.
5. A user-facing before/after result.
6. A rollback path through MCP.

Transient runtime actions, such as play/stop and note preview, do not need
project rollback, but they must still fail safely and must not leave stuck state.

If a capability cannot satisfy this contract, it stays read-only, dry-run-only,
or manual-instruction-only.

## Evidence Levels

Use these labels before implementing a feature:

| Level | Meaning | Allowed implementation |
|---|---|---|
| `documented` | Official Image-Line docs expose the API. | Implement after live smoke test. |
| `documented-unconfirmed` | Official docs expose the API, but a live smoke failed or was state-dependent. | Keep behind targeted probes/manual guidance until a false-positive check verifies target state, focus/selection, indexing, readback timing, and rollback. |
| `live-probed` | Current FL build exposes and executes the API. | Implement with version/capability reporting. |
| `existing` | Current MCP already exposes it safely. | Reuse; do not duplicate. |
| `probe-needed` | Name exists or docs imply a path, but behavior is unverified. | Build a probe first, not a user tool. |
| `api-limited` | No stable API path is known. | Read-only plan or manual instruction only. |

Primary references:

- MIDI scripting API: <https://www.image-line.com/fl-studio-learning-content/fl-studio-online-manual/html/midi_scripting.htm>
- Piano Roll scripting API: <https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll_scripting_api.htm>
- Edison / Audio Editor Script Tool: <https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/plugins/editortool_run.htm>
- Slicex: <https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/plugins/Slicex.htm>
- Slicex Wave Editor: <https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/plugins/Slicex%20Editor.htm>
- Sampler Channel settings: <https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/chansettings_sampler.htm>

## Current Safety Baseline

Run the local audit before adding write tools:

```bash
.venv/bin/python scripts/audit_tool_safety.py
```

The current branch has no static write gaps; this is the PR gate:

```bash
.venv/bin/python scripts/audit_tool_safety.py --fail-on-gaps
```

That command should pass today and fail if a new unsafe write tool is added.
For historical context, the pre-fix ratchet was:

```bash
.venv/bin/python scripts/audit_tool_safety.py --max-write-gaps 9
```

For downstream tooling or PR bots, the same audit can emit JSON:

```bash
.venv/bin/python scripts/audit_tool_safety.py --format json
```

The audit statically classifies FastMCP tools as:

- `read-only`: no FL mutation found.
- `transient`: runtime action that should not persist in the project.
- `external-write`: writes outside FL, for example MIDI file export.
- `server-state`: changes MCP/server state only.
- `write-safe`: uses `safety.safe_write` or `safety.safe_write_group`.
- `write-gap`: mutates FL without the rollback contract.
- `needs-review`: cannot be confidently classified statically.

The initial gaps on this branch were older direct-write tools:

- Tempo writes in transport.
- Arrangement pattern/marker writes.
- Piano Roll generated-script writes and transforms.
- Composer tools that select a channel and call the Piano Roll bridge.

They now route through the safety layer. Piano Roll writes are backed by FL
Studio undo: the generated scripts wrap edits in `flp.score.undoSection()` when
available, and MCP rollback invokes `general.undoUp()`.

The current static baseline reports:

- 57 `write-safe` tools.
- 0 `write-gap` tools.
- 49 `read-only` tools.
- 5 `transient` runtime tools.
- 4 `server-state` tools.
- 2 `external-write` tools.

`--fail-on-gaps` is the current no-regression gate.

## API-Backed Feature Packs

### Step Sequencer

Status: `documented`, `live-probed`.

Useful API:

- `channels.getGridBit`
- `channels.setGridBit`
- `channels.getStepParam`
- `channels.getCurrentStepParam`
- `channels.setStepParameterByIndex`
- Step parameter constants such as `pVelocity`, `pPan`, `pShift`, `pRepeat`.

MVP:

- Read a channel step grid.
- Set/clear steps.
- Write a full pattern.
- Shift a pattern.
- Randomize velocity with dry-run preview.

Safety requirement:

- Snapshot all changed grid bits and step parameters before writing.
- Apply a full-pattern write as one grouped rollback unit.

### Channel Organizer

Status: `documented`, `live-probed`.

Useful API:

- `channels.getChannelName` / `setChannelName`
- `channels.getChannelColor` / `setChannelColor`
- `channels.getChannelType`
- `channels.getTargetFxTrack` / `setTargetFxTrack`
- `channels.getChannelVolume` / `setChannelVolume`

MVP:

- Rename/color channels.
- Classify channel types, including audio clip/generator/automation.
- Assign unrouted channels to mixer tracks.
- Apply confirmed audio defaults such as channel volume 50%.

Current shipped slice:

- `fl_get_channel_details`
- `fl_detect_unassigned_channels`
- `fl_set_channel_name`
- `fl_set_channel_mixer_track`
- `fl_assign_channel_to_free_mixer_track`

Safety requirement:

- Add snapshot scopes for channel name, color, target mixer track, and volume.
- Keep Stretch Pro/Normalize out of the MVP until a real API path is proven.

### Pattern Management

Status: `documented`, `live-probed`; `setPatternLength` is
`documented-unconfirmed` on FL Studio Producer Edition v25.2.5 build 5055 until
the targeted false-positive probe verifies whether the documented v39 API is
absent, stale-controller related, target-state dependent, or readback delayed.

Useful API:

- `patterns.patternNumber`
- `patterns.patternCount`
- `patterns.getPatternName` / `setPatternName`
- `patterns.getPatternColor` / `setPatternColor`
- `patterns.getPatternLength` / `setPatternLength`
- `patterns.clonePattern`
- `patterns.movePattern`
- `patterns.jumpToPattern`
- `patterns.findFirstNextEmptyPat`

MVP:

- Detailed pattern list/current/select.
- Rename/color/length.
- Clone/move.

Safety requirement:

- Clone and move need explicit restore behavior.
- Do not implement delete/merge/split until an API-backed rollback story exists.

Current next slice:

- Pattern color and length writes with scoped snapshots. ✅ shipped
- Current pattern selection snapshot/restore for grouped organizer changes.
- Find-empty-pattern as read-only planning support. ✅ shipped
- Clone/move only after live smoke verifies stable readback and restore.

Live evidence and false-positive probes:

- 2026-06-01, controller `channels-v37`: `patterns.setPatternLength` is
  documented, but `api_probe dir` did not expose `setPatternLength` on FL
  Studio Producer Edition v25.2.5 build 5055, and the rollback-safe write
  command returned API unavailable before mutation. Keep the tool
  `documented-unconfirmed` on this build; do not remove support solely from
  this runtime result.

### Playlist Track Organizer

Status: `documented`, `live-probed` for track-level operations.

Useful API:

- `playlist.trackCount`
- `playlist.getTrackName` / `setTrackName`
- `playlist.getTrackColor` / `setTrackColor`
- `playlist.muteTrack`
- `playlist.soloTrack`
- `playlist.selectTrack`

MVP:

- List playlist tracks.
- Rename/color/mute/solo/select playlist tracks.

Safety requirement:

- Snapshot track name/color/mute/solo state.
- Treat select as transient or restore previous selection.

Not currently supported:

- General playlist clip enumeration.
- Stacked/overlapping clip detection.
- Clip movement/deletion.

### Effect Slot Control and Native Mixer EQ

Status: `documented`, partially `live-probed`. Track-slot enable has passed
live smoke. Slot mix and per-slot mute are `documented-unconfirmed` on FL Studio
Producer Edition v25.2.5 build 5055 until the targeted false-positive probe
checks API presence, occupied-slot targeting, selected-track variants, readback
timing, and rollback. Native EQ writes remain `live-probed` where readback
sticks on the tested build/state.

Useful API:

- `mixer.getPluginMixLevel`
- `mixer.setPluginMixLevel`
- `mixer.isTrackSlotsEnabled`
- `mixer.enableTrackSlots`
- `mixer.isTrackPluginValid`
- Live-probed: `getPluginMuteState`, `setPluginMuteState`.
- `mixer.getEqGain` / `setEqGain`
- `mixer.getEqFrequency` / `setEqFrequency`
- `mixer.getEqBandwidth` / `setEqBandwidth`
- `mixer.getEqBandCount`

MVP:

- List effect slots with plugin names and slot mix.
- Set slot mix.
- Bypass/enable all slots on a track.
- Read native mixer EQ.
- Apply simple low/high shaping intents as fallback when no EQ plugin is loaded.
- Per-slot bypass and EQ type changes only after live readback is proven.

Safety requirement:

- Snapshot slot mix and bypass state.
- Snapshot every changed band parameter before writing.
- Do not promise full chain restore; plugin loading/removal is API-limited.

Current next slice:

- Expose a user-facing Effect Slot + Native EQ Pack over the already-probed
  primitives. ✅ shipped
- Add static audit coverage for slot and EQ restore payloads.
- Live-smoke slot mix, track-slot enable, EQ gain/frequency/bandwidth, and
  rollback before promoting per-slot bypass or EQ type changes.

Live evidence and false-positive probes:

- 2026-06-01, controller `channels-v37`: `mixer.setPluginMixLevel` did not
  stick on track 49 slot 0 (`Fruity Limiter`) or track 50 slot 0 (`Fruity
  parametric EQ 2`), although rollback restore remained safe. Because the API
  is officially documented, this remains `documented-unconfirmed`, not final
  `api-limited`, until `scripts/probe_documented_api_live.py` checks direct and
  selected-track variants.
- 2026-06-01, controller `channels-v37`: the false-positive probe verified
  `mixer.setPluginMixLevel` on Master track 0, slot 8 (`Fruity parametric EQ
  2`) in both direct and selected-track variants, with rollback verified. Slot
  mix is therefore target/plugin/state dependent, not globally `api-limited`.
- 2026-06-01, controller `channels-v37`: per-slot mute/enable returned API
  unavailable on the same targets. This stays probe-gated because the exposed
  `plugins.getPluginMuteState` / `setPluginMuteState` path is live-probed but
  not part of the documented mixer slot API surface.
- 2026-06-01, controller `channels-v37`: native EQ setter names were present,
  but gain writes did not stick on tracks 0, 1, 49, or 50 while rollback/restore
  remained safe. Keep Native EQ writes `documented-unconfirmed` until a narrower
  target/state probe proves a working path.
- 2026-06-01, controller `channels-v37`: targeted Native EQ high-pass attempt
  on mixer track 8 `Drums` partially stuck: band 0 frequency moved to the
  normalized 120 Hz value (`0.2594`), but type stayed `0` instead of the
  attempted high-pass value `3`. Rollback restored the original band state.
  Native EQ type writes need a dedicated REC event/value mapping probe.
- 2026-06-01, controller `channels-v37`: generic plugin parameter writes did
  not stick for any of Fruity Limiter's 18 exposed parameters on track 49 slot
  0; keep Limiter sidechain configuration manual until a stable parameter path
  is proven. Do not generalize this result to all plugin parameters; EQ2 passed
  below.
- 2026-06-01, controller `channels-v37`: Fruity Parametric EQ 2 plugin
  parameter write/readback/rollback passed on track 50 slot 0, Band 4 level.

### Step Parameter Pack

Status: `documented`, `probe-needed` for value ranges and restore behavior per
parameter.

Useful API:

- `channels.getStepParam`
- `channels.getCurrentStepParam`
- `channels.setStepParameterByIndex`
- Step parameter constants such as `pVelocity`, `pPan`, `pShift`, and
  `pRepeat`.

MVP:

- Read step velocity, pan, pitch/shift, release, and modulation where available.
- Set one step parameter at a time with readback. ✅ shipped
- Apply full-pattern humanization as one named rollback unit after individual
  parameter writes are live-smoked.

Safety requirement:

- Snapshot the affected channel's grid and every changed step parameter.
- Start with read-only inspection for parameters whose ranges vary by FL build.
- Do not ship randomized bulk writes until deterministic readback and rollback
  are verified.

### Project Doctor and Organizer

Status: orchestration over API-backed primitives.

MVP:

- Project health report with read-only findings. ✅ shipped
- Export readiness report with blocker/advisory split. ✅ shipped
- Dry-run fix plan that references existing rollback-safe tools. ✅ shipped
- Fix execution remains one approved write at a time.
- Grouped rollback for organizer actions.

Safety requirement:

- No direct writes. The doctor must call only safe lower-level operations.
- Multi-step organizer changes must be one named rollback unit by default.

### Piano Roll Return Channel and Comfort Transforms

Status: `documented` for local Piano Roll note/marker mutation,
`api-limited` for returning note data to the MCP server.

Useful API:

- `flp.score` note access and mutation inside a generated Piano Roll script.
- Note properties such as time, length, number, velocity, pan, release, color,
  slide, porta, selected, and muted where exposed by FL's Piano Roll API.
- Marker creation and mutation where supported by the active FL build.

Allowed next steps:

- Build a return-channel probe before promoting `fl_piano_get_notes`. ✅ shipped
- Add undo-backed transforms for duplicate, humanize, velocity ramp, gate,
  legato, overlap trim, strum, arpeggiate, mute/unmute, note color, slide,
  porta, and snap-to-scale.
- Add marker helpers only as generated, reviewable script payloads.

Current shipped slice:

- `duplicate` and `velocity_ramp` transforms are shipped as undo-backed writes.
- Initial marker helpers are shipped as generated-script writes:
  add marker, add time-signature marker, clear markers.
- Piano Roll writes can optionally retarget a channel/pattern through the
  controller before the generated script is triggered. The controller uses
  `ui.openEventEditor` with `channels.getRecEventId(...)` when available and
  falls back to `ui.showWindow`.
- Marker and note readback remain API-limited; rollback uses FL undo.

Safety requirement:

- Treat every generated script transform as a write tool.
- Use the existing Piano Roll undo-backed safety path.
- Return explicit readback limitations until the return-channel probe is
  solved.
- Avoid destructive delete-selected/delete-region until selected note data can
  be captured and restored.

### Edison / Audio Editor Script Tool

Status: `documented`, `probe-needed` for MCP return paths and practical rollback.

Useful API:

- Audio Editor scripts can operate on Edison and Slicex audio through generated
  scripts.
- Documented operations include sample/selection edits such as normalize,
  amplification, silence, reverse, trim, centering, and region operations.

Allowed next steps:

- Generate and install manual audio editor script templates.
- Build read-only probes for sample length, selection, sample rate, channels,
  region count, and region names if a reliable return path exists.
- Prefer offline audio artifact generation: analyzed WAV copies, markerized
  WAV files, region JSON, CUE-style metadata, and reviewable reports.

Safety requirement:

- Do not directly mutate the active Edison/Slicex sample without an audio
  snapshot and restore path.
- Treat generated audio editor scripts as manual/probe workflows until restore
  data is complete.

### Slicex

Status: `documented`, `probe-needed`.

Useful API:

- Slicex can consume slices and region metadata from audio material.
- Official docs describe both Audio Editor script usage and Slicex editor
  scripting surfaces, so FL-version behavior must be probed before committing
  to a single implementation path.

Allowed next steps:

- Build a Slicex prep pack outside FL: transient detection, zero-crossing
  alignment, markerized WAV export, and region metadata export.
- Generate manual Slicex script templates for region cleanup and reporting
  after the active scripting path is verified.
- Keep Slicex-to-Piano-Roll workflows manual or artifact-based until readback
  and rollback are proven.

Safety requirement:

- Do not auto-load Slicex, load samples, dump score, send clips to the
  playlist, or delete regions through UI automation.
- Direct region/sample edits need full restore data before becoming tools.

## Probe-Needed or Limited Areas

| Area | Current result | Allowed next step |
|---|---|---|
| Audio clip Normalize | Manual documents the UI setting; no direct MIDI scripting setter confirmed. | Probe REC/event paths only. |
| Stretch Pro mode | Sampler UI documents mode; MIDI scripting exposes stretch time, not clearly the mode. | Research/probe, not MVP. |
| Source sample path | No direct channel file-path getter confirmed. | User-supplied paths or later probe. |
| Piano Roll note readback to MCP | Piano Roll scripts can read notes locally, but the bridge has no return channel. | Generated transforms only; no `get_notes` tool yet. |
| Playlist clip overlap detection | No general clip enumeration API confirmed. | Keep track-level only. |
| Plugin loading | API controls loaded plugins; loading instances remains unsupported. | Suggest/load-manually/configure-loaded model. |
| Plugin preset next/previous | FL exposes preset navigation, but no verified MCP restore primitive. | Read-only/manual guidance only. |
| Edison/Slicex destructive live edits | Audio editor scripts can mutate samples, but no MCP-level audio snapshot/restore path exists. | Manual script generation, probes, or offline artifacts only. |
| Slicex scripting path | Official docs expose Slicex scripting surfaces, but practical Python vs legacy editor behavior must be verified per FL build. | Build a probe before user-facing tools. |
| Full FLP snapshot/restore | MCP can snapshot affected state, not the full project file. | MCP-local snapshots only. |

## Contract-Broken Capabilities

These capabilities must not be exposed as user-facing write tools until a
future design proves the full safety contract:

- Plugin loading or plugin insertion.
- Playlist clip editing, placement, movement, or deletion.
- Pattern or clip deletion.
- Project open, project new, project render, or similar file/session commands.
- Raw UI automation or raw escape-hatch calls.
- Destructive Edison or Slicex live edits without an audio snapshot.
- Preset next/previous as a write action without verified readback and
  rollback.

## Feature Gate Template

Before coding a new tool, fill this out in the PR description or design note:

```text
User value:
API evidence:
Safety class:
Snapshot scope:
Restore operation:
Readback:
Rollback unit:
Dry-run behavior:
Tests:
Live FL build verified:
```

If any of `Snapshot scope`, `Restore operation`, or `Readback` is unclear, the
tool is not ready to write FL state.
