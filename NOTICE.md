# Project Provenance

`flstudio-mcp` is a maintained fork of
[`rosasynthesiz/flstudio-mcp`](https://github.com/rosasynthesiz/flstudio-mcp).
The original project name and Python package name are retained
for compatibility with existing MCP client configurations, installer scripts,
and downstream references. (Command names were originally retained but have been
consolidated and renamed as of v2.0.0).

The current maintained repository is
[`thunderdew-dawn/flstudio-mcp`](https://github.com/thunderdew-dawn/flstudio-mcp).

## What This Fork Adds

This fork has diverged materially from the upstream baseline. Its engineering
direction is a rollback-first FL Studio production assistant rather than a broad
API wrapper surface.

Core additions and maintained differences include:

- A MIDI SysEx transport and standalone daemon for reliable FL controller
  communication across MCP clients.
- macOS setup support through the IAC Driver, alongside Windows loopMIDI.
- A safety layer requiring scoped snapshot, smallest practical write, readback,
  persisted changelog entry, and rollback path for every project-state write.
- API capability classification and live-probe discipline for FL scripting
  behavior that differs by build.
- A documented production tool suite covering mix diagnosis, routing, channel
  organization, Piano Roll operations, composition, audio analysis, plugin
  parameter control, and project-readiness reports.
- Strict exclusions for unsafe surfaces such as plugin loading, broad raw API
  escape hatches, playlist clip editing, project save/render automation, and
  full-project restore claims.
- CI, safety audits, prompt-level evals, an agent workflow guide, and roadmap
  checkpoints that keep the implementation reviewable.

## Attribution

The upstream MIT license and original copyright notice are preserved in
`LICENSE`. New work in this fork is maintained by `thunderdew-dawn` and
contributors under the same MIT license.
