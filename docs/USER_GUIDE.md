# User Guide: Value, Prompts, and Tool Reference

This guide explains what flstudio-mcp is useful for, how a user talks to it
through an AI assistant, and what every exposed MCP tool does.

Most users should ask in plain language. The assistant leverages safety classes, explicit product boundaries, and the current 94-tool public catalog. It proposes a plan when needed, and applies approved changes through the rollback-first safety layer. Users can also name a specific `fl_*` tool directly when they want precise control.

## Why This App Exists

flstudio-mcp turns FL Studio into a controllable production workspace for any
MCP-compatible AI assistant. Its value is not just remote control; it combines
live FL Studio context, music-production judgement, and reversible edits.

- It lets users ask for production work in natural language: mix diagnosis,
  channel cleanup, routing, plugin tweaks, Piano Roll writing, arrangement
  markers, MIDI export, and audio analysis.
- It gives the assistant real project state instead of screenshots or guesses:
  transport, tempo, channels, mixer tracks, patterns, playlist tracks, routing,
  plugins, plugin parameters, and live meter data.
- It keeps project mutation conservative. Every persistent FL Studio write must
  snapshot the affected state, make the smallest practical change, read back the
  result, log restore data, and support rollback.
- It separates safe automation from FL Studio API limits. Unsupported actions,
  such as loading plugins, rendering audio, deleting patterns, editing playlist
  clips, or broad UI automation, remain manual guidance instead of unsafe tools.

## How Users Interact With The AI

The normal workflow is conversational:

1. The user asks for an outcome, for example "scan my mix and fix the worst
   headroom issue".
2. The assistant checks `fl_transport(action="ping")` and reads relevant resources such as
   `fl://status`, `fl://mixer`, `fl://channels`, or specific tools.
3. For risky or multi-step work, the assistant explains what it plans to do and
   which changes are reversible.
4. The assistant applies one approved change or one named rollback unit.
5. The assistant reports what changed, what was skipped, and how to roll it
   back.

Users do not need to know tool names, but direct tool names are available for
precision. These are both valid:

```text
Please rename mixer track 8 to Drums and color it blue.
```

```text
Use fl_mixer with action set_name on track 8, then fl_set_track_color on track 8.
```

## Safety Classes

| Safety class | Meaning |
|---|---|
| `read-only` | Reads FL Studio, files, or server context without mutating the project. |
| `write-safe` | Mutates FL Studio through the safety layer with snapshot, readback, changelog, and rollback. |
| `transient` | Controls runtime state such as playback or song position; it should not persist in the project. |
| `server-state` | Changes MCP server state, safety history, dry-run mode, or rollback state. |
| `external-write` | Writes outside FL Studio, such as a MIDI file or exported change log. |

## Module Examples

Each example is a user prompt. The assistant may call several tools behind the
scenes, and write tools should be described before execution when the change is
not trivial.

### Transport And Bridge

Prompt:

```text
Check that FL Studio is connected, tell me the tempo, then start playback.
```

Typical tools: `fl_transport(action="ping")`,
`fl_transport(action="get_tempo")`, `fl_transport(action="play")`,
`fl_transport(action="get_play_state")`.

### Project, Mixer, And Channel State

Prompt:

```text
Show me a concise overview of the project, then list tracks that are muted or
too hot.
```

Typical tools: `fl_get_project_state`, `fl_mixer`,
`fl_mixer_get_levels`.

### Channel Organizer And Step Sequencer

Prompt:

```text
Find channels that are not routed to mixer tracks, assign the kick to a free
track, and write a four-on-the-floor kick pattern.
```

Typical tools: `fl_detect_unassigned_channels`,
`fl_assign_channel_to_free_mixer_track`, `fl_channel`.

### Patterns, Playlist, And Arrangement

Prompt:

```text
Create a named intro pattern, clone my main groove for the drop, color the drop
pattern red, and add section markers at bars 1, 17, and 33.
```

Typical tools: `fl_arrange_new_pattern`, `fl_arrange_clone_pattern`,
`fl_pattern`, `fl_arrange_add_marker`.

### Piano Roll And Scale Composition

Prompt:

```text
Write an 8-bar melody in D Dorian to the selected channel, then quantize it to
1/16 notes.
```

Typical tools: `fl_scale_get`, `fl_piano_roll`, or the higher-level
`fl_write_raga_melody`.

### Plugins, Effects, And Mixing Intents

Prompt:

```text
Find the EQ on the lead vocal, reduce harshness around 3 kHz, then show the
before and after parameter values.
```

Typical tools: `fl_plugin`, `fl_apply_eq_intent`.

