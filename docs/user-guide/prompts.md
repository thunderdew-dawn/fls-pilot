# Prompts

This page collects useful user prompts for working with fls-pilot. Users do not need to know tool names, but direct tool names remain available for precision.

## Module Examples

Each example is a user prompt. The assistant may call several tools behind the
scenes. For workflows that may write to FL Studio, the default behavior is to
scan/read-only first, propose one reversible action with a risk level, ask for
explicit confirmation, apply at most one approved change, read back where
supported, report before/after plus rollback or `change_id`, then stop.

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
Find channels that are not routed to mixer tracks. Propose the safest one-track
routing fix with a risk level, but do not apply it until I confirm.
```

Typical tools: `fl_detect_unassigned_channels`,
`fl_assign_channel_to_free_mixer_track`, `fl_channel`.

### Patterns, Playlist, And Arrangement

Prompt:

```text
Review my pattern and playlist metadata first. Propose one low-risk reversible
organization change, ask for confirmation, then stop.
```

Typical tools: `fl_arrange_new_pattern`, `fl_arrange_clone_pattern`,
`fl_pattern`, `fl_arrange_add_marker`.

### Piano Roll And Scale Composition

Prompt:

```text
Prepare an 8-bar D Dorian melody plan for the selected channel. Tell me the
risk level and wait for confirmation before writing to the Piano Roll.
```

Typical tools: `fl_scale_get`, `fl_piano_roll`, or the higher-level
`fl_write_raga_melody`.

### Plugins, Effects, And Mixing Intents

Prompt:

```text
Find the EQ on the lead vocal and propose one rollback-safe harshness reduction
around 3 kHz. Include the risk level and wait for confirmation.
```

Typical tools: `fl_plugin`, `fl_apply_eq_intent`.

> **Note on UI Refresh:** When the assistant applies EQ or plugin changes via `fl_apply_eq_intent`, the parameters take effect immediately in the audio engine. However, if the plugin window is currently open in FL Studio, the GUI may not visually update until the user clicks on it or reopens the window.

### Mix Review

Prompt:

```text
Run Mix Review, explain the top three problems, and apply only the safest
headroom fix first after I confirm the exact proposed change.
```

Typical tools: `fl_review_mix`, `fl_review_low_end_stereo`, `fl_gain_stage`,
`fl_apply_mix_adjustment`, `fl_get_change_history`.

### Routing, Bulk Control, And Color

Prompt:

```text
Review routing first. Propose one low-risk rollback-safe routing change with a
risk level and wait for confirmation before applying it.
```

Typical tools: `fl_detect_cleanup_candidates`, `fl_group_tracks`,
`fl_mute_tracks`, `fl_clear_mute_solo`.

### Project Health And Export Readiness

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

### Safety-First Examples

```text
Scan my mix first. Do not change anything yet. Tell me the safest next action,
its risk level, and offer only one reversible fix.
```

```text
Review the routing first. Give me a read-only diagnosis and one low-risk
rollback-safe routing change to approve.
```

```text
Prepare this project for export. Report blockers first, use dry-run planning,
and stop before applying anything.
```

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

## Prompting Tips

Use intent-first prompts when you want the assistant to choose tools:

```text
Prepare this project for export. Report problems first and give me a dry-run fix plan only.
```

Use tool-first prompts when you need deterministic control:

```text
Use fl_transport(action="get_tempo"), then fl_get_project_state.
```

Use safety-first prompts when the project is important:

```text
Make one reversible change, verify readback, report the rollback ID, then stop.
```
