# User Guide

fls-pilot turns FL Studio into a controllable production workspace for MCP-compatible AI assistants. 

fls-pilot is (not only) a Model Context Protocol (MCP) server that lets MCP-compatible clients such as Claude Desktop, ChatGPT Desktop, Cursor, and other MCP hosts control FL Studio through FL Studio's scripting API and a safety-focused server layer.

It is built for real music-production workflows: mix diagnosis, live peak watching, project cleanup, naming and color standards, routing review, plugin-chain planning, MIDI export, piano-roll composition, audio analysis, and export-readiness checks.

Knowledgebase-first architecture
fls-pilot keeps verified FL Studio knowledge in a local, human- and machine-readable Knowledgebase: parameter ranges, dB/Hz/normalized mappings, known API limits, pitfalls, and safe workflow recipes. Agents are instructed to consult and extend this Knowledgebase instead of guessing.

Token-efficient LLM workflows
The project treats token cost, tool-selection noise, and unnecessary MCP roundtrips as product-quality concerns. Runtime resources, KB lookup tools, capped context endpoints, and domain-specific workflows are designed to give LLMs the smallest useful context instead of dumping the whole project or tool surface into the prompt.

The project is intentionally **rollback-first**. Supported project mutations are routed through scoped snapshots, smallest-practical writes, readback where FL Studio exposes it, changelog entries, and rollback paths. Where FL Studio's API does not expose functionality, fls-pilot states that boundary explicitly instead of pretending the assistant can do it.

This guide is split into focused pages for MkDocs:

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
