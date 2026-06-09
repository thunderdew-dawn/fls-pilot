# Project Provenance

`fls-pilot` is a maintained, materially extended fork of
[`rosasynthesiz/flstudio-mcp`](https://github.com/rosasynthesiz/flstudio-mcp).

The current maintained repository is
[`thunderdew-dawn/fls-pilot`](https://github.com/thunderdew-dawn/fls-pilot).

The 3.0 line intentionally adopts the `fls-pilot` project, package, command,
controller, environment-variable, and import names as a breaking rename with no
compatibility aliases. This rename avoids confusion with the upstream project,
prevents package and command-name collisions in distribution channels such as
PyPI, and makes it clear that this fork now follows its own release path,
compatibility contract, and engineering direction.

## Relationship to the Upstream Project

The upstream `rosasynthesiz/flstudio-mcp` project established the foundation for
controlling FL Studio through an MCP server, including natural-language mixing
assistance, composition workflows, plugin and preset support, MIDI operations,
audio analysis, and project-safety concepts.

`fls-pilot` builds on that foundation, but has diverged into a broader
rollback-first FL Studio production assistant for MCP-compatible clients. The
fork is not intended to present itself as the same package, command-line tool,
or compatibility surface as the upstream project.

In short:

* `flstudio-mcp` is the respected upstream foundation.
* `fls-pilot` is a renamed, compatibility-breaking maintained fork.
* The fork keeps provenance and attribution visible while developing its own
  safety model, roadmap, release process, and production-tooling scope.

## What This Fork Adds

This fork has diverged materially from the upstream baseline. Its engineering
direction is a rollback-first FL Studio production assistant rather than only a
broad API wrapper surface.

Core additions and maintained differences include:

* A broader MCP-client target, including Claude Desktop, ChatGPT Desktop,
  Cursor, and other MCP-compatible hosts.
* A MIDI SysEx transport and standalone daemon for reliable FL controller
  communication across supported MCP clients.
* macOS setup support through the IAC Driver, alongside Windows loopMIDI.
* A safety layer requiring scoped snapshots, smallest-practical writes,
  readback where FL Studio exposes it, persisted changelog entries, and
  rollback paths for supported project-state writes.
* API capability classification and live-probe discipline for FL Studio
  scripting behavior that may differ by FL Studio build or platform.
* A documented production tool suite covering mix review, live peak watching,
  routing review, channel and mixer organization, Piano Roll operations,
  composition, audio-file analysis, plugin parameter control, project preflight,
  and export-readiness reports.
* Knowledgebase-backed parameter handling for dB, Hz, normalized values, safe
  ranges, and known API limits.
* A capability matrix and explicit FL Studio API reality documentation, so
  supported workflows, partial workflows, and unavailable DAW/UI-only actions
  are stated plainly.
* Strict exclusions for unsafe or unsupported surfaces such as automatic plugin
  loading, broad raw API escape hatches, playlist clip editing, project
  save/render automation, and full-project restore claims.
* CI checks, safety audits, prompt-level evaluations, an agent workflow guide,
  and roadmap checkpoints intended to keep implementation and releases
  reviewable.

## Attribution

We are grateful for the original work in
[`rosasynthesiz/flstudio-mcp`](https://github.com/rosasynthesiz/flstudio-mcp).
Its concepts and implementation provided the foundation that made this fork
possible.

The upstream MIT license and original copyright notice are preserved in
`LICENSE`. New work in this fork is maintained by `thunderdew-dawn` and
contributors under the same MIT license.

