# FL Studio AI Assistant Roadmap

## Purpose
This file is the active execution roadmap for the branch.

## Current Implementation Scope
1. Safety primitives and change history
2. API-backed project organization and routing workflows
3. Product-level project preparation workflows
4. Creative intelligence and experimental infrastructure

## Current Stable Capabilities
- Mix Doctor
- Knowledgebase & Safe Wrappers
- Full-song peak watch
- Plugin parameter control
- Gain staging
- Reference match
- Bulk track control
- Track/channel coloring
- MIDI export
- Audio analysis basics
- Channel Type Classifier
- Project Organizer MVP
- Naming Standard Assistant
- Color Standardizer
- Routing Doctor 2.0
- Audio Clip Inspector
- Audio Clip Safe Defaults Assistant
- Project Health Dashboard MVP
- Preflight Project MVP
- Guided Fix Mode
- Change Log / Rollback UX improvements

## Verified FL Studio API Capabilities
- `channels.setChannelName` works
- `channels.setTargetFxTrack` works
- `channels.getChannelType` works and can distinguish `CT_AudioClip`, `CT_Sampler`, `CT_GenPlug`, etc.
- Mixer fader dB read/write calibration exists via empirical calibration table
- Controller/build-specific behavior must remain documented with build markers

## Known FL Studio API Limitations
- Stretch Mode cannot currently be read or set through the verified FL Python API path.
- Normalize cannot currently be read or set through the verified FL Python API path.
- Deep sample parameters are not exposed reliably.
- AudioClip handling may rename, route, color, lower volume, and produce manual checklists, but must not claim automatic Stretch Pro or Normalize handling.
- Native EQ type / high-pass configuration remains documented-unconfirmed unless a verified rollback-safe API path exists.
- Plugin loading/insertion remains manual.
- Playlist clip editing/deletion and destructive pattern/clip deletion remain out of scope.

## Completed Release Milestones

### v1.1.0 — Project Organization & Routing Intelligence
- [x] Channel Type Classifier
- [x] Project Organizer MVP
- [x] Naming Standard Assistant
- [x] Color Standardizer
- [x] Routing Doctor 2.0
- [x] Audio Clip Inspector
- [x] Audio Clip Safe Defaults Assistant
- [x] Project Health Dashboard MVP
- [x] Preflight Project MVP
- [x] Guided Fix Mode
- [x] Change Log / Rollback UX improvements

Verified live against FL Studio via TCP bridge on macOS, including guided-fix workflow and EQ parameter application.

## Active Roadmap

### P0 — Safety and Evidence
- Keep safety primitives current
- Keep rollback by ID reliable
- Keep Knowledgebase entries updated
- Keep API capability audit updated
- Keep live verification checkpoints documented
- Preserve build-specific evidence with FL Studio build and controller marker

### P1 — Jam-to-Project / Structured Cleanup Workflows
- Jam Session Analyzer
- Jam Session Cleanup Plan Generator
- Grouped cleanup application with named rollback units
- Existing-structure preservation mode
- Bus placement policy:
  - default: `before_group`
  - supported: `before_group`, `after_group`, `central_front`, `central_end`, `preserve_existing`
- Send channel preparation
- Global automation lane preparation
- Send automation lane preparation
- Final Project Health / Preflight integration

### P2 — Product-level Workflows
- Export & Delivery Assistant
- Stem Export Manager
- Session Setup Templates
- Plugin Chain Assistant 2.0
- Arrangement Coach
- Energy Curve Analyzer
- Transition Doctor
- Low-End Safety Assistant
- Sidechain Doctor
- Creative Block Breaker
- Explain My Mix
- Reference Track Deconstruction
- Handoff Report

### P3 — Later / Experimental / API-dependent
- Hook / Motif Coach
- Automation Analyzer
- Automation Pack Generator
- A/B Variant Manager
- Plugin Replacement Assistant
- CPU / Performance Doctor
- Compare Project Against Reference Structure
- Deep Sample & Loop Intelligence
- Optional TCP/push-event transport research
- Piano Roll readback research
- REC automation write/readback probes

## Current Next Release Candidate

### v1.2.0 — Jam-to-Project Assistant

Goal:
Turn an unstructured jam session into a structured, production-ready FL Studio project.

Proposed scope:
- `fl_analyze_jam_session()`
- `fl_plan_jam_session_cleanup()`
- `fl_apply_jam_session_cleanup_step(plan_id, step_id)`
- `fl_apply_jam_session_cleanup_group(plan_id, group_id)`
- `fl_finalize_jam_session_cleanup()`

The assistant should detect and organize inconsistent or missing names across:
- patterns
- playlist tracks
- channels/generators
- mixer tracks

It should also prepare or propose:
- consistent colors
- channel-to-mixer routing
- bus layout
- send channels
- global automation lanes
- send automation lanes
- final preflight checks

Safety:
- Plan first.
- No large cleanup without user approval.
- Each applied step or group must be one named rollback unit.
- Preserve recognizable existing structure when detected.
- Do not move/delete playlist clips.
- Do not delete patterns or clips.
- Do not load plugins.
- Do not claim automatic Stretch Pro or Normalize handling.

## Out of Scope For Current Push
- Plugin loading or insertion
- Playlist clip editing, placement, movement, or deletion
- Pattern or clip deletion
- Project open/new/save-as/render automation
- Raw controller/API escape hatches
- Broad UI automation tools
- Full FLP snapshot or full-project restore claims
- Unsafe automation recording tools
- Automatic Stretch Pro / Normalize handling

## Safety & Documentation Links
- [Engineering Standards](docs/ENGINEERING_STANDARDS.md)
- [API Capability Audit](docs/API_CAPABILITY_AUDIT.md)
- [Verification History](docs/VERIFICATION_HISTORY.md)
- [Backlog Research](docs/BACKLOG_RESEARCH.md)