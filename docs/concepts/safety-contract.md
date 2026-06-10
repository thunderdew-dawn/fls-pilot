# Safety Model

These rules apply to all agents working with FLStudioPilot, whether they are
using the software, changing the repository, or planning GitHub work.

## Write Safety Gates

Every persistent FL Studio write must follow:

1. Scoped snapshot.
2. Smallest practical write.
3. Readback verification where supported.
4. Changelog entry.
5. Rollback path.

Multi-step persistent changes must be one named rollback unit unless the split
is explicit and documented. Piano Roll writes stay undo-backed and must state
readback limits.

## Stop And Fallback Rules

- Do not guess normalized values, dB/Hz mappings, REC event IDs, track indices,
  plugin parameter indices, or valid ranges.
- Do not edit MIDI/TCP ports unless the user asks for setup troubleshooting.
- Do not auto-load plugins, insert plugins, delete patterns/clips, edit playlist
  clips, save-as, render, or use raw escape hatches.
- Do not promise Stretch Pro, Normalize, native EQ type, Piano Roll readback, or
  other unsupported FL API behavior.
- If bridge status, target selection, readback, rollback, or API support is
  unclear, switch to read-only, dry-run, probe-only, or manual guidance.

## Do Not Ship As User-Facing Tools

- Plugin loading or insertion.
- Playlist clip editing, placement, movement, or deletion.
- Pattern or clip deletion.
- Project open, new, save-as, or render automation.
- Raw controller/API escape hatches.
- Full FLP snapshot or full-project restore claims.
- Broad UI automation tools.
- Unsafe automation recording tools.

Plugin work should configure already-loaded plugins only. Loading stays manual.

## Required Safety Posture

- No FL Studio project-state mutation may ship without rollback.
- Read-only actions are the only exception.
- Every persistent write must follow the write safety gates above.
- Multi-step changes must be one named rollback unit unless there is a clear,
  documented reason to split them.
- If API support, readback, or rollback is unclear, implement read-only,
  dry-run, manual-guidance, or probe-only behavior.
- Keep Piano Roll transforms undo-backed and explicit about readback limits.
- Normalize and Stretch Pro behavior remains probe-dependent; do not promise it.

## Documented API Failures

If an officially documented API fails or behaves differently in a live test, do
not immediately discard the capability. Classify it as
`documented-unconfirmed` and run a targeted false-positive probe before
demoting it. The probe must check API presence, target selection/focus,
indexing, readback timing, target/plugin state, and rollback on the current FL
build.
