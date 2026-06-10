# fls-pilot

fls-pilot is (not only) a Model Context Protocol (MCP) server that lets MCP-compatible clients such as Claude Desktop, ChatGPT Desktop, Cursor, and other MCP hosts control FL Studio through FL Studio's scripting API and a safety-focused server layer.

It is built for real music-production workflows: mix diagnosis, live peak watching, project cleanup, naming and color standards, routing review, plugin-chain planning, MIDI export, piano-roll composition, audio analysis, and export-readiness checks.

## Knowledgebase-first architecture

fls-pilot keeps verified FL Studio knowledge in a local, human- and machine-readable Knowledgebase: parameter ranges, dB/Hz/normalized mappings, known API limits, pitfalls, and safe workflow recipes. Agents are instructed to consult and extend this Knowledgebase instead of guessing.

## Token-efficient LLM workflows

The project treats token cost, tool-selection noise, and unnecessary MCP roundtrips as product-quality concerns. Runtime resources, KB lookup tools, capped context endpoints, and domain-specific workflows are designed to give LLMs the smallest useful context instead of dumping the whole project or tool surface into the prompt.

The project is intentionally **rollback-first**. Supported project mutations are routed through scoped snapshots, smallest-practical writes, readback where FL Studio exposes it, changelog entries, and rollback paths. Where FL Studio's API does not expose functionality, fls-pilot states that boundary explicitly instead of pretending the assistant can do it.

It is designed for real production workflows: mix review, project cleanup, routing checks, naming and color standards, plugin-chain planning, MIDI export, piano-roll composition, audio analysis, and export-readiness checks.

## What fls-pilot helps with

- Review mixes while FL Studio is playing
- Detect clipping, peak risks, and routing problems
- Organize channels and mixer tracks
- Apply naming, color, and routing standards where the FL Studio API supports it
- Suggest plugin chains and presets
- Generate piano-roll material through the script bridge
- Export MIDI files
- Analyze external audio files
- Create project health and preflight reports

## Safety first

fls-pilot is intentionally **rollback-first**.

Supported project changes use:

- scoped snapshots
- smallest-practical writes
- readback where FL Studio exposes it
- changelog entries
- rollback paths

Where FL Studio does not expose a feature through its API, fls-pilot documents that boundary instead of pretending the assistant can perform the action.

## Core workflows

### Mix Review

fls-pilot can watch live mixer peaks while the user plays the project and report clipping, headroom risks, and balance issues.

### Project Organizer

Rename, color, group, and route channels or mixer tracks where FL Studio exposes the required metadata.

### Routing Review

Detect fragile routing, unrouted channels, and bus-layout problems. Supported fixes are applied as rollback units.

### Plugin and Preset Assistant

Scan plugin databases and preset folders, suggest chains, and configure supported parameters after the user manually loads the plugin.

### Composition and Piano Roll

Generate scale-aware melodies, chords, and patterns through the armed piano-roll script bridge.

### Audio Analysis

Analyze `.wav` or `.mp3` files from disk for tempo, key, and melody extraction when optional audio extras are installed.

### Project Preflight

Combine mix review, routing review, organization checks, and cleanup suggestions into an export-readiness report.

## FL Studio API reality

FL Studio's Python API is useful, but it does not expose the whole DAW.

fls-pilot can work reliably with exposed API areas such as mixer peaks, channel metadata, supported routing, MIDI file writing, and scripted piano-roll workflows.

Some actions remain unavailable or manual:

- loading or inserting plugins
- moving or splitting playlist clips directly
- rendering audio to WAV
- changing deep Audio Clip internals such as Stretch Pro or Normalize

These limits are part of the product contract and are documented explicitly.

## Project status

The GitHub project board is the source of truth for roadmap and release planning.

Useful links:

- [User Guide](user-guide/index.md)
- [Generated roadmap](project/ROADMAP.github.md)
- [Issues and support](https://github.com/thunderdew-dawn/fls-pilot/issues)
- [Security policy](community/security.md)

## Maintained fork

fls-pilot is a materially extended and actively maintained fork of `rosasynthesiz/flstudio-mcp`.

The rename from `flstudio-mcp` to `fls-pilot` is intentional and breaking. It avoids package and command-name collisions and makes clear that this fork follows its own release path, compatibility contract, and engineering direction.

Attribution and provenance are documented in `docs/community/notice.md`.
