# Changelog

This changelog is curated from the repository commit history and project documentation. It focuses on user-visible behavior, safety contracts, compatibility changes, and known FL Studio API boundaries. Routine formatting, metadata-only refreshes, one-off verification notes, and transient release housekeeping are intentionally omitted unless they change the public product contract.

## v2.0.0-stable - Architecture Foundation, Tool Efficiency, and Safety-First Production Workflows

**Release date:** 2026-06-07  
**Status:** Stable  
**Based on:** `main` through `d5dea16`, after the `v2.0.0-rc1` tag (`4ccfc85`)

### Release positioning

v2.0.0 stabilizes `flstudio-mcp` as a production-oriented MCP bridge for FL Studio rather than a collection of low-level transport and parameter helpers. The release consolidates the public tool surface, introduces a stronger operation registry and batching model, moves the recommended client-facing runtime to a localhost TCP daemon bridge, and makes rollback-first behavior the default expectation for persistent writes.

The release also makes a deliberate distinction between what the bridge can safely automate through FL Studio's exposed Python/controller APIs and what still requires manual FL Studio interaction. That distinction is now part of the release contract, not a footnote.

### Breaking changes and migration notes

- **Legacy low-level aliases were removed from public registration.** Use the consolidated domain tools instead of older one-purpose getter/setter aliases.
- **Public workflow names were cleaned up for the stable API.** Product-level tools now use consistent review/cleanup/preflight naming instead of compatibility aliases kept during earlier milestones.
- **The recommended stable transport is the daemon bridge.** MCP clients talk to the MCP server over stdio; the server talks to `fl-studio-mcp-daemon` over localhost TCP; the daemon owns the MIDI ports and forwards SysEx traffic to the FL Studio controller script. This avoids depending on every MCP client process being able to open MIDI devices directly.
- **Persistent writes are expected to go through audited write paths.** Batches and domain actions reject unsafe mixtures, unknown operations, and raw escape-hatch behavior rather than silently passing them through.
- **Some previously implied capabilities are explicitly not claimed.** Automatic plugin insertion/loading, preset recall inside FL Studio, destructive playlist/pattern edits, audio rendering, FLP save/open automation, and Stretch Pro/normalize clip operations remain outside the supported automation boundary unless FL Studio exposes safe APIs for them.

### Added

- **Consolidated domain tools** for common FL Studio work areas:
  - `fl_transport`
  - `fl_mixer`
  - `fl_channel`
  - `fl_pattern`
  - `fl_playlist`
  - `fl_effect`
  - `fl_plugin`
  - `fl_piano_roll`
  - `fl_batch`
- **Operation registry** for validating operation names, safety classes, parameter schemas, routing rules, and read/write behavior before requests reach the transport layer.
- **`fl_batch` execution** for safe multi-step reads and homogeneous persistent-write batches, including hard limits, write-safety checks, and no mixed unsafe operation classes.
- **Rollback-first write groups** with named units, snapshot/readback expectations, rollback metadata, and safer failure handling for persistent project mutations.
- **`fl://agent-briefing` resource** so an MCP-compatible LLM can discover the compact public tool surface, safety policy, rollback expectations, and recommended workflow without burning context on obsolete aliases.
- **Knowledgebase-backed policy metadata** for higher-level product tools, including policy references in findings and cleaner guidance for what is automatable versus advisory.
- **Low-End/Stereo Safety Assistant** via `fl_review_low_end_stereo`, including checks around mono/stereo expectations, pan and stereo separation readback, and mix-risk reporting.
- **Mix Review refinements** including clearer distinction between master/output clipping and insert-track headroom risk, threshold fixes, and more useful review metadata.
- **Project organization and routing review workflows** that combine naming, color, channel type classification, routing visibility, dry-run planning, and rollback-safe cleanup actions.
- **Preflight and guided cleanup workflows** for preparing a project before export, collaboration, or mix review without requiring the LLM to manually coordinate many low-level calls.
- **Plugin and preset library awareness** that reads installed FL Studio plugin database entries and preset folders from disk to suggest likely plugin chains or presets. These tools are advisory; they do not claim to load plugins or presets automatically inside FL Studio.
- **Live project resources** for common read-only state such as project, transport, channels, mixer, and patterns.
- **Audio and composition helpers carried forward into the stable line**, including audio analysis, MIDI export, scale/raga composition assistance, piano-roll helpers, and rollback-backed pattern/channel/effect comfort tools.

