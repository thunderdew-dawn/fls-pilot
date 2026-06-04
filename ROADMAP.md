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

### P0.5 — Architecture Foundation & Tool Efficiency
- Regenerate the current tool inventory and lock the exact low-level
  consolidation scope before implementation.
- Consolidate redundant getter/setter tools into a compact low-level/domain
  surface; the target is roughly 19 low-level/domain tools plus retained
  product workflow tools.
- Keep high-value workflow tools such as Mix Doctor, Project Doctor, Routing
  Doctor, Project Organizer, audio analysis, MIDI export, resources, and
  Knowledgebase tools unless a later roadmap item explicitly removes them.
- Add an internal operation registry and validation layer before exposing new
  consolidated write paths.
- Strengthen grouped write safety before generic batching: pre-validate all
  operations, snapshot all write scopes before mutation, verify readback where
  supported, and handle partial failures with immediate rollback attempts.
- Add domain tools additively, then remove legacy low-level aliases only after
  parity tests, registration checks, documentation updates, and safety audit
  pass.
- Implement `fl_batch` with strict validation, a max 50 operation limit, one
  named rollback unit for persistent writes, and no mixed
  persistent/transient/external/Piano Roll batches without a separate safety
  design.
- Preserve the rollback contract; the safety audit must remain at 0 write gaps.

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

## Current Next Release Candidates

### v1.2.0 — Architecture Foundation & Tool Efficiency

Goal:
Reduce LLM token consumption, tool-selection noise, and avoidable MCP
round-trips by consolidating redundant low-level getter/setter tools into a
compact domain-driven surface. The target is roughly 19 low-level/domain tools
plus retained product workflow tools, not a total cap for the whole MCP server.

Current baseline:
- Latest static audit baseline observed 156 registered/static MCP tools.
- Phase 0 must regenerate the inventory before implementation and classify each
  current tool as keep, consolidate, remove, or blocked.
- Product workflows remain in scope unless explicitly removed by a later
  roadmap item.

Proposed scope:
- **Phase 0**: Inventory and scope lock, including registration/tool-count
  checks and duplicate-registration cleanup if confirmed.
- **Phase 1**: Operation registry and validation layer sourced from existing
  safe primitives and Knowledgebase data where available.
- **Phase 2**: Verified grouped write safety. `safe_write_group` is already used
  by user-facing tools, but generic batch exposure requires stronger readback,
  validation, and partial-failure rollback handling.
- **Phase 3**: Add domain tools additively for parity testing
  (`fl_transport`, `fl_mixer`, `fl_channel`, `fl_pattern`, `fl_playlist`,
  `fl_effect`, `fl_plugin`, `fl_piano_roll`, and optional `fl_safety`).
- **Phase 4**: Add `fl_batch` with strict whitelist validation and a hard max
  50 operation limit.
- **Phase 5**: Refactor product workflows internally only where the operation
  registry reduces meaningful duplication without weakening safety.
- **Phase 6**: Remove legacy low-level tools without deprecation wrappers after
  parity tests, docs, Knowledgebase updates, registration checks, and safety
  audit pass.

Safety:
- Consolidation and batching must not weaken the rollback contract.
- Persistent write batches must pre-validate every operation before mutation,
  snapshot all scopes before the first write, execute as one named rollback
  unit, and reject unsafe mixes of persistent writes, transient controls,
  external file writes, and Piano Roll undo-backed edits.
- `continue_on_error` is acceptable only for read-only batches unless a future
  safety design proves rollback-safe partial writes.
- `scripts/audit_tool_safety.py --fail-on-gaps` must remain green with 0 write
  gaps throughout the rollout.

### v1.3.0 — Jam-to-Project Assistant

Goal:
Turn an unstructured jam session into a structured, production-ready FL Studio project.
Reuse the v1.2 operation registry, domain tools, and batch infrastructure where
they are available and rollback-safe.

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