> **Note on UI Refresh:** When the assistant applies EQ or plugin changes via `fl_apply_eq_intent`, the parameters take effect immediately in the audio engine. However, if the plugin window is currently open in FL Studio, the GUI may not visually update until the user clicks on it or reopens the window.

### Mix Doctor

Prompt:

```text
Run Mix Doctor, explain the top three problems, and apply only the safest
headroom fix first.
```

Typical tools: `fl_diagnose_mix`, `fl_gain_stage`, `fl_apply_mix_fix`,
`fl_get_change_history`.

### Routing, Bulk Control, And Color

Prompt:

```text
Group all drum tracks into a Drums bus, mute the bass group for comparison,
then undo the mute when I say so.
```

Typical tools: `fl_detect_cleanup_candidates`, `fl_group_tracks`,
`fl_mute_tracks`, `fl_clear_mute_solo`.

### Project Doctor And Export Readiness

Prompt:

```text
Prepare this project for export: report duplicate names, unrouted channels,
muted tracks, suspicious levels, and give me a dry-run fix plan.
```

Typical tools: `fl_project_health_report`, `fl_export_readiness_report`,
`fl_project_dry_run_fix_plan`.

### Audio Analysis, Presets, Chains, And MIDI Export

Prompt:

```text
Analyze this reference file for tempo and key, suggest a preset from my local
library for a warm bass, then export an 8-bar MIDI sketch.
```

Typical tools: `fl_analyze_audio`, `fl_suggest_preset`,
`fl_setup_chain`, `fl_export_midi`.

## Useful Prompt Patterns

```text
Scan first, do not change anything yet.
```

```text
Show me exactly which tool you will use before you write to FL Studio.
```

```text
Make one reversible change, verify readback, then stop.
```

```text
Use dry-run mode and give me a fix plan only.
```

```text
Rollback the last MCP change.
```

```text
Export the change log so I can audit what was changed.
```

## MCP Resources

Resources are read-only context endpoints the assistant can pull without a
tool call. They are intentionally capped so automatic context reads stay small.

| Resource | What it gives the assistant |
|---|---|
| `fl://status` | Bridge health, heartbeat age, FL version, tempo, and playback state. |
| `fl://project` | Tempo, transport, and project-level counts. |
| `fl://transport` | Playback, recording, song position, and tempo snapshot. |
| `fl://channels` | Capped Channel Rack summary. |
| `fl://mixer` | Capped mixer-track summary. |
| `fl://patterns` | Capped pattern list. |

## Full Tool Reference

The current public MCP surface registers 86 tools: 40 `read-only`, 33
`write-safe`, 4 `server-state`, 2 `external-write`, and 7 Knowledgebase tools
registered outside the static annotation pattern.

### Arrangement Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_arrange_new_pattern` | `write-safe` | Creates a new named pattern and selects it. |
| `fl_arrange_select_channel` | `write-safe` | Selects the Channel Rack channel used as the note-bridge target. |
| `fl_arrange_clone_pattern` | `write-safe` | Clones a pattern, including notes where FL exposes that path. |
| `fl_arrange_add_marker` | `write-safe` | Adds a section marker at a bar. |

### Audio Analysis Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_analyze_audio` | `read-only` | Estimates tempo, key, and audio properties from a file. |
| `fl_extract_melody` | `read-only` | Extracts a monophonic melody from an audio file using pyin or CREPE when available. |

### Bulk Control Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_solo_tracks` | `write-safe` | Solos a resolved group of mixer tracks as one reversible operation. |
| `fl_mute_tracks` | `write-safe` | Mutes a resolved group of mixer tracks as one reversible operation. |
| `fl_clear_mute_solo` | `write-safe` | Clears mixer mute and solo states in one grouped rollback unit. |

### Chain Planning Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_list_chains` | `read-only` | Lists available genre or purpose chain recipes. |
| `fl_list_installed_plugins` | `read-only` | Reads installed FL plugin database entries from disk. |
| `fl_setup_chain` | `read-only` | Plans a chain from available plugins; it does not load plugins. |

### Channel And Step Sequencer Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_channel` | `write-safe` | Consolidated Channel Rack domain tool. Actions include list, get, get_selected, get_steps, classify, select, set_color, set_mute, set_mixer_target, set_name, set_pan, set_solo, set_steps, and set_volume. |
| `fl_detect_unassigned_channels` | `read-only` | Finds channels that likely need mixer-track assignment. |
| `fl_assign_channel_to_free_mixer_track` | `write-safe` | Finds a free mixer track and assigns a channel to it. |
| `fl_inspect_audio_clips` | `read-only` | Scans Audio Clips for routing, naming, and volume issues. |
| `fl_plan_audio_clip_safe_defaults` | `read-only` | Plans safe defaults (volume normalization, free track routing) for Audio Clips. |
| `fl_apply_audio_clip_safe_defaults` | `write-safe` | Applies safe volume limits and routing to Audio Clips with manual checklists for Stretch/Normalize. |

