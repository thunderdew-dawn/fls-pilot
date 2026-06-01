---
name: flstudio-production
description: Use this skill when the user wants Claude/Codex to control FL Studio through FLStudioMCP, diagnose or organize a project, write Piano Roll notes, edit mixer/channel/pattern/playlist state, configure already-loaded plugins, export MIDI, or troubleshoot the FL bridge. Always prefer rollback-safe MCP tools over manual instructions when a tool exists.
---

# FL Studio Production

Use the FLStudioMCP tool surface as a rollback-first production assistant.

## Start Every Session

1. Call `fl_ping` before live FL work.
2. Confirm the reported controller build is the one expected by the current
   code or roadmap checkpoint.
3. If a write is requested, read current state first, apply the smallest useful
   change, verify readback, and keep the rollback path visible.
4. For Piano Roll writes, remind the user once per FL session to run
   `MCP Apply` from the Piano Roll Scripting menu if the bridge is not armed.

## Safety Rules

- Read-only tools may be used freely.
- Persistent FL writes must be rollback-backed. If a write result is
  unexpected, use `fl_rollback_last_change` immediately.
- External writes such as `fl_export_midi` write files only; they do not mutate
  FL Studio state.
- Do not load plugins, delete patterns/clips, automate broad UI actions, or use
  raw FL API escape hatches.
- If an officially documented API fails in a live test, treat it as
  `documented-unconfirmed` and run a targeted false-positive probe before
  discarding the capability.

## References

Read only the references needed for the current task:

- `references/limits.md` before promising or rejecting an FL capability.
- `references/tool-map.md` to choose the right MCP tool for a user request.
- `references/workflows.md` for common production workflows.
- `references/troubleshooting.md` when bridge, daemon, readback, or rollback
  behavior is unclear.

## Response Style

Tell the user exactly what changed, what was only diagnosed or planned, what was
rolled back, and which API limits still apply. Avoid vague claims such as
"configured" unless readback or rollback evidence supports them.
