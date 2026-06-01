# Roadmap

> **Transport note (v0.2):** the FL <-> server channel is MIDI SysEx, not a
> file queue. See [`docs/architecture.md`](docs/architecture.md) and
> [`docs/CHANGELOG.md`](docs/CHANGELOG.md). The tool surface is unchanged;
> phase work continues on top of the new transport.

## Non-negotiable safety contract

This project follows the contribution rule strictly: **no tool may modify FL
Studio state unless the change is reversible through the MCP safety layer**.
Read-only actions are the only exception.

## Roadmap maintenance rule

`ROADMAP.md` is the active execution tracker for this branch. It must be kept
up to date in the same PR or commit series whenever:

1. A roadmap slice is completed or materially re-scoped.
2. A live FL verification checkpoint passes or fails.
3. Priority order changes due to API limits, safety constraints, or user
   direction.

If implementation and roadmap diverge, roadmap alignment is a blocking follow-up
task.

## Current verification checkpoints

- 2026-06-01: Piano Roll retargeting infrastructure slice passed offline.
  - Verified path: `compileall` for `src/fl_studio_mcp`, controller script, and focused scripts; `scripts/test_pianoroll.py`; `scripts/test_compose.py`; `scripts/audit_tool_safety.py --fail-on-gaps`.
  - Result: existing undo-backed Piano Roll write tools can optionally pass a channel/pattern target through the bridge to the controller, which uses `ui.openEventEditor` when available and falls back to `ui.showWindow`.
  - Live verification passed on FL Studio Producer Edition v25.2.5 (build 5055), controller build marker `channels-v37`: targeted append write to channel 1 / pattern 4 returned `retargeted=True` via `ui.openEventEditor`, then `fl_rollback_last_change` restored through FL undo.
- 2026-06-01: Priority 1/2 live smoke suite attempted, blocked by stale FL controller build.
  - Verified path: daemon up, bridge ping ok (`build=channels-v35`), then
    `scripts/test_priority12_live.py`.
  - Result: blocked at command preflight (`Unknown command: pattern_find_empty`)
    because FL still runs an older script build that does not include the new
    controller handlers. Required next step: reload FL MIDI scripts and rerun
    the live smoke suite.
- 2026-06-01: Fixture hard-standardize + live capability sweep passed on FL Studio Producer Edition v25.2.5 (build 5055), controller build marker `channels-v36`.
  - Verified path: `scripts/fixture_hard_standardize_live.py` (names/colors/markers) then `scripts/run_live_capability_sweep.py`.
  - Result: core rollback-safe writes verified (patterns color, playlist track props, mixer routing/selection, effects slot mix + enabled, native EQ band edit, step sequencer grid bit, plugin param write) with immediate rollback confirmation.
  - Known limits on this build: `pattern_set_length` is API-unavailable (skipped); `mixer_set_stereo_sep` call executes but does not stick (treated as API-limited in live sweep).
- 2026-06-01: Priority 1 + Priority 2 implementation slice (offline) passed.
  - Verified path: `compileall` for `src/` + controller script, safety audit
    gate (`scripts/audit_tool_safety.py --fail-on-gaps`), focused offline tests:
    `scripts/test_effects_pattern_extensions.py`,
    `scripts/test_step_sequencer.py`, `scripts/test_pattern_playlist.py`,
    `scripts/test_pianoroll.py`.
  - Result: new rollback-safe Pattern Completion, Effect Slot + Native EQ
    tools, Project Doctor/Export Readiness reports, and initial Piano Roll
    comfort transforms (`duplicate`, `velocity_ramp`) are integrated and
    passing offline checks.
- 2026-05-31: Scale & Mode Composition Pack Phase 6 live smoke passed on FL Studio
  Producer Edition v25.2.5 (build 5055), controller build marker
  `channels-v35`.
  - Verified path: heartbeat -> ping -> scale catalog read -> scale notes query -> melody creation -> channel focus -> note writing & hotkey triggering via piano-roll bridge.
  - Result: all checks passed, scale listing and mapping works, notes correctly generated and written to FL Studio.
