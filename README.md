![version](https://img.shields.io/badge/version-3.0.0a1-blue)
![status](https://img.shields.io/badge/status-alpha-orange)
[![CI](https://github.com/thunderdew-dawn/fls-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/thunderdew-dawn/fls-pilot/actions/workflows/ci.yml)
[![CodeQL](https://github.com/thunderdew-dawn/fls-pilot/actions/workflows/codeql.yml/badge.svg)](https://github.com/thunderdew-dawn/fls-pilot/actions/workflows/codeql.yml)
![license](https://img.shields.io/badge/license-MIT-green)

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D6?logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-12%2B-000000?logo=apple&logoColor=white)
![FL Studio](https://img.shields.io/badge/FL%20Studio-2025%2B-orange)

![rollback-first](https://img.shields.io/badge/safety-rollback--first-brightgreen)
![readback](https://img.shields.io/badge/writes-readback%20gated-blue)
![api-evidence](https://img.shields.io/badge/API-evidence%20based-purple)
![no-UI-claims](https://img.shields.io/badge/limits-explicit-lightgrey)

![MCP](https://img.shields.io/badge/MCP-compatible-6f42c1)
![LLM](https://img.shields.io/badge/LLM-Claude%20%7C%20ChatGPT%20%7C%20Cursor-blueviolet)
![DAW](https://img.shields.io/badge/DAW-FL%20Studio-orange)

# fls-pilot

**Rollback-first FL Studio control for MCP-compatible LLMs: AI mixing, composition, project cleanup, routing review, and production assistance through natural language.**

*The LLM assistant diagnosing and fixing a mix in FL Studio through natural language.*

## Overview

fls-pilot is a Model Context Protocol (MCP) server that lets MCP-compatible clients such as Claude Desktop, ChatGPT Desktop, Cursor, and other MCP hosts control FL Studio through FL Studio's scripting API and a safety-focused server layer.

It is built for real music-production workflows: mix diagnosis, live peak watching, project cleanup, naming and color standards, routing review, plugin-chain planning, MIDI export, piano-roll composition, audio analysis, and export-readiness checks.

The project is intentionally **rollback-first**. Supported project mutations are routed through scoped snapshots, smallest-practical writes, readback where FL Studio exposes it, changelog entries, and rollback paths. Where FL Studio's API does not expose functionality, fls-pilot states that boundary explicitly instead of pretending the assistant can do it.

## High-Level Tools

The highest-value entry points for day-to-day production work are:

1. **Mix Review:** Scan a playing mix for clipping, peak risks, and balance problems, then propose reversible fixes.
2. **Project Organizer & Naming Standard Assistant:** Rename, color, group, and route channels and mixer tracks where FL Studio exposes the required metadata.
3. **Routing Review 2.0:** Detect routing problems, unrouted channels, and fragile bus layouts; propose and apply supported fixes as rollback units.
4. **Plugin & Preset Assistant:** Suggest chains and presets based on the user's installed plugin database and preset folders.
5. **Composition & Scale Composer:** Generate chord progressions and melodies in a selected scale or mode and write them through the piano-roll bridge.
6. **Audio Clip Safe Defaults:** Inspect audio clips, apply supported safe volume defaults, find free mixer tracks, and generate manual checklists for unavailable API states.
7. **Audio Analyzer:** Analyze external audio files for tempo/key and extract melodies to MIDI when optional audio extras are installed.
8. **Project Preflight & Health Overview:** Combine mix review, routing review, organization checks, and cleanup suggestions into an export-readiness report.

For detailed usage, examples, and the full tool catalog, see the [User Guide](docs/USER_GUIDE.md).

## How it Works: 8 Production Phases

FL Studio's Python API has strict boundaries. fls-pilot combines safe controller calls, local file analysis, generated Piano Roll scripts, a daemon-owned MIDI bridge, and a snapshot/rollback safety layer.

### Phase 1: Ideation & Composition

* **Audio Analysis (****`fl_analyze_audio`****, ****`fl_extract_melody`****)**

  * **Limitation:** FL Studio's API cannot read or analyze arbitrary audio files directly.
  * **Workflow:** fls-pilot reads `.wav` or `.mp3` files from disk and analyzes them with Python libraries. Accurate pitch tracking is available when optional audio extras are installed.

* **Piano Roll & Scales (****`fl_piano_roll`****, ****`fl_scale_get`****)**

  * **Limitation:** External programs cannot freely push notes into the Piano Roll at runtime through a direct public API.
  * **Workflow:** fls-pilot generates a temporary `MCP_Apply` script. The user arms the bridge once per session, and the daemon triggers the script through the configured shortcut.

### Phase 2: Arrangement & Structure

* **Patterns & Playlist (****`fl_pattern`****, ****`fl_playlist`****)**

  * **Limitation:** Direct editing, splitting, or moving of playlist clips is API-limited.
  * **Workflow:** fls-pilot manages supported pattern creation, cloning where exposed, section markers, and track metadata.

### Phase 3 & 4: Diagnosis & Preparation

* **Audio Clip Safe Defaults (****`fl_inspect_audio_clips`****)**

  * **Limitation:** Deep Audio Clip settings such as Stretch Pro, Normalize, and some sample internals are not exposed.
  * **Workflow:** fls-pilot applies safe Channel Rack volume defaults where supported, checks free mixer tracks, and creates manual checklists for unavailable API states.

* **Project Organizer (****`fl_channel`****, ****`fl_mixer`****, ****`fl_apply_color_standard`****)**

  * **Safety:** Large renaming, coloring, and routing operations use scoped snapshots and named rollback units.

### Phase 5: Signal Flow & Routing

* **Routing Tools (****`fl_review_routing`****, ****`fl_apply_bus_layout`****, ****`fl_group_tracks`****)**

  * **Workflow:** fls-pilot detects routing issues, proposes bus layouts, and applies supported routing changes through rollback-safe operations.

### Phase 6: Sound Design

* **Chain Planner & Presets (****`fl_setup_chain`****, ****`fl_suggest_preset`****)**

  * **Hard limit:** FL Studio's API cannot load or insert plugins.
  * **Workflow:** fls-pilot scans plugin database and preset folders, suggests suitable chains, and can configure supported parameters after the user manually loads the selected plugin.

### Phase 7: Mixing & Dynamics

* **Mix Doctor (****`fl_review_mix`****, ****`fl_mix_watch_start`****)**

  * **Limitation:** A static song snapshot is not enough because audio levels change over time.
  * **Workflow:** The user plays the song while fls-pilot polls live API peak meters and stores running peak evidence for each track.

* **Knowledgebase & Intents (****`fl_apply_eq_intent`****)**

  * **Problem:** LLMs can hallucinate invalid plugin or DAW parameter values.
  * **Workflow:** fls-pilot checks values against Knowledgebase conversion entries and verified ranges before sending supported changes to FL Studio.

### Phase 8: Export, Health & Safety

* **Project Health Checks (****`fl_check_project_preflight`****)**

  * **Workflow:** Before manual audio rendering, fls-pilot can run combined mix, routing, cleanup, and export-readiness checks.

* **MIDI Export (****`fl_export_midi`****)**

  * **Limitation:** FL Studio's API cannot click "Render to WAV".
  * **Workflow:** fls-pilot writes standard `.mid` files directly to disk. Audio bouncing remains manual.

* **Safety Layer (****`fl_rollback_last_change`****)**

  * **Limitation:** FL Studio's native undo can be unreliable for API scripts.
  * **Workflow:** fls-pilot stores scoped snapshots and changelog entries for supported writes. Rollback restores the affected supported state through the MCP safety path.

## What sets it apart

fls-pilot is a production assistant, not only a note sender.

* **Rollback-first writes:** project-modifying tools use snapshots, readback where available, changelog entries, and named rollback units.
* **API-evidence discipline:** FL Studio API limits are documented and handled explicitly.
* **Knowledgebase-backed parameters:** dB, Hz, normalized values, safe ranges, and known limits are stored in the local Knowledgebase.
* **Live-probe workflow:** build-dependent behavior is verified through smoke/probe scripts before relying on it for writes.
* **Real production focus:** mix review, routing review, project organization, plugin suggestions, piano-roll composition, MIDI export, and audio-file analysis.
* **LLM client flexibility:** designed for MCP-compatible clients rather than one hardcoded assistant.

> [!IMPORTANT]
> Version 3.0 is the breaking FL Studio Pilot rename. Use `fls-pilot`,
> `fls-pilot-daemon`, `fls_pilot`, `FLStudioPilot`, and `FLS_PILOT_*`;
> old package, command, import, controller, and environment-variable aliases are not retained.

## Capability Matrix

| Area        | Capability                              | Status      | Safety mode                                            | API reality                                                       | Tracking                                                                                         |
| ----------- | --------------------------------------- | ----------- | ------------------------------------------------------ | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Mix         | Mix Review / Peak Watch                 | 🟡 Alpha    | Read-only diagnosis → gated fixes                      | Live peak evidence required while the user plays the project      | [area](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Aworkflow) |
| Project     | Organizer / Naming / Colors             | 🟡 Alpha    | Snapshot + write + readback where supported + rollback | Supported where FL exposes channel and mixer metadata             | [area](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Aworkflow) |
| Routing     | Routing Review / Bus Layout             | 🟡 Alpha    | Proposal → approved write → rollback unit              | Routing writes require supported FL API readback                  | [area](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Aworkflow) |
| Composition | Piano Roll / Scale Composer             | 🟡 Alpha    | Generated script bridge                                | User must arm `MCP_Apply` once per session                        | [area](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Aworkflow) |
| Plugins     | Plugin Chain Planner / Preset Assistant | 🟠 Partial  | Suggest-only until user loads the plugin               | FL Studio API cannot load or insert plugins                       | [area](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Aapi)      |
| Audio       | Audio Analyzer / Melody Extraction      | 🟡 Optional | File analysis only                                     | Reads audio files from disk, not from the FL Studio API           | [area](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Aworkflow) |
| Export      | MIDI Export / Preflight                 | 🟡 Alpha    | File write + report                                    | Audio rendering remains manual because FL API cannot click Render | [area](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Aworkflow) |
| Safety      | Snapshot / Changelog / Rollback         | 🟡 Alpha    | Persistent change log + named rollback units           | Native FL undo is not reliable for API scripts                    | [area](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Asafety)   |

### Status Legend

| Symbol            | Meaning                                                                           |
| ----------------- | --------------------------------------------------------------------------------- |
| 🟢 Stable         | Tested and expected to work across supported builds                               |
| 🟡 Alpha          | Works, but still under active validation                                          |
| 🟠 Partial        | Useful, but constrained by FL Studio API limits                                   |
| 🔵 Read-only      | Reports or proposes only; does not mutate the project                             |
| 🛡️ Rollback-safe | Persistent writes use snapshot, readback where supported, changelog, and rollback |
| 🚧 Planned        | Tracked but not implemented                                                       |
| ⛔ Not possible    | Blocked by FL Studio API or DAW/UI boundary                                       |

## FL Studio API Reality

FL Studio's Python API is useful, but it does not expose the whole DAW. fls-pilot treats these limits as part of the product contract.

| Claim                         | Reality                                              | fls-pilot behavior                                                       |
| ----------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------ |
| Load plugins automatically    | ⛔ Not exposed by FL Studio's API                     | Suggests chains and presets; the user loads the chosen plugin manually   |
| Configure plugin parameters   | 🟠 Possible after plugin is loaded and mapped        | Uses safe normalized values where mappings are known                     |
| Write piano-roll notes        | 🟡 Possible through the armed script bridge          | Generates `MCP_Apply` script output and triggers the armed bridge        |
| Move/split playlist clips     | ⛔ API-limited                                        | Uses supported pattern, marker, metadata, and checklist workflows        |
| Read live mixer peaks         | 🟢 Supported                                         | Runs peak watch while the user plays the song                            |
| Render audio to WAV           | ⛔ UI-only                                            | User renders manually; fls-pilot can analyze the rendered file afterward |
| Rename/color/route tracks     | 🟡 Supported where the API exposes it                | Uses snapshot → write → readback → changelog → rollback                  |
| Set deep Audio Clip internals | ⛔ Not exposed for Stretch/Normalize/sample internals | Applies safe supported defaults and generates manual checklists          |

## Maintained fork

This repository is a materially extended fork of [`rosasynthesiz/flstudio-mcp`](https://github.com/rosasynthesiz/flstudio-mcp), now maintained at [`thunderdew-dawn/fls-pilot`](https://github.com/thunderdew-dawn/fls-pilot).

The project now uses the `fls-pilot` package and command names as an intentional breaking rename. Its engineering direction is explicit: rollback-first FL Studio production tooling, documented API-evidence handling, live-probe discipline for build-dependent behavior, macOS support, CI safety audits, prompt evals, and a committed agent workflow guide.

Breaking-release sequencing and migration gates are tracked in GitHub Project #7 and [release planning issue #66](https://github.com/thunderdew-dawn/fls-pilot/issues/66). See `NOTICE.md` for provenance and attribution.

## Project Status

The GitHub project board is the source of truth. Public Markdown snapshots are generated into `docs/generated/`.

* [Roadmap source of truth: GitHub Project #7](https://github.com/users/thunderdew-dawn/projects/7)
* [Public roadmap snapshot](docs/generated/ROADMAP.github.md)
* [Release planning issue #66](https://github.com/thunderdew-dawn/fls-pilot/issues/66)
* [Open release blockers](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+is%3Aopen+label%3Arelease-blocker)
* [API-limited work](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aapi-limited)
* [API-dependent work](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aapi-dependent)
* [FL Studio API work](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Aapi)
* [Safety-related work](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Asafety)
* [Workflow-related work](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Aworkflow)
* [Documentation work](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Aarea%3Adocs)
* [GitHub source-of-truth items](https://github.com/thunderdew-dawn/fls-pilot/issues?q=is%3Aissue+label%3Agithub-source-of-truth)
* [Issues and support](https://github.com/thunderdew-dawn/fls-pilot/issues), plus `SUPPORT.md`
* [Security policy](SECURITY.md)
* Generated roadmap/changelog snapshots: `docs/generated/` via the `Sync GitHub Markdown Snapshots` workflow