### Color Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_set_track_color` | `write-safe` | Colors one or more mixer tracks by color name or hex value. |
| `fl_set_channel_color` | `write-safe` | Colors one or more Channel Rack channels by color name or hex value. |

### Scale Composition Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_write_raga_melody` | `write-safe` | Writes a generated scale or raga melody through the Piano Roll bridge. |
| `fl_write_raga_chords` | `write-safe` | Writes scale-aware chords through the Piano Roll bridge. |
| `fl_scale_list` | `read-only` | Lists supported scales, modes, ragas, and related scale families. |
| `fl_scale_get` | `read-only` | Returns intervals and note mapping for a selected scale. |

### Effect Slot And Native EQ Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_effect` | `write-safe` | Consolidated effect-slot and native EQ domain tool. Actions include get_slot, list_slots, get_track_slots_enabled, set_slot_enabled, set_slot_mix, set_track_slots_enabled, get_eq, and set_eq_band. |

### Export Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_export_midi` | `external-write` | Writes a type-1 MIDI file to disk from an arrangement specification. |

### Mix Doctor Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_diagnose_mix` | `read-only` | Scans the mix and reports concrete issues with evidence and proposed fixes. |
| `fl_apply_mix_fix` | `write-safe` | Applies one gated Mix Doctor fix through the safety layer. |
| `fl_mix_watch_start` | `read-only` | Starts full-song peak watching for better level evidence. |
| `fl_mix_watch_status` | `read-only` | Reports current peak-watch status. |
| `fl_mix_watch_stop` | `read-only` | Stops peak watching and returns a diagnosis. |
| `fl_gain_stage` | `read-only` | Proposes level trims for healthier gain staging. |
| `fl_reference_match` | `read-only` | Compares level and balance against a reference audio file. |

### Mixing Intent Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_apply_eq_intent` | `write-safe` | Applies a musical EQ intent to a target plugin or native EQ path. |
| `fl_apply_reverb_intent` | `write-safe` | Applies a calibrated reverb intent to an already-loaded plugin. |
| `fl_apply_delay_intent` | `write-safe` | Applies a calibrated delay intent to an already-loaded plugin. |
| `fl_get_track_level` | `read-only` | Reads a mixer track's current level in dB. |
| `fl_apply_compression_intent` | `write-safe` | Applies a calibrated compression intent, optionally level-aware. |

### Domain, Batch, Project, And Safety Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_transport` | `write-safe` | Consolidated transport domain tool. Actions include ping, get_tempo, set_tempo, get_play_state, play, stop, toggle_play, record, get_song_position, set_song_position, get_time_signature, and set_time_signature. Runtime controls are transient; tempo and time-signature writes use rollback. |
| `fl_mixer` | `write-safe` | Consolidated mixer domain tool. Actions include list, get, get_selected, get_route, select, set_color, set_mute, set_name, set_pan, set_route, set_solo, set_stereo_separation, and set_volume. |
| `fl_channel` | `write-safe` | Consolidated Channel Rack domain tool. Actions include list, get, get_selected, get_steps, classify, select, set_color, set_mute, set_mixer_target, set_name, set_pan, set_solo, set_steps, and set_volume. |
| `fl_pattern` | `write-safe` | Consolidated pattern domain tool. Actions include list, get, get_length, get_selected, find_empty, select, rename, set_color, and set_length. |
| `fl_playlist` | `write-safe` | Consolidated playlist-track domain tool. Actions include list, get, select, set_color, set_mute, set_name, and set_solo. Playlist clip editing is not supported. |
| `fl_effect` | `write-safe` | Consolidated effect-slot and native EQ domain tool. |
| `fl_plugin` | `write-safe` | Consolidated already-loaded plugin domain tool for list, list_params, get_param, and set_param. Plugin loading stays manual. |
| `fl_piano_roll` | `write-safe` | Consolidated Piano Roll domain tool for undo-backed note writes, transforms, markers, and explicit readback-limit reports. |
| `fl_batch` | `write-safe` | Runs strict-whitelisted registry read batches or homogeneous persistent-write batches through one named rollback unit. |
| `fl_get_project_state` | `read-only` | Reads project-level state such as tempo, time signature, and counts. |
| `fl_mixer_get_levels` | `read-only` | Reads mixer peak levels. |
| `fl_take_snapshot` | `server-state` | Captures MCP safety-layer snapshot data for inspection. |
| `fl_get_change_history` | `read-only` | Lists recent MCP changelog entries. |
| `fl_get_change_log_summary` | `read-only` | Returns a markdown table summary of recent rollback units and IDs. |
| `fl_export_change_log` | `external-write` | Exports the MCP changelog to a JSON file on disk. |
| `fl_rollback_last_change` | `server-state` | Rolls back the latest MCP change. |
| `fl_rollback_change` | `server-state` | Rolls back a specific change by change ID. |
| `fl_set_dry_run` | `server-state` | Enables or disables dry-run mode for planned changes. |

