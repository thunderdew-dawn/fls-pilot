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
| `live-probed` | Current FL build exposes and executes the API. | Implement with version/capability reporting. |
| `existing` | Current MCP already exposes it safely. | Reuse; do not duplicate. |
| `probe-needed` | Name exists or docs imply a path, but behavior is unverified. | Build a probe first, not a user tool. |
| `api-limited` | No stable API path is known. | Read-only plan or manual instruction only. |

Primary references:

- MIDI scripting API: <https://www.image-line.com/fl-studio-learning-content/fl-studio-online-manual/html/midi_scripting.htm>
- Piano Roll scripting API: <https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll_scripting_api.htm>
- Sampler Channel settings: <https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/chansettings_sampler.htm>

## Current Safety Baseline

Run the local audit before adding write tools:

```bash
.venv/bin/python scripts/audit_tool_safety.py
```

Use the current baseline as a ratchet while the existing gaps are being fixed:

```bash
.venv/bin/python scripts/audit_tool_safety.py --max-write-gaps 9
```

That command should pass today and fail if a new unsafe write tool is added.
Once a gap is resolved, lower the baseline. When all gaps are gone, switch CI to:

```bash
.venv/bin/python scripts/audit_tool_safety.py --fail-on-gaps
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

Initial expected gaps on this branch are older direct-write tools:

- Tempo writes in transport.
- Arrangement pattern/marker writes.
- Piano Roll generated-script writes and transforms.
- Composer tools that select a channel and call the Piano Roll bridge.

Those are not blockers for auditing; they are the first backlog before adding
new write-heavy domains.

The initial static baseline reports:

- 22 `write-safe` tools.
- 9 `write-gap` tools.
- 27 `read-only` tools.
- 5 `transient` runtime tools.
- 3 `server-state` tools.
- 1 `external-write` tool.

`--fail-on-gaps` is expected to fail until the 9 write gaps are resolved or
explicitly reclassified with a documented rollback story. `--max-write-gaps 9`
is the current no-regression gate.

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

Safety requirement:

- Add snapshot scopes for channel name, color, target mixer track, and volume.
- Keep Stretch Pro/Normalize out of the MVP until a real API path is proven.

### Pattern Management

Status: `documented`, `live-probed`.

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

### Effect Slot Control

Status: `documented`, `live-probed` for mix and track slot enable; per-slot
mute needs a live behavior test before user-facing exposure.

Useful API:

- `mixer.getPluginMixLevel`
- `mixer.setPluginMixLevel`
- `mixer.isTrackSlotsEnabled`
- `mixer.enableTrackSlots`
- `mixer.isTrackPluginValid`
- Live-probed: `getPluginMuteState`, `setPluginMuteState`.

MVP:

- List effect slots with plugin names and slot mix.
- Set slot mix.
- Bypass/enable all slots on a track.
- Per-slot bypass only after live readback is proven.

Safety requirement:

- Snapshot slot mix and bypass state.
- Do not promise full chain restore; plugin loading/removal is API-limited.

### Native Mixer EQ

Status: `documented`, `live-probed`.

Useful API:

- `mixer.getEqGain` / `setEqGain`
- `mixer.getEqFrequency` / `setEqFrequency`
- `mixer.getEqBandwidth` / `setEqBandwidth`
- `mixer.getEqBandCount`

MVP:

- Read native mixer EQ.
- Apply simple low/high shaping intents as fallback when no EQ plugin is loaded.

Safety requirement:

- Snapshot every changed band parameter before writing.

### Project Doctor and Organizer

Status: orchestration over API-backed primitives.

MVP:

- Project health report with read-only findings.
- Fix plan with one approved fix at a time.
- Grouped rollback for organizer actions.

Safety requirement:

- No direct writes. The doctor must call only safe lower-level operations.
- Multi-step organizer changes must be one named rollback unit by default.

## Probe-Needed or Limited Areas

| Area | Current result | Allowed next step |
|---|---|---|
| Audio clip Normalize | Manual documents the UI setting; no direct MIDI scripting setter confirmed. | Probe REC/event paths only. |
| Stretch Pro mode | Sampler UI documents mode; MIDI scripting exposes stretch time, not clearly the mode. | Research/probe, not MVP. |
| Source sample path | No direct channel file-path getter confirmed. | User-supplied paths or later probe. |
| Piano Roll note readback to MCP | Piano Roll scripts can read notes locally, but the bridge has no return channel. | Generated transforms only; no `get_notes` tool yet. |
| Playlist clip overlap detection | No general clip enumeration API confirmed. | Keep track-level only. |
| Plugin loading | API controls loaded plugins; loading instances remains unsupported. | Suggest/load-manually/configure-loaded model. |
| Full FLP snapshot/restore | MCP can snapshot affected state, not the full project file. | MCP-local snapshots only. |

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
