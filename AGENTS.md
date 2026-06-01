# AGENTS.md

This file is the repository guide for AI-assisted coding in this workspace.
Follow it together with the higher-priority system/developer instructions.

## Mandatory First Reads

Before changing code, tests, docs, scripts, controller files, skill files, evals,
or roadmap state, read these files and follow them as binding project
instructions:

- `docs/ENGINEERING_STANDARDS.md`
- `ROADMAP.md`

If either file conflicts with an ad-hoc prompt, stop and surface the conflict
before implementing. The safety contract and roadmap scope are not optional.

## Working Mode

- Act as a senior, pragmatic software engineer.
- Inspect the repo before changing it. Read surrounding code, existing tool
  patterns, tests, safety layer, protocol constants, controller handlers, and
  registration style.
- For implementation work, explicitly inspect the relevant parts of
  `ROADMAP.md`, `docs/API_CAPABILITY_AUDIT.md`,
  `src/fl_studio_mcp/safety.py`, `src/fl_studio_mcp/protocol.py`, the FL
  controller script, existing tool modules, and focused tests/scripts before
  editing.
- For non-trivial implementation slices, produce a short implementation plan
  before editing and confirm the slice is dependency-correct and rollback-safe.
- Before building anything new, check whether the functionality already exists
  under a different name or can be composed from existing safe primitives.
- Prefer existing project patterns over new abstractions.
- Use established patterns: protocol constants, controller handlers,
  `safety.safe_write`, `safety.safe_write_group`, Piano Roll safety helpers,
  focused tests/scripts, and FastMCP registration style.
- Keep edits small, coherent, and backport-friendly.
- Preserve all user and uncommitted changes. Never revert unrelated work.
- Use English for commits, code comments, docstrings, and repo documentation.

## Required Safety Posture

- No FL Studio project-state mutation may ship without rollback.
- Read-only actions are the only exception.
- Every persistent write must follow:
  scoped snapshot -> smallest practical write -> readback -> changelog entry ->
  rollback path.
- Multi-step changes must be one named rollback unit unless there is a clear,
  documented reason to split them.
- If API support, readback, or rollback is unclear, implement read-only,
  dry-run, manual-guidance, or probe-only behavior.
- Keep Piano Roll transforms undo-backed and explicit about readback limits.
- Normalize and Stretch Pro behavior remains probe-dependent; do not promise it.

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

## Documented API Failures

If an officially documented API fails or behaves differently in a live test, do
not immediately discard the capability. Classify it as
`documented-unconfirmed` and run a targeted false-positive probe before
demoting it. The probe must check API presence, target selection/focus,
indexing, readback timing, target/plugin state, and rollback on the current FL
build.

## Implementation Checklist

For every new FL-mutating tool, add or update:

- Protocol command constants, if needed.
- FL controller handler.
- Snapshot scope.
- Restore operation.
- Readback verification.
- Safety-layer integration via the established safety helpers.
- Tool annotations and docstring explaining safety behavior.
- Static audit compatibility.
- Focused script/unit test or rollback-safe live smoke script.
- Roadmap/API audit/docs note when behavior or scope changes.

## Roadmap Discipline

- Treat `ROADMAP.md` as the active execution tracker.
- Keep it current in the same PR or commit series whenever a slice is
  completed, re-scoped, verified, blocked, or reprioritized.
- Record live FL verification checkpoints with date, FL build, controller build
  marker, tested path, and rollback result.
- Psytrance-specific features are out of scope until explicitly reintroduced.

## Commit Discipline

- Use sensible staged commits while working.
- Each commit should be a coherent feature slice or tightly scoped fix.
- Keep commits useful for cherry-picking by sister projects.
- Do not mix unrelated cleanup, formatting, and feature work.
- Commit messages must be English and explain the change clearly.

## Verification Expectations

Run the smallest meaningful checks for the changed area, then broaden when the
blast radius justifies it:

- Compile checks for touched Python code.
- `scripts/audit_tool_safety.py --fail-on-gaps`.
- `scripts/audit_tool_safety.py --fail-on-missing-safety-docs --format json`
  when tool annotations or docstrings change.
- Focused script tests for changed areas.
- FastMCP registration/tool-count checks when tool registration changes.
- Rollback-safe live smoke tests when FL Studio is available and the change
  touches live behavior.

If repo-wide `pytest` or `ruff` failures are pre-existing, report them
separately and do not churn unrelated code.

At handoff, summarize changed files, verification run, remaining risks or API
limits, and the next recommended roadmap slice.

## Local Environment

- Python target: 3.12 for current development on this machine. Package metadata
  still supports Python 3.10+ unless changed deliberately.
- On macOS, commands importing pip, XML, or audio dependencies may need:

```bash
export DYLD_LIBRARY_PATH="/usr/local/opt/expat/lib:${DYLD_LIBRARY_PATH:-}"
```

- Prefer `rg` and `rg --files` for search.
- Use `apply_patch` for manual file edits.
- Do not use destructive Git commands unless explicitly requested.

## Live FL Studio Procedure

- Start the TCP daemon yourself when live tests require it.
- Confirm heartbeat and `fl_ping` before live work.
- Confirm the controller build marker expected by the current code.
- Read current state before writing.
- For live write tests, write a temporary value, verify readback, rollback
  immediately, and verify restoration.
- If MIDI routing, script reload, or restart state is uncertain, diagnose the
  connection before changing code.
- Stop daemons you started and leave playback stopped/recording disarmed after
  tests.