- 2026-05-31: Plugin Params Pack Phase 5 live smoke passed on FL Studio
  Producer Edition v25.2.5 (build 5055), controller build marker
  `channels-v35`.
  - Verified path: heartbeat -> ping -> plugin list -> param list & single param read -> preset name read -> rollback-safe plugin param edit write/readback/rollback.
  - Result: parameter read/write rollback passed. Preset next/prev remains read-only/manual because FL exposes navigation but no verified MCP restore primitive.
- 2026-05-31: Piano Roll Pack Phase 4 offline tests passed.
  - Verified path: note name parsing -> chord interval generation -> Pyscript rendering -> rollback undo action generation.
  - Result: 31 tests passed.
- 2026-05-31: Patterns & Playlist Pack Phase 3 live smoke passed on FL Studio
  Producer Edition v25.2.5 (build 5055), controller build marker
  `channels-v34`.
  - Verified path: heartbeat -> ping -> pattern list & length read -> playlist tracks read ->
    rollback-safe pattern rename write/readback/rollback ->
    rollback-safe playlist track mute/rename/color/selection write/readback/rollback.
  - Result: all checks passed, rollback restoration confirmed for patterns and playlist tracks.
- 2026-05-31: Mixer Pack Phase 2 live smoke passed on FL Studio
  Producer Edition v25.2.5 (build 5055), controller build marker
  `channels-v28`.
  - Verified path: heartbeat -> ping -> mixer track details read (with `dock_side` and `stereo_sep`) ->
    rollback-safe select track write/readback/rollback -> rollback-safe send route
    write/readback/rollback -> rollback-safe stereo separation write/readback/rollback ->
    peak level measurement verification.
  - Result: all checks passed, rollback restoration confirmed for selection, routing, and stereo separation.
- 2026-05-31: Step Sequencer Pack Phase 1 live smoke passed on FL Studio
  Producer Edition v25.2.5 (build 5055), controller build marker
  `channels-v26`.
  - Verified path: heartbeat -> ping -> grid read -> write-safe step grid bit
    write/readback/rollback -> rollback verification.
  - Result: grid bit mutation and rollback restoration successfully verified.
- 2026-05-31: Channel Organizer Pack v1 live smoke passed on FL Studio
  Producer Edition v25.2.5 (build 5055), controller build marker
  `channels-v16`.
  - Verified path: heartbeat -> ping -> channel detail read (`type`, `pitch`) ->
    rollback-safe rename write/readback/rollback -> rollback-safe mixer-target
    write/readback/rollback.
  - Result: all checks passed, rollback restoration confirmed for both write
    operations.

For every write-capable tool, the required shape is:

1. Take a scoped snapshot before the write.
2. Execute the smallest practical change.
3. Read back the affected state.
4. Persist a change-log entry with enough restore data to undo it.
5. Return a human-readable before/after result.
6. Support rollback through the MCP rollback path.

This applies to mixer, channel, pattern, playlist, piano-roll, routing, plugin,
effect-slot, project-tempo, time-signature, UI-assisted, and bulk operations.
Multi-step tools must apply as one named rollback unit unless explicitly split
into smaller user-approved changes.

Tools that cannot provide rollback are limited to read-only diagnosis, dry-run
planning, or clearly labelled manual instructions. They must not silently make
irreversible changes in FL Studio.

Transport-only runtime controls such as play, stop, and preview note triggering
do not change the saved project structure, but any persisted project mutation
such as tempo, pattern edits, channel routing, note writes, or mixer/plugin
changes must follow this contract.

## Contract-broken features

The following capabilities are useful in FL Studio, but they violate this
project's safety contract unless a future implementation proves scoped
snapshot, write, readback, changelog, and rollback. They must not ship as
user-facing write tools in their current form:

- Plugin loading or plugin insertion. Keep the current model: suggest the
  plugin, ask the user to load it manually, then configure already-loaded
  plugin parameters through rollback-backed tools.
