# User Guide

fls-pilot turns FL Studio into a controllable production workspace for MCP-compatible AI assistants. This guide is split into focused pages for MkDocs:

- [Workflows](workflows.md): how users interact with the assistant, common production workflows, and safety classes.
- [Prompts](prompts.md): reusable prompt patterns and module-specific examples.
- [Tool Reference](tool-reference.md): MCP resources, full public tool catalog, and product boundaries.

## Why This App Exists

fls-pilot turns FL Studio into a controllable production workspace for any
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

## Recommended Reading Order

1. Start with [Workflows](workflows.md) to understand the normal interaction model and rollback-first safety approach.
2. Use [Prompts](prompts.md) when you want practical copy-and-paste examples.
3. Use [Tool Reference](tool-reference.md) when you need exact MCP tool names, safety classes, or boundaries.

## Quick Start

Most users can ask in plain language:

```text
Scan my mix first, explain the top three issues, and do not change anything yet.
```

For precise control, users can name tools directly:

```text
Use fl_mixer with action set_name on track 8, then fl_mixer with action set_color on track 8.
```
