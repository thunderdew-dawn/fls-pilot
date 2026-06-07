# Changelog

## v2.0.0 -- Architecture Foundation, Tool Efficiency, and TCP Daemon Transport

**Major Release**: This release marks a significant architectural shift towards domain-driven tools, strict safety guarantees, and the migration to a robust TCP daemon for MCP server communication. It consolidates redundant legacy tools, drastically reducing LLM token consumption and tool-selection noise.

### What changed

#### Architecture & Transport
* **TCP Daemon Transport**: Migrated MCP-to-MIDI communication to a standalone `socketserver.ThreadingTCPServer` daemon (`fl-studio-mcp-daemon`). The MCP server now connects via TCP (`FLSTUDIO_MCP_TRANSPORT=tcp`), allowing the daemon to safely hold the virtual MIDI ports (SysEx) open across MCP client restarts. This ensures stable, high-throughput communication.
* **FastMCP Orchestration**: Shifted orchestration logic into `FastMCP` (via `@mcp.tool` registration).

#### Tool Consolidation & Domain Tools
* **Consolidated Domain Surface**: Replaced 86 legacy, one-off low-level aliases with a compact set of domain tools: `fl_transport`, `fl_mixer`, `fl_channel`, `fl_pattern`, `fl_playlist`, `fl_effect`, `fl_plugin`, `fl_piano_roll`, and `fl_batch`.
* **Read-Only & Persistent Batching (`fl_batch`)**: Introduced generic batching with strict whitelist validation, a hard 50-operation limit, and `continue_on_error` support for read operations.
* **Public Tool Footprint**: Reduced the registered public FastMCP tools to 87, focusing entirely on domain primitives and product workflows. 

#### Safety & State Mutation
* **Verified Grouped Write Safety**: `safety.safe_write_group` now pre-validates operations, snapshots all scopes before mutation, performs per-write readback where supported, enforces explicit verify readback pairs, and attempts immediate reverse rollback after a partial failure.
* **Zero Write Gaps**: All persistent FL Studio state mutations are strictly rollback-capable. The repository now passes `scripts/audit_tool_safety.py --fail-on-gaps` in CI.
* **Anti-Vibe Coding Compliance**: The codebase is strictly enforced by `audit_anti_vibe.py`, eliminating lazy evaluation, missing exception chains, and undocumented "quick fixes".

#### New Product Workflows
* **Low-End/Stereo Safety Assistant (`fl_review_low_end_stereo`)**: Reports bass/sub mono-compatibility risks, mixer pan/stereo-separation metadata, and Master headroom with compact Knowledgebase policy references.
* **Mix Review Polish**: User-facing findings now keep compact per-row KB metadata (`kb_rule_ids`, `kb_confidence_levels`), moving heavy rule context into top-level references.
* **Agent Orientation (`fl://agent-briefing`)**: A new compact entrypoint providing bridge status, Knowledgebase-first rules, and stop rules for LLM agents.

## v1.1.0 -- Project Organization & Routing Intelligence

* **Introduced**: Channel Type Classifier, Project Organizer MVP, Naming Standard Assistant, Color Standardizer, Routing Review 2.0.
* **Audio Clip Intelligence**: Added Audio Clip Inspector and Safe Defaults Assistant to help manage unwieldy sample drops.
* **Project Health**: Released Project Health Overview MVP, Project Preflight MVP, and Guided Cleanup Mode to orchestrate multi-step project standardizations.
* **Safety UX**: Change Log and Rollback UX improvements. Verified live against FL Studio via TCP bridge on macOS.

## v0.2.0 -- MIDI SysEx transport

**Breaking change**: The transport between the MCP server and the FL controller script switched from a file-based JSON queue to MIDI SysEx. Protocol version bumped 1 -> 2.

### Why
FL Studio's controller-script Python sandbox blocks every form of file write (e.g., `open("...", "w")`, `os.makedirs()`).

### What changed
* `protocol.py`: New SysEx wire format, base64-JSON payload.
* `connection.py`: Rewritten on `mido` + `python-rtmidi`.
* **Virtual MIDI Ports**: Requires `FLStudioMCP RX` and `FLStudioMCP TX`.

## v0.1.0 -- File-queue bridge (withdrawn)

Initial release. Withdrawn because the file-queue design did not work on FL builds that sandbox controller-script file I/O.