- Playlist clip editing, placement, movement, or deletion. Playlist track
  organization is in scope; clip-level mutation is not in scope until the API
  exposes reliable enumeration, readback, and restore data.
- Pattern or clip deletion. Destructive removal is not acceptable without a
  complete restore story.
- Project open, project new, project render, or similar file/workflow commands.
  These are high-impact session operations and remain manual unless a robust
  project backup and recovery design exists.
- Raw UI automation or raw escape-hatch calls. They bypass reviewable safety
  semantics and make commits impossible to audit.
- Destructive Edison or Slicex live edits without an audio snapshot. Audio
  editor scripts may be generated as manual/probe workflows, but direct sample
  mutation needs full restore data before it can become a write tool.
- Preset next/previous as a write action without rollback. FL Studio exposes
  preset navigation in some places, but no reliable MCP restore primitive is
  currently verified. These commands must stay read-only/manual guidance unless
  preset state can be read back and restored.

## Phase A — Safety baseline before expansion

Before adding the API-backed production suite:

- [x] Add the PR-facing capability/safety audit document and static tool audit
      script: [`docs/API_CAPABILITY_AUDIT.md`](docs/API_CAPABILITY_AUDIT.md)
      and `scripts/audit_tool_safety.py`.
- [x] Inventory every MCP tool and mark it as read-only, transient runtime
      control, write with rollback, or write gap. Current gate:
      `scripts/audit_tool_safety.py --fail-on-gaps`.
- [x] Move existing direct project writes behind `safety.safe_write` or
      `safety.safe_write_group`. Initial gaps were tempo set, arrangement
      pattern/marker writes, Piano Roll generated-script writes, and compose
      tools that call the Piano Roll bridge. Piano Roll writes are rollbackable
      through FL Studio's undo stack because the generated scripts use
      `flp.score.undoSection()` when available.
- [x] Expose the MCP changelog safely: recent history, JSON export, stable
      change IDs, and LIFO-only rollback by change ID.
- [ ] Add snapshot scopes for new API-backed domains:
      channel name, channel mixer target, step grid/step params, pattern
      name/color/length/current selection, playlist track name/color/mute/solo,
      effect slot mix/bypass, project time signature, and native mixer EQ.
- [ ] Add grouped/named rollback units for project organizer, routing doctor,
      step-pattern writes, and bulk operations.
- [x] Treat Piano Roll generated-script transforms as write tools: all exposed
      transforms route through `safety.safe_piano_roll_write` and FL undo
      rollback. Readback remains explicitly API-limited.
- [ ] Document each tool's safety class in its docstring and MCP annotations.
- [x] Add tests for planned restore payloads where FL-live tests are not
      practical.

## Sister Project Consolidation — geezoria/FLStudioMCP

Reference: <https://github.com/geezoria/FLStudioMCP>. The sister project is a
useful feature-discovery source, but not a design to copy wholesale. It exposes
a very broad 160+ tool surface, including TCP transport, step sequencer writes,
playlist/arrangement tools, automation recording, piano-roll transforms,
generators, voice-to-MIDI, and audio analysis. Our adoption rule is stricter:
each persistent FL mutation must fit the snapshot -> write -> readback ->
rollback contract, or it stays read-only/dry-run/manual.

### Adopt as high-priority product capabilities

These overlap strongly with real user workflows and are backed by FL scripting
APIs we have already documented or probed.

1. **Step Sequencer Pack**
   - Add grid read/write, full step-pattern write, clear, shift, and velocity
     humanization.
   - Snapshot changed grid bits and step parameters as one rollback unit.
   - This is the strongest missing composition workflow because it avoids the
     Piano Roll bridge entirely.

2. **Channel Organizer Pack**
   - Add channel rename, channel type detail, pitch, target mixer assignment,
     and "assign to free mixer track".
   - Promote the user's audio-default request only where API-backed:
     channel volume 50%, name/color/route are in scope; Normalize and Stretch
     Pro stay probe-dependent.
   - v1 shipped: details read, unassigned-channel detection, rename, explicit
     mixer-target assignment, and assign-to-free-mixer-track. Pitch write and
     Normalize/Stretch Pro remain out of scope.