### Changed

- **The public API is smaller and more intentional.** Instead of exposing many narrow aliases directly to the LLM, v2.0.0 routes most interactions through compact domain actions with explicit parameters and safety classes.
- **Documentation now centers on actual workflow boundaries.** README, roadmap, architecture notes, user guide, verification history, and knowledgebase material were rewritten to describe supported phases, known API gaps, transport setup, and live-verification expectations.
- **The maintained fork provenance is explicit.** The project documents its origin from `rosasynthesiz/flstudio-mcp` while presenting the current fork as the maintained package line.
- **Transport documentation now reflects the real bridge topology.** The stable architecture is MCP client -> MCP server -> localhost TCP daemon -> MIDI SysEx -> FL Studio controller script, not a generic claim that FL Studio itself exposes a socket server to MCP clients.
- **Version and packaging metadata were updated to the 2.0.0 stable line**, including production/stable classifiers, supported Python versions, platform classifiers, optional audio extras, and console entry points for the MCP server and daemon.
- **Live verification and regression coverage were expanded.** RC1 follow-up commits added probes, routing/connectivity tests, threshold corrections, organizer fixes, and final safety/architecture documentation before stable publication.

### Fixed since v2.0.0-rc1

- Fixed Mix Review threshold logic so reported clipping/headroom findings align with the intended pre-fader and output-risk semantics.
- Fixed Project Organizer behavior around color validation and routed project cleanup paths.
- Fixed server routing/resource hints for bridge connectivity so transport failures are surfaced more clearly.
- Added RC1 live probes and regression tests around the compact public surface, routing, project organization, and safety primitives.
- Clarified low-end/stereo verification and daemon architecture details to avoid overstating what runs inside FL Studio's controller sandbox.

### Safety contract

- Read-only tools must stay read-only.
- Dry-run tools must describe intended actions without mutating the project.
- Persistent writes must pass through the safety layer, operation registry, and rollback-aware write grouping where applicable.
- Product tools should prefer diagnostics, plans, and bounded fixes over broad, irreversible edits.
- Unsafe or unsupported FL Studio operations should be reported as limitations or manual checklist items rather than hidden behind optimistic automation language.

### Known limitations and non-goals

These are intentionally documented so the stable release does not overpromise:

- FL Studio's public Python/controller APIs do not expose everything needed for full DAW automation.
- Plugin insertion/loading and preset recall remain advisory/manual workflows.
- Audio rendering, FLP save/open, and full project snapshot/restore are not part of the supported MCP contract.
- Playlist clip editing/deletion and destructive pattern deletion are outside the safe automation boundary.
- Stretch Pro, normalize, and detailed audio clip parameter mutation remain unavailable unless FL Studio exposes reliable APIs.
- Mix and project analysis can highlight risks and propose bounded fixes, but it should not be described as mastering, source separation, or guaranteed audio-quality correction.
- Any new FL Studio version or controller marker revision should be re-smoked before claiming live support beyond the documented verification environment.

### Intentionally de-emphasized in release notes

The following work exists in the history but should not be headline material for v2.0.0-stable because it is mostly internal or supporting work:

- Formatting-only and wording-only documentation passes.
- Metadata/index refreshes that did not change behavior.
- One-off verification logs that only confirm already documented behavior.
- Packaging housekeeping that does not affect installation, runtime, or supported APIs.
- Temporary compatibility shims removed before the stable release.

## v2.0.0-rc1 - Compact Public Tool Surface and Registry-Based Safety

**Release date:** 2026-06-05  
**Status:** Release candidate  
**Tag:** `v2.0.0-rc1`

