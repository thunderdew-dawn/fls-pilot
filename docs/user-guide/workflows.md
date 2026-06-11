# Workflows

This page explains how users normally work with fls-pilot through an AI assistant and how the safety model should be communicated.

## How Users Interact With The AI

The normal workflow is conversational:

1. The user asks for an outcome, for example "scan my mix and fix the worst
   headroom issue".
2. The assistant reads `fl://agent-briefing`, checks `fl://status`, and uses
   relevant resources such as `fl://mixer`, `fl://channels`, or specific tools.
3. For risky or multi-step work, the assistant explains what it plans to do and
   which changes are reversible.
4. The assistant applies one approved change or one named rollback unit.
5. The assistant reports what changed, what was skipped, and how to roll it
   back.

Users do not need to know tool names, but direct tool names are available for
precision. These are both valid:

```text
Please rename mixer track 8 to Drums and color it blue.
```

```text
Use fl_mixer with action set_name on track 8, then fl_mixer with action set_color on track 8.
```

## Safety Classes

| Safety class | Meaning |
|---|---|
| `read-only` | Reads FL Studio, files, or server context without mutating the project. |
| `write-safe-required` | Mutates FL Studio through the safety layer with snapshot, readback, changelog, and rollback. |
| `transient` | Controls runtime state such as playback or song position; it should not persist in the project. |
| `server-state` | Changes MCP server state, safety history, dry-run mode, or rollback state. |
| `external-write` | Writes outside FL Studio, such as a MIDI file or exported change log. |

## Rollback-First Operating Model

For any persistent FL Studio write, the assistant should follow this sequence:

1. Read the current state.
2. Snapshot the affected state.
3. Make the smallest practical change.
4. Read back the result.
5. Log restore data.
6. Report what changed and how it can be rolled back.

## Recommended Assistant Behavior

- Prefer diagnosis before mutation.
- Use dry-run mode for broad cleanup or export-readiness work.
- Apply only one approved change or one named rollback unit at a time when risk is non-trivial.
- Clearly state skipped actions when FL Studio API boundaries prevent safe automation.

## Related Pages

- [Prompts](prompts.md) for practical examples.
- [Tool Reference](tool-reference.md) for exact tool names and safety annotations.
