# FLStudioMCP Limits

## Hard Limits

- Do not load or insert plugins. Configure only plugins already loaded in the
  project.
- Do not delete patterns, playlist clips, or project state.
- Do not offer project open/new/save-as/render automation.
- Do not expose raw controller/API calls as user-facing actions.
- Do not claim full-FLP snapshots or full-project restore.
- Do not use broad UI automation as a substitute for API-backed tools.

## Probe-Gated Areas

- Native mixer EQ type/high-pass writes are documented-unconfirmed on the
  tested FL Studio 25.2.5 build. Frequency readback can change while the visible
  type remains unchanged, so do not promise high-pass configuration until a
  target-specific probe proves the type mapping.
- `patterns.setPatternLength` is documented but unavailable on the tested
  runtime. Keep it documented-unconfirmed for that build, not deleted.
- Effect-slot mix and some plugin parameter writes may be target/plugin/state
  dependent. A failing broad live test is not enough to demote a documented API.
- Normalize and Stretch Pro behavior for audio channels remains probe-dependent.

## False-Positive Probe Checklist

Before rejecting a documented API after a live failure, check:

- API presence on the current controller build.
- Correct target selection and focus.
- Track/channel/pattern/slot indexing.
- Readback timing or stale cached data.
- A rollback-safe temporary write and restoration.
- Whether the failure is plugin-specific or target-state-specific.

## Manual-Only Cases

When a capability is blocked by the limits above, give concise manual guidance
and continue with read-only planning or already-safe tools.