3. **Pattern Management Pack**
   - Add first-class current/list/select/rename/color/length/clone/move/find
     empty tools.
   - Do not add delete/merge/split until there is a proven restore story.

4. **Playlist Track Organizer**
   - Add playlist track list/name/color/mute/solo/select.
   - Add `fl://playlist` as a resource capped like existing mixer/channel
     resources.
   - Do not claim general clip enumeration, overlap detection, clip movement,
     or clip deletion until a reliable API path exists.

5. **Effect Slot and Native EQ Pack**
   - Add effect slot read, slot mix, track-slot enable/bypass, and native mixer
     EQ read/write.
   - Support setting Low/High bands to Low Cut (High Pass) and High Cut (Low Pass)
     modes via `general.processRECEvent` (using `mixer.REC_Mixer_EQ_Type`,
     `_Freq`, and `_Q` event IDs) to allow plugin-free, CPU-friendly channel high-passing.
   - Snapshot slot mix/enabled state and every changed EQ band parameter.
   - Treat per-slot mute as live-test-required before user-facing exposure.

6. **Safety / Change History Pack**
   - Expose recent MCP changelog entries, export the changelog, and rollback by
     recent index or change id.
   - Add named grouped rollback units for organizer, routing doctor, and bulk
     cleanup operations.
   - Optionally anchor large grouped writes with `general.saveUndo` where FL
     exposes it, without replacing MCP-level restore payloads.

7. **Project Doctor**
   - Build as orchestration over safe primitives, not as a second write layer.
   - Combine Mix Doctor, Routing Doctor, organizer findings, plugin/effect-slot
     state, muted/soloed tracks, duplicate names, too-hot levels, and export
     readiness into one read-only report.
   - Apply one approved fix at a time, each with its own rollback unit.

### Adopt later, with architecture changes

- **Piano Roll comfort transforms**: clear, transpose, duplicate, humanize,
  velocity ramp, delete selected/region. These are real inside Piano Roll
  scripts, but MCP readback remains the hard part. Keep them undo-backed and
  explicit about limited readback unless a reliable return channel is added.
- **High-level generators**: chord progressions, drum grooves, basslines,
  arpeggios, melodies, and DnB grooves are valuable, but should compile to our
  existing `fl_export_midi`, step sequencer, or safe Piano Roll writer instead
  of becoming many thin write tools.
- **Voice-to-MIDI**: useful, but should first ship as read-only transcription
  to note JSON/MIDI. Writing into FL must route through the safe Piano Roll
  writer and requires clear optional dependency handling.
- **Audio melody-to-Piano-Roll and sample flip workflows**: keep analysis
  read-only first; generated MIDI/notes are reviewable artifacts before any FL
  write.
- **Automation via REC events**: promising but risky. Build probes first for
  tempo, channel volume/pan, mixer volume, and plugin params; only expose tools
  where the created automation can be read back or safely undone.
- **TCP bridge / push events**: attractive for throughput and event streaming,
  but not a near-term replacement for the now-working MIDI SysEx bridge. Treat
  it as an experimental transport branch after the product tool surface is
  safer and better tested.

### Do not copy into the roadmap as user-facing tools

- Raw escape hatches such as `fl_call_raw`; they bypass reviewable safety.
- Project open/new/render as automated tools; they are UI/file-workflow heavy
  and high-risk without a stronger backup story.
- Pattern delete, playlist clip delete/place, marker delete, full clip
  enumeration, and arrangement switching unless probes prove current FL builds
  expose them reliably.
- Plugin loading/insertion; keep the current "suggest/load manually/configure
  loaded plugin" model.
- Broad UI window tools. Keep focus/window controls as infrastructure and
  diagnostics, not core product surface.
- Full FLP snapshot/restore claims. MCP snapshots restore the affected state,
  not an entire project file.