### Project Organizer Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_analyze_project_organization` | `read-only` | Finds unnamed, uncolored, and ungrouped channels. |
| `fl_plan_project_cleanup` | `read-only` | Plans naming and coloring fixes. |
| `fl_apply_project_cleanup_step` | `write-safe` | Applies a batch of specific name and color fixes. |
| `fl_apply_naming_standard` | `write-safe` | Batch applies a naming schema (e.g., psytrance) across channels and buses. |
| `fl_apply_color_standard` | `write-safe` | Batch applies a color schema (e.g., psytrance) across channels and buses. |

### Pattern And Playlist Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_pattern` | `write-safe` | Consolidated pattern domain tool for reads and rollback-backed metadata/control writes. |
| `fl_playlist` | `write-safe` | Consolidated playlist-track domain tool for track metadata/control only. Playlist clip editing is not supported. |

### Piano Roll Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_piano_roll` | `write-safe` | Consolidated Piano Roll domain tool. Actions include write_notes, write_chord, clear, quantize, transpose, duplicate, velocity_ramp, add_marker, add_time_signature_marker, clear_markers, get_notes, and probe_return_channel. |

### Plugin Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_plugin` | `write-safe` | Consolidated already-loaded plugin domain tool for plugin listing, parameter listing, parameter read, and rollback-backed parameter write. |
| `fl_plugin_get_preset_name` | `read-only` | Reads the current plugin preset name where FL exposes it. |
| `fl_plugin_next_preset` | `read-only` | Returns manual guidance for moving to the next preset; it does not mutate FL. |
| `fl_plugin_prev_preset` | `read-only` | Returns manual guidance for moving to the previous preset; it does not mutate FL. |

### Preset Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_list_presets` | `read-only` | Lists presets found on disk. |
| `fl_suggest_preset` | `read-only` | Suggests presets from the local library based on a description. |

### Project Doctor Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_project_health_report` | `read-only` | Reports project organization and health issues. |
| `fl_export_readiness_report` | `read-only` | Reports issues that may block or degrade export readiness. |
| `fl_project_dry_run_fix_plan` | `read-only` | Produces a fix plan without changing FL Studio. |
| `fl_project_health_dashboard` | `read-only` | A single pane of glass aggregating Mix Doctor, Routing Doctor, and Project Organizer insights. |
| `fl_preflight_project` | `read-only` | Export readiness checks covering clipping, unrouted channels, and manual checklists. |
| `fl_start_guided_fix_mode` | `read-only` | Starts an LLM-orchestrated Guided Fix Mode session by returning a stateless session blueprint. |
| `fl_get_guided_fix_context` | `read-only` | Reconstructs the current Guided Fix context from fresh diagnostics without relying on conversational history. |

### Routing Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_get_routing_all` | `read-only` | Reads the full mixer routing matrix. |
| `fl_get_channel_routing` | `read-only` | Reads channel-to-mixer routing. |
| `fl_detect_cleanup_candidates` | `read-only` | Finds likely routing or organization cleanup candidates. |
| `fl_analyze_routing` | `read-only` | Analyzes structural routing issues like unrouted channels or generators skipping groups. |
| `fl_plan_routing_fix` | `read-only` | Proposes renaming and routing fixes for structural issues. |
| `fl_apply_routing_batch` | `write-safe` | Executes batch routing fixes. |
| `fl_create_bus_layout` | `write-safe` | Routes sources to newly created grouped buses (e.g., in 10-track blocks). |
| `fl_group_tracks` | `write-safe` | Routes selected tracks into a named bus as one grouped rollback unit. |

### Transport Tools

| Tool | Safety | What it does |
|---|---|---|
| `fl_transport` | `write-safe` | Consolidated transport domain tool for ping, reads, rollback-backed tempo/time-signature writes, and transient playback controls. |

## Boundaries To State Clearly To Users

- The app cannot load or insert plugins. Users load plugins manually, then the
  assistant can inspect and configure already-loaded plugins.
- The app does not expose project open, new, save-as, render, pattern deletion,
  playlist clip editing, or raw UI automation tools.
- Piano Roll writes use an armed `MCP_Apply` script and FL undo for rollback;
  structured note readback is still API-limited.
- FL Studio API behavior can be build-dependent. The known-working baseline is
  documented in the README, and live probes should be run before relying on a
  new FL Studio build for write-heavy work.