### Added

- Initial compact domain-tool architecture for transport, mixer, channel, pattern, playlist, effects, plugins, piano roll, and batching.
- Registry-based operation validation and policy enforcement.
- Knowledgebase-backed product workflow policy references.
- Initial batch execution support for reducing round-trips and tool noise.
- Documentation and tests for the new architecture, tool migration, and safety expectations.

### Changed

- Began retiring the legacy alias-heavy public surface in favor of domain action tools.
- Reworked README, roadmap, verification history, and package metadata for the 2.0.0 line.
- Moved product workflows toward stable naming and clearer safety classes.

### Notes

The RC line was useful for validating the architecture but still needed threshold fixes, routing/project-organizer fixes, final low-end/stereo verification, and final public API cleanup before stable publication.

## v1.1.0 - Project Organization and Routing Intelligence

**Release date:** 2026-06-04  
**Status:** Milestone release line; not present as a Git tag in the current repository tag list

### Added

- Channel Type Classifier for identifying likely buses, inserts, instruments, audio tracks, sends, and utility channels from live project state.
- Project Organizer planning and rollback-safe cleanup for naming, colors, and track organization.
- Routing Review and Routing Cleanup workflows for finding suspicious mixer routing, missing routes, and project-structure issues.
- Audio Clip Inspector and safer clip-state reporting within the limits of FL Studio's exposed APIs.
- Project Health, Preflight, and Guided Cleanup workflows for higher-level review before export or collaboration.
- Live capability sweeps and tests around project organization, routing, guided mode, and rollback behavior.

### Changed

- Shifted from individual helper tools toward more workflow-oriented project review tools.
- Documented FL Studio API gaps more clearly, especially around clip mutation, plugin loading, and destructive edits.

## v1.0.0 - Maintained Fork Baseline, Cross-Platform Support, and Safety Layer

**Release date:** 2026-06-02  
**Status:** Tagged stable baseline  
**Tag:** `v1.0.0`

### Added

- Maintained fork baseline with package metadata, installation flow, documentation, and verification history.
- Cross-platform support for Windows and macOS setup, including macOS installation guidance and transport compatibility work.
- Standalone daemon/MIDI bridge support for environments where MCP clients cannot directly open MIDI ports.
- Rollback-aware safety layer for persistent writes, including named rollback units and safer write history.
- Live MCP resources for status/project/transport/channel/mixer/pattern state.
- Mix Doctor and Mix Review foundations, including full-song peak-watch behavior instead of relying only on short snapshots.
- Gain staging, reference-match, genre chain, plugin-chain, preset-suggestion, and library-aware advisory tools.
- Audio analysis helpers for tempo/key/pitch-style analysis where optional dependencies are installed.
- MIDI export and composition helpers, including scale/raga-oriented generation support.
- Piano-roll, note-bridge, arrangement, plugin-parameter, and mixing-intent workflows inherited from the upstream project and hardened in the maintained fork.

### Changed

- Reframed the project from a minimal FL Studio MCP experiment into a documented, safety-aware maintained fork.
- Expanded tests, audits, and safety classification docs around write behavior.
- Improved macOS compatibility and SSE/client compatibility documentation.

## v0.2.0 - MIDI SysEx Bridge and Early Workflow Expansion

**Status:** Historical pre-stable line

### Added

- MIDI SysEx bridge approach after FL Studio controller-script file writes proved unreliable in the controller sandbox.
- Virtual MIDI port setup and controller-script communication model.
- Early project, mixer, channel, pattern, playlist, note, plugin-parameter, and transport tools.
- Early arrangement, note writing, plugin parameter, and mix-intent helpers.

### Notes

This line established the practical transport foundation, but the public surface was still low-level and noisy compared with the stable v2.0.0 domain-tool API.

## v0.1.0 - Initial Prototype

**Status:** Withdrawn / replaced by the MIDI SysEx approach

### Notes

The original file-queue-oriented prototype was superseded because FL Studio controller-script file writes were not reliable enough for a stable MCP workflow.