### Revised build order after consolidation

1. **Safety primitives first**
   - Snapshot scopes for channel name/type/pitch/target, step grid/params,
     pattern name/color/length/current selection, playlist track state, effect
     slots, native EQ, time signature, and undo metadata.
   - Changelog browsing and rollback by id/index.

2. **API-backed quick wins**
   - Step Sequencer Pack.
   - Channel Organizer Pack.
   - Pattern Management Pack.
   - Playlist Track Organizer.
   - Effect Slot and Native EQ Pack.

3. **Product-level workflows**
   - Project Organizer MVP.
   - Routing Doctor 2.0.
   - Project Doctor / Health Report.
   - Export readiness report.

4. **Creative intelligence**
   - Generator pack that emits reviewable notes/MIDI/step patterns.
   - Voice/audio transcription as optional read-only analysis first.
   - Safe write path only after generated material is inspectable and
     rollback-backed.

5. **Experimental infrastructure**
   - Push events and optional TCP transport.
   - Piano Roll readback/return-channel research.
   - REC automation write/readback probes.

## Official API Expansion Backlog

These items come from the official MIDI Controller, Piano Roll, Edison/Audio
Editor, and Slicex scripting surfaces. They are prioritized for product value
and compatibility with the safety contract.

### Priority 1 — rollback-backed production primitives

1. **Effect Slot + Native EQ Pack**
   - Add user-facing tools for mixer effect slot readback, slot mix, slot
     enabled/bypass state where verified, and native mixer EQ band read/write.
   - Snapshot every changed slot and EQ band parameter before writes.
   - Read back slot/EQ state after every mutation and log a restore payload.
   - Treat per-slot bypass/mute and EQ type changes as live-smoke-required
     before exposing them broadly.

2. **Step Parameter Pack**
   - Extend the Step Sequencer Pack beyond grid bits to step velocity, pan,
     pitch, release, and modulation parameters where the MIDI Controller API
     exposes stable read/write calls.
   - Snapshot the affected channel's step grid and changed step parameters as
     one named rollback unit for full-pattern operations.
   - Add read-only inspection first for any step parameter whose value range or
     restore behavior differs across FL Studio versions.

3. **Pattern Organizer Completion**
   - Add rollback-backed tools for pattern color, pattern length, current
     pattern selection snapshot/restore, find-empty-pattern, and clone/move if
     readback proves stable.
   - Keep pattern delete, merge, split, and destructive cleanup out of scope
     until restore data is complete.
   - Use one grouped rollback unit for multi-pattern organizer actions.

4. **Project Doctor / Export Readiness Report**
   - Build a read-only aggregate report over existing safe primitives:
     routing, mixer peaks, plugin parameter visibility, muted/solo states,
     duplicate or empty names, unassigned channels, suspicious pattern lengths,
     and playlist organization.
   - Produce fix plans as dry-run recommendations first.
   - Apply fixes only one approved rollback-backed operation at a time.

### Priority 2 — Piano Roll productivity after return-channel research

1. **Piano Roll Return-Channel Probe**
   - Research whether generated Piano Roll scripts can return structured note
     data to the MCP server through a reliable file, clipboard, bridge, or
     controller-mediated path.
   - Keep `fl_piano_get_notes` explicitly API-limited until this probe is
     proven and tested.
   - Document failure modes and FL version assumptions before enabling any
     readback-dependent tool.

2. **Piano Roll Comfort Transforms**
   - Add selected/all scope transforms for duplicate, humanize timing,
     humanize velocity, velocity ramp, gate/length, legato, overlap trim,
     strum, arpeggiate, mute/unmute, note color, slide, porta, and
     snap-to-scale.
   - Every transform must use the Piano Roll undo-backed safety path and return
     an explicit readback limitation until the return-channel probe is solved.
   - Avoid destructive delete-selected/delete-region tools unless the selected
     note set can be captured and restored.

