# Roadmap

> **Transport note (v0.2):** the FL <-> server channel is MIDI SysEx, not a
> file queue. See [`docs/architecture.md`](docs/architecture.md) and
> [`docs/CHANGELOG.md`](docs/CHANGELOG.md). The tool surface is unchanged;
> phase work continues on top of the new transport.

## Non-negotiable safety contract

This project follows the contribution rule strictly: **no tool may modify FL
Studio state unless the change is reversible through the MCP safety layer**.
Read-only actions are the only exception.

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
- [ ] Treat Piano Roll generated-script transforms as write tools: they need
      a reversible representation or must stay dry-run/manual until rollback is
      solved for that operation.
- [ ] Document each tool's safety class in its docstring and MCP annotations.
- [ ] Add tests for planned restore payloads where FL-live tests are not
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

- `fl_channel_list` — Names, types, colors, current pattern.
- `fl_channel_get` — Volume, pan, mute, solo, target mixer track.
- `fl_channel_set_volume`, `_pan`, `_mute`, `_solo`.
- `fl_channel_select` — Make a channel active.
- `fl_channel_get_grid` — Read the step-sequencer grid for the current pattern.
- `fl_channel_set_grid_bit` — Write a single step. (This is how we draw drum
  patterns without needing the Piano Roll pyscript.)
- `fl_channel_clear_grid` — Wipe steps for a channel in the current pattern.
- `fl_channel_get_color`, `_set_color` — Visual organization.

Risk: FL's channel API uses `channels.channelNumber()` and `channels.selectedChannel()`
for the active channel. Some functions need the explicit index; some use the
selection. The script normalizes to explicit indices.

## Phase 2 — Mixer (~10 tools)

- `fl_mixer_list_tracks` — Up to 125 tracks plus Master at index 0.
- `fl_mixer_get_track` — Name, volume, pan, mute, solo, dock side, color.
- `fl_mixer_set_volume`, `_set_pan`, `_set_mute`, `_set_solo`.
- `fl_mixer_select_track` — Drive UI focus.
- `fl_mixer_get_route` — Where this track's audio is sent.
- `fl_mixer_set_route` — Add/remove a route to another track.
- `fl_mixer_get_levels` — Peak meter sample (read via `OnUpdateMeters`).

Risk: `setTrackVolume` takes a normalized float 0.0–1.0 where 0.8 is unity
gain, not 1.0. The tools accept dB and convert.

## Phase 3 — Patterns + playlist (~6 tools)

- `fl_pattern_list` — Names, lengths, colors.
- `fl_pattern_select`, `_rename`.
- `fl_pattern_get_length` (in steps and beats).
- `fl_playlist_get_tracks` — Playlist track names and visibility.
- `fl_playlist_get_markers` — Time-line markers (used to insert section markers).

API limits worth surfacing in tool docs:
- New patterns cannot be created from scratch; clone an existing pattern
  instead (`fl_arrange_clone_pattern`).

## Phase 4 — Piano Roll pyscript (~6 tools)

This is the most invasive phase — adds the second script type.

- `fl_piano_write_notes` — Note batch into the active pattern's Piano Roll.
- `fl_piano_write_chord` — Helper that builds a chord by name (`Cmaj7`,
  `Bbm9`) and writes it.
- `fl_piano_clear` — Wipe the active pattern.
- `fl_piano_quantize` — Snap selected notes.
- `fl_piano_transpose` — Shift in semitones.
- `fl_piano_get_notes` — Read back what is in the active pattern.

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

## Phase 5 — Plugin params (~5 tools)

- `fl_plugin_list_params` — Parameter index, name, current value, value range.
- `fl_plugin_get_param`, `_set_param`.
- `fl_plugin_get_preset_name`, `_select_preset_index`.

This is intentionally scoped tight. Per-VST parameter naming is a mess across
plugins; we expose the raw FL view and let the LLM map names.

## Phase 6 — Scale & mode composition (~8 tools)

Genre- and producer-agnostic composition in any scale or mode: Western modes,
pentatonic, the Carnatic melakarta and janya ragas, Arabic maqam, and beyond.
Claude supplies the correct notes/intervals for the requested scale and writes
them through the note bridge. Indian ragas are one supported family among many,
not the headline.

- Scale catalogue — scales and modes by family, each with its
  ascending/descending intervals (e.g. the 72 melakarta ragas plus common
  janyas — Bhairavi, Mohanam, Kalyani — alongside Western modes, pentatonic,
  and maqam).
- Scale → note mapping at a chosen base note.
- Melody and chords in a chosen scale, shaped by a mood/character (e.g.
  `devotional`, `cinematic`, `melancholic`, `energetic`), written via the note
  bridge (`fl_write_raga_melody`, `fl_write_raga_chords`).
- Section markers for arrangement (intro, build, drop, …).

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
