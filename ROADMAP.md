# FL Studio AI Assistant Roadmap

## Purpose
This file is the active execution roadmap for the branch.

## Current Implementation Scope
1. Safety primitives and change history
2. API-backed quick wins
   - Step Sequencer Pack
   - Channel Organizer Pack
   - Pattern Management Pack
   - Playlist Track Organizer
   - Effect Slot and Native EQ Pack
3. Product-level workflows
   - Project Organizer MVP
   - Routing Doctor 2.0
   - Project Doctor / Health Report
   - Export readiness report
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

## Active Roadmap

### P0 — Safety and Evidence
- Safety primitives
- Change history
- Rollback by ID
- Knowledgebase updates
- API capability audit updates
- Live verification checkpoint discipline

### P1 — API-backed Core Workflows
- Channel Type Classifier
- Project Organizer MVP
- Naming Standard Assistant
- Color Standardizer
- Routing Doctor 2.0
- Bus Layout Planner
- Audio Clip Inspector
- Audio Clip Safe Defaults Assistant
- Preflight Project MVP
- Project Health Dashboard MVP
- Guided Fix Mode

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

### v1.1.0 — Project Organization & Routing Intelligence
- Channel Type Classifier
- Project Organizer MVP
- Naming Standard Assistant
- Color Standardizer
- Routing Doctor 2.0
- Audio Clip Inspector
- Audio Clip Safe Defaults Assistant
- Project Health Dashboard MVP
- Preflight Project MVP
- Change Log / Rollback UX improvements

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