3. **Piano Roll Marker Pack**
   - Add scale, section, time-signature, and cue marker helpers where the Piano
     Roll scripting API can write them predictably.
   - Keep marker edits undo-backed and grouped with related note transforms
     when they are part of one musical operation.
   - Prefer generated reviewable script payloads over broad opaque commands.

Tracking the full scope — eight phases shipping the MCP server, the scale/mode
composition tools, the SKILL.md, evals, and the Claude Code plugin marketplace
bundle.

Each phase is shippable on its own. Each ends with `python scripts/test_bridge.py`
still passing.

## Phase 0 — Foundation (shipping)

Goal: prove the SysEx bridge works end-to-end and ship the absolute
minimum tool surface.

- [x] MIDI SysEx protocol (commands, responses, heartbeat) over two loopMIDI ports.
- [x] FL controller script with `OnSysEx`/`OnMidiMsg` dispatch and an `OnIdle` heartbeat.
- [x] FastMCP server skeleton with stdio transport.
- [x] Transport tools: ping, tempo get/set, play, stop, toggle, record,
      play-state, song-position get/set. **10 tools total.**
- [x] `scripts/test_bridge.py` standalone harness.
- [x] Install script for Windows. (macOS / Linux: not shipped — contributions welcome.)

## Phase 1 — Channel rack (~12 tools)

The channel rack is where most users place samples and instruments.

- [x] `fl_channel_list` — Names, types, colors, current pattern.
- [x] `fl_channel_get` — Volume, pan, mute, solo, target mixer track.
- [x] `fl_channel_set_volume`, `_pan`, `_mute`, `_solo`.
- [x] `fl_channel_select` — Make a channel active.
- [x] `fl_channel_get_grid` — Read the step-sequencer grid for the current pattern.
- [x] `fl_channel_set_grid_bit` — Write a single step. (This is how we draw drum
  patterns without needing the Piano Roll pyscript.)
- [x] `fl_channel_clear_grid` — Wipe steps for a channel in the current pattern.
- [x] `fl_channel_get_color`, `_set_color` — Visual organization.

Risk: FL's channel API uses `channels.channelNumber()` and `channels.selectedChannel()`
for the active channel. Some functions need the explicit index; some use the
selection. The script normalizes to explicit indices.

## Phase 2 — Mixer (~10 tools)

- [x] `fl_mixer_list_tracks` — Up to 125 tracks plus Master at index 0.
- [x] `fl_mixer_get_track` — Name, volume, pan, mute, solo, dock side, color, stereo separation.
- [x] `fl_mixer_set_volume`, `_set_pan`, `_set_mute`, `_set_solo`, `_set_stereo_separation`.
- [x] `fl_mixer_select_track` — Drive UI focus.
- [x] `fl_mixer_get_route` — Where this track's audio is sent.
- [x] `fl_mixer_set_route` — Add/remove a route to another track.
- [x] `fl_mixer_get_levels` — Peak meter sample (read via `OnUpdateMeters`).

Risk: `setTrackVolume` takes a normalized float 0.0–1.0 where 0.8 is unity
gain, not 1.0. The tools accept dB and convert.

## Phase 3 — Patterns + playlist (~6 tools) [x] Completed

- [x] `fl_pattern_list` — Names, lengths, colors.
- [x] `fl_pattern_select`, `_rename`.
- [x] `fl_pattern_get_length` (in steps and beats).
- [x] `fl_playlist_list_tracks` — Playlist track list.
- [x] `fl_playlist_get_track` — Playlist track details.
- [x] `fl_playlist_set_mute`, `_set_solo`, `_set_name`, `_set_color`, `_select_track` — Playlist track mutations with rollback.
- [x] `fl_arrange_add_marker` (previously implemented in arrangement slice) — Section markers.

API limits worth surfacing in tool docs:
- New patterns cannot be created from scratch; clone an existing pattern
  instead (`fl_arrange_clone_pattern`).

## Phase 4 — Piano Roll pyscript (~6 tools) [x] Completed

This is the most invasive phase — adds the second script type.

- [x] `fl_piano_write_notes` — Note batch into the active pattern's Piano Roll.
- [x] `fl_piano_write_chord` — Helper that builds a chord by name (`Cmaj7`, `Bbm9`) and writes it.
- [x] `fl_piano_clear` — Wipe the active pattern.
- [x] `fl_piano_quantize` — Snap selected notes.
- [x] `fl_piano_transpose` — Shift in semitones.
- [x] `fl_piano_get_notes` — Declared as `api-limited` with clear error response.

Mechanics:
1. FL's pyscript sandbox can't receive data the server hands it, so the daemon
   generates the `MCP_Apply` `.pyscript` with the notes baked in and writes it
   into FL's Piano roll scripts folder.
2. FL exposes no API to run a pyscript, so the note bridge is armed once per
   session: run `MCP_Apply` from the Piano roll's Scripting menu.
3. To apply a batch, the daemon force-focuses FL and re-triggers the armed
   script (FL's "Run last script again"); FL re-reads the `.pyscript` and writes
   the notes. No file queue, no JSON polling.

The Piano roll must be FL's active panel for the re-trigger to land, so the
bridge force-focuses FL first.

## Phase 5 — Plugin params (~5 tools) [x] Completed

- [x] `fl_plugin_list_params` — Parameter index, name, current value, value range.
- [x] `fl_plugin_get_param`, `_set_param`.
- [x] `fl_plugin_get_preset_name`.
- [x] `fl_plugin_next_preset`, `fl_plugin_prev_preset` return read-only/manual guidance instead of mutating FL state, because preset navigation has no verified rollback primitive.

This is intentionally scoped tight. Per-VST parameter naming is a mess across
plugins; we expose the raw FL view and let the LLM map names.

## Phase 6 — Scale & mode composition (~8 tools) [x] Completed

Genre- and producer-agnostic composition in any scale or mode: Western modes,
pentatonic, the Carnatic melakarta and janya ragas, Arabic maqam, and beyond.
Claude supplies the correct notes/intervals for the requested scale and writes
them through the note bridge. Indian ragas are one supported family among many,
not the headline.

- [x] Scale catalogue — scales and modes by family, each with its
  ascending/descending intervals (e.g. the 72 melakarta ragas plus common
  janyas — Bhairavi, Mohanam, Kalyani — alongside Western modes, pentatonic,
  and maqam).
- [x] Scale → note mapping at a chosen base note.
- [x] Melody and chords in a chosen scale, shaped by a mood/character (e.g.
  `devotional`, `cinematic`, `melancholic`, `energetic`), written via the note
  bridge (`fl_write_raga_melody`, `fl_write_raga_chords`).
- [x] Section markers for arrangement (`fl_arrange_add_marker`).

Micro-tonal and gamaka-heavy traditions (e.g. Carnatic) get the *scale
framework* — correct swaras/intervals — not gamaka or micro-tonal rendering;
that's a 12-tone MIDI limit, not a tool limit.

Scale/mode data lives in `src/fl_studio_mcp/presets/` as plain Python modules
so it ships inside the wheel.

## Phase 7 — Polish & ship

- [ ] `skills/flstudio-production/SKILL.md` orchestration layer with deep
      content in `references/`. Under 500 lines.
- [ ] `evals/evals.json` — 10 questions exercising the full tool surface.
- [ ] `.claude-plugin/marketplace.json` so this can live in
      `rosasynthesiz-skills` as an installable plugin.
- [ ] `AGENTS.md` describing the agentic workflow for future Claude sessions
      working on this codebase.
- [ ] Demo video and screenshots in `docs/`.
- [ ] GitHub Actions for linting and the standalone bridge tests (mock FL).
- [ ] Pin a known-working FL Studio version range in README.

## Out of scope (intentionally)

- Loading new VST instances — FL API does not allow this.
- Creating new patterns ex nihilo — same limitation.
- Audio recording control beyond the record-arm toggle.
- Multiple FL Studio instances on one machine — not currently wired.
